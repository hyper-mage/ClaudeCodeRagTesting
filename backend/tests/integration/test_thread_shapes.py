"""Real-DB shape tests for GET/PATCH/DELETE /api/threads/{id} (quick task 260718-o4c).

These hit the REAL dev Supabase via a real PostgREST round-trip — `get_supabase` is NOT
patched here or in conftest. `test_get_thread_embeds_and_sorts_messages` is the canonical
guard: it 500s on the pre-hotfix `maybe_single()` + `*, messages(*)` embedding code and 200s
on the fixed code — that delta is the whole point of this suite.
"""
import uuid

import pytest

from tests.integration import requires_supabase

pytestmark = [pytest.mark.integration, requires_supabase]


def test_get_thread_embeds_and_sorts_messages(seeded_thread, client):
    tid = seeded_thread["tid"]

    resp = client.get(f"/api/threads/{tid}")

    # REGRESSION GUARD: on the pre-hotfix `maybe_single()` + `*, messages(*)` resource
    # embedding, postgrest-py raises APIError code 204 "Missing response" → the endpoint
    # 500s. On the fixed plain-list-execute code it returns 200. This assertion is the guard.
    assert resp.status_code == 200, resp.text

    body = resp.json()
    messages = body["messages"]
    # Both inserted messages come back via the REAL embedded `messages(*)` array.
    assert len(messages) == 2
    contents = [m["content"] for m in messages]
    assert set(contents) == {"first", "second"}
    # Asc order by created_at is proven end-to-end: the "second" (later) row was INSERTED
    # FIRST in the fixture, so a naive/unsorted return would put it at index 0. get_thread's
    # Python asc-sort must place "first" (earlier created_at) at index 0.
    assert messages[0]["content"] == seeded_thread["early_content"]  # "first"
    assert messages[1]["content"] == seeded_thread["late_content"]   # "second"


def test_patch_thread_persists_and_no_clobber(seeded_thread, client):
    tid = seeded_thread["tid"]

    # Model-only PATCH must persist model and NOT touch persona (exclude_unset no-clobber).
    resp = client.patch(f"/api/threads/{tid}", json={"model": "anthropic/claude-sonnet-4.5"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["model"] == "anthropic/claude-sonnet-4.5"
    assert body["persona"] is None  # model-only PATCH did not clobber persona

    # Reload proves it persisted to the real row (not just echoed).
    reget = client.get(f"/api/threads/{tid}")
    assert reget.status_code == 200, reget.text
    assert reget.json()["model"] == "anthropic/claude-sonnet-4.5"

    # Explicit null is a deliberate clear (D-05), persona still untouched.
    clear = client.patch(f"/api/threads/{tid}", json={"model": None})
    assert clear.status_code == 200, clear.text
    cleared = clear.json()
    assert cleared["model"] is None
    assert cleared["persona"] is None


def test_delete_thread_removes_row_and_cascades(seeded_thread, client, db):
    tid = seeded_thread["tid"]

    resp = client.delete(f"/api/threads/{tid}")
    assert resp.status_code == 204

    # Row is actually gone → 404 on re-GET.
    assert client.get(f"/api/threads/{tid}").status_code == 404

    # ON DELETE CASCADE FK: the thread's messages are gone too (real DB check).
    remaining = db.table("messages").select("id").eq("thread_id", tid).execute()
    assert remaining.data == []
    # Fixture teardown is idempotent, so the already-deleted thread cleans up without error.


def test_delete_nonexistent_thread_404(client):
    # A random unseeded id owned by nobody → 404 (IDOR gate).
    resp = client.delete(f"/api/threads/{str(uuid.uuid4())}")
    assert resp.status_code == 404
