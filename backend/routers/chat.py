import json
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from auth import get_user_id
from database import get_supabase
from models.schemas import MessageCreate
from services.openai_service import get_openai_client, create_thread, add_message_to_thread, stream_run

try:
    from langsmith import traceable
except ImportError:
    def traceable(func=None, **kwargs):
        if func:
            return func
        return lambda f: f

router = APIRouter(prefix="/api/threads", tags=["chat"])


@router.post("/{thread_id}/messages")
@traceable(name="chat_send_message")
async def send_message(
    thread_id: str,
    body: MessageCreate,
    user_id: str = Depends(get_user_id),
):
    db = get_supabase()

    # Verify thread belongs to user
    thread = (
        db.table("threads")
        .select("*")
        .eq("id", thread_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not thread.data:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Store user message
    user_msg = (
        db.table("messages")
        .insert({
            "thread_id": thread_id,
            "user_id": user_id,
            "role": "user",
            "content": body.content,
        })
        .execute()
    )

    client = get_openai_client()

    # Create OpenAI thread if needed
    openai_thread_id = thread.data.get("openai_thread_id")
    if not openai_thread_id:
        openai_thread_id = create_thread(client)
        db.table("threads").update({"openai_thread_id": openai_thread_id}).eq("id", thread_id).execute()

    # Add message to OpenAI thread
    add_message_to_thread(client, openai_thread_id, body.content)

    async def event_generator():
        full_content = ""
        try:
            for delta in stream_run(client, openai_thread_id):
                full_content += delta
                yield {
                    "event": "content_delta",
                    "data": json.dumps({"text": delta}),
                }

            # Store assistant message
            assistant_msg = (
                db.table("messages")
                .insert({
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "role": "assistant",
                    "content": full_content,
                })
                .execute()
            )

            # Auto-generate title from first message
            if not thread.data.get("title"):
                title = body.content[:50] + ("..." if len(body.content) > 50 else "")
                db.table("threads").update({"title": title}).eq("id", thread_id).execute()

            yield {
                "event": "done",
                "data": json.dumps({
                    "message_id": assistant_msg.data[0]["id"],
                    "content": full_content,
                }),
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())
