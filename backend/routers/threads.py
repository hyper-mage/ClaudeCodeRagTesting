from fastapi import APIRouter, Depends, HTTPException
from auth import get_user_id
from database import get_supabase
from models.schemas import ThreadCreate, ThreadResponse, ThreadWithMessages, MessageResponse, ThreadUpdate

router = APIRouter(prefix="/api/threads", tags=["threads"])


# Every endpoint here is fully synchronous (no `await`), so they are plain `def`:
# FastAPI runs `def` path operations in its threadpool, giving real concurrency for
# the ChatPage mount fan-out (list + per-thread reads) instead of blocking the loop.
@router.get("", response_model=list[ThreadResponse])
def list_threads(user_id: str = Depends(get_user_id)):
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
def create_thread(body: ThreadCreate, user_id: str = Depends(get_user_id)):
    db = get_supabase()
    result = (
        db.table("threads")
        .insert({"user_id": user_id, "title": body.title})
        .execute()
    )
    return result.data[0]


@router.get("/{thread_id}", response_model=ThreadWithMessages)
def get_thread(thread_id: str, user_id: str = Depends(get_user_id)):
    db = get_supabase()
    # Single round-trip: embed the thread's messages via PostgREST resource embedding
    # (`*, messages(*)`), replacing the prior thread-then-messages two-query fan-out. The
    # thread is ownership-checked (.eq id + user_id); messages are already thread-scoped,
    # so the embedded array carries exactly the same rows the old second query returned.
    #
    # Do NOT use .maybe_single() here: combined with resource embedding it trips a
    # postgrest-py bug that raises APIError code 204 "Missing response" instead of
    # returning the row (regression from the 260717-j1d single-round-trip rewrite). A plain
    # list execute is the safe form — 0 rows → not owned/nonexistent → 404 (IDOR gate).
    result = (
        db.table("threads")
        .select("*, messages(*)")
        .eq("id", thread_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    row = result.data[0]
    # PostgREST embed order is not guaranteed without a foreign-table order arg (also
    # implicated in the 204 bug above), so sort the embedded messages asc by created_at in
    # Python to preserve the exact ThreadWithMessages contract (messages asc).
    row["messages"] = sorted(row.get("messages") or [], key=lambda m: m["created_at"])
    return row


@router.patch("/{thread_id}", response_model=ThreadResponse)
def update_thread(
    thread_id: str, body: ThreadUpdate, user_id: str = Depends(get_user_id)
):
    """Partial-write the per-thread model AND/OR persona pins (MODEL-06 / PERS-01 / PERS-05).

    Ownership is enforced by a SINGLE scoped UPDATE (.eq id + user_id): a non-owned
    thread matches 0 rows → 404, so the update itself is the IDOR gate (T-13-IDOR /
    T-17-04) — no separate ownership SELECT. The update payload is an exclude_unset
    model_dump, so ONLY the keys the client actually sent are written: a persona-only
    PATCH cannot clobber the model pin and a model-only PATCH cannot clobber the persona
    (T-17-05, no-clobber). An EXPLICIT null is still a deliberate clear ({model: null}
    clears the pin back to the default tier, D-05/D-10) because exclude_unset keeps
    explicitly-set keys even when their value is None.
    """
    db = get_supabase()
    patch = body.model_dump(exclude_unset=True)
    updated = (
        db.table("threads")
        .update(patch)
        .eq("id", thread_id)
        .eq("user_id", user_id)
        .execute()
    )
    # 0 rows updated → the thread is not owned / does not exist → 404 (IDOR gate).
    if not updated.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    # supabase-py returns the updated rows in .data; the row carries the new model/persona.
    return updated.data[0]


@router.delete("/{thread_id}", status_code=204)
def delete_thread(thread_id: str, user_id: str = Depends(get_user_id)):
    db = get_supabase()
    # Single scoped DELETE (.eq id + user_id — ADDS the user_id scope the old delete
    # lacked, strictly safer). PostgREST returns the deleted rows in .data; 0 rows →
    # not owned / nonexistent → 404 (IDOR gate). Success returns None (204, no body).
    result = (
        db.table("threads")
        .delete()
        .eq("id", thread_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    return None
