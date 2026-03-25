import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from auth import get_user_id

logger = logging.getLogger(__name__)
from database import get_supabase
from models.schemas import MessageCreate
from services.llm_service import stream_chat_completion

try:
    from langsmith import traceable
except ImportError:
    def traceable(func=None, **kwargs):
        if func:
            return func
        return lambda f: f

router = APIRouter(prefix="/api/threads", tags=["chat"])


RETRIEVAL_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Search the user's uploaded documents for relevant information. "
            "Optionally filter by document_type or topic to narrow results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "document_type": {
                    "type": "string",
                    "enum": [
                        "technical_documentation",
                        "meeting_notes",
                        "research_paper",
                        "tutorial",
                        "email",
                        "general",
                    ],
                    "description": "Filter by document type, e.g. 'tutorial' or 'meeting_notes'",
                },
                "topic": {
                    "type": "string",
                    "description": "Filter by document topic",
                },
            },
            "required": ["query"],
        },
    },
}


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
    db.table("messages").insert({
        "thread_id": thread_id,
        "user_id": user_id,
        "role": "user",
        "content": body.content,
    }).execute()

    # Load all messages for this thread
    history = (
        db.table("messages")
        .select("role, content")
        .eq("thread_id", thread_id)
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    messages = [{"role": m["role"], "content": m["content"]} for m in history.data]

    async def event_generator():
        full_content = ""
        try:
            # Check if user has any documents for retrieval
            doc_check = (
                db.table("documents")
                .select("id")
                .eq("user_id", user_id)
                .eq("status", "completed")
                .limit(1)
                .execute()
            )
            tools = [RETRIEVAL_TOOL] if doc_check.data else None

            current_messages = list(messages)

            while True:
                tool_call_happened = False

                for event in stream_chat_completion(current_messages, tools=tools):
                    if event["type"] == "text_delta":
                        full_content += event["text"]
                        yield {
                            "event": "content_delta",
                            "data": json.dumps({"text": event["text"]}),
                        }
                    elif event["type"] == "tool_call":
                        tool_call_happened = True
                        # Execute tool calls
                        from services.retrieval_service import search_documents

                        # Add assistant message with tool calls
                        current_messages.append({
                            "role": "assistant",
                            "tool_calls": event["tool_calls"],
                        })

                        for tc in event["tool_calls"]:
                            fn_name = tc["function"]["name"]
                            fn_args = json.loads(tc["function"]["arguments"])

                            if fn_name == "search_documents":
                                # Build metadata filter from optional params
                                metadata_filter = {}
                                if "document_type" in fn_args:
                                    metadata_filter["document_type"] = fn_args["document_type"]
                                if "topic" in fn_args:
                                    metadata_filter["topic"] = fn_args["topic"]
                                try:
                                    results = search_documents(
                                        user_id=user_id,
                                        query=fn_args["query"],
                                        metadata_filter=metadata_filter or None,
                                    )
                                    tool_result = json.dumps(results)
                                except Exception as e:
                                    logger.error(f"search_documents failed: {e}", exc_info=True)
                                    tool_result = json.dumps({"error": str(e)})
                            else:
                                tool_result = json.dumps({"error": f"Unknown tool: {fn_name}"})

                            current_messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": tool_result,
                            })

                if not tool_call_happened:
                    break

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
