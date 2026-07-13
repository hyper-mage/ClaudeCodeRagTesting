from fastapi import APIRouter, Depends, HTTPException
from auth import get_user_id
from database import get_supabase
from models.schemas import ThreadCreate, ThreadResponse, ThreadWithMessages, MessageResponse, ThreadUpdate

router = APIRouter(prefix="/api/threads", tags=["threads"])


@router.get("", response_model=list[ThreadResponse])
async def list_threads(user_id: str = Depends(get_user_id)):
    db = get_supabase()
    result = (
        db.table("threads")
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data


@router.post("", response_model=ThreadResponse, status_code=201)
async def create_thread(body: ThreadCreate, user_id: str = Depends(get_user_id)):
    db = get_supabase()
    result = (
        db.table("threads")
        .insert({"user_id": user_id, "title": body.title})
        .execute()
    )
    return result.data[0]


@router.get("/{thread_id}", response_model=ThreadWithMessages)
async def get_thread(thread_id: str, user_id: str = Depends(get_user_id)):
    db = get_supabase()
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

    messages = (
        db.table("messages")
        .select("*")
        .eq("thread_id", thread_id)
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return {**thread.data, "messages": messages.data}


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: str, body: ThreadUpdate, user_id: str = Depends(get_user_id)
):
    """Partial-write the per-thread model AND/OR persona pins (MODEL-06 / PERS-01 / PERS-05).

    Re-checks ownership server-side (.eq id + user_id → 404 on a non-owned
    thread, IDOR mitigation T-13-IDOR / T-17-04) before writing. The update
    payload is an exclude_unset model_dump, so ONLY the keys the client
    actually sent are written: a persona-only PATCH cannot clobber the model pin
    and a model-only PATCH cannot clobber the persona (T-17-05, no-clobber). An
    EXPLICIT null is still a deliberate clear ({model: null} clears the pin back
    to the default tier, D-05/D-10) because exclude_unset keeps explicitly-set
    keys even when their value is None.
    """
    db = get_supabase()
    owned = (
        db.table("threads")
        .select("id")
        .eq("id", thread_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not owned.data:
        raise HTTPException(status_code=404, detail="Thread not found")

    patch = body.model_dump(exclude_unset=True)
    updated = (
        db.table("threads")
        .update(patch)
        .eq("id", thread_id)
        .eq("user_id", user_id)
        .execute()
    )
    # supabase-py returns the updated rows in .data; the row carries the new model/persona.
    return updated.data[0]


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(thread_id: str, user_id: str = Depends(get_user_id)):
    db = get_supabase()
    thread = (
        db.table("threads")
        .select("id")
        .eq("id", thread_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not thread.data:
        raise HTTPException(status_code=404, detail="Thread not found")

    db.table("threads").delete().eq("id", thread_id).execute()
