"""GET /api/threads/{id} exposes `usage` on every message (COST-01 / COST-04).

Wave 0 (Plan 14-01) — written BEFORE MessageResponse declares `usage`, so on first
run the assertion FAILS: FastAPI's response_model strips any field not declared on
MessageResponse even though the DB select('*') returns it (Pitfall 1). Goes GREEN
once Task 2 adds `usage: dict | None = None` to MessageResponse.

Mirrors the MagicMock `_table` side_effect style from test_usage_capture.py and the
TestClient + dependency_overrides pattern from test_keys_status.py.
"""
from unittest.mock import MagicMock, patch


_USER_ID = "11111111-1111-1111-1111-111111111111"


def _thread_db():
    """A MagicMock supabase client wired for threads.get_thread:

    - threads.select('*').eq().eq().maybe_single().execute() → a thread row
    - messages.select('*').eq().eq().order().execute() → rows, the assistant
      carrying a `usage` dict (cost + tokens).
    """
    db = MagicMock()

    def _table(name: str):
        tbl = MagicMock()
        if name == "threads":
            res = MagicMock()
            res.data = {"id": "t1", "user_id": _USER_ID, "title": "x", "model": None}
            tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = res
        elif name == "messages":
            res = MagicMock()
            res.data = [
                {
                    "id": "m1", "thread_id": "t1", "role": "user",
                    "content": "hi", "created_at": "2026-06-25T00:00:00+00:00",
                },
                {
                    "id": "m2", "thread_id": "t1", "role": "assistant",
                    "content": "hello", "created_at": "2026-06-25T00:00:01+00:00",
                    "usage": {"cost": 0.0021, "total_tokens": 1200},
                },
            ]
            tbl.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = res
        return tbl

    db.table.side_effect = _table
    return db


def test_get_thread_returns_usage() -> None:
    """The assistant message's `usage` (cost + tokens) survives the response_model
    serialization on GET /api/threads/{id} — the read-path fix that proves Pitfall 1
    (FastAPI strips undeclared fields) is closed."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    db = _thread_db()
    app.dependency_overrides[get_user_id] = lambda: _USER_ID
    try:
        with patch("routers.threads.get_supabase", return_value=db):
            resp = TestClient(app).get("/api/threads/t1")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    messages = resp.json()["messages"]
    # Once `usage` is declared on MessageResponse, every message carries the key
    # (None for the user row, the cost dict for the assistant row). Before the fix,
    # FastAPI strips the field entirely → this assertion fails (RED).
    for msg in messages:
        assert "usage" in msg, f"usage stripped from message {msg.get('id')}: {msg}"
    assistant = next(m for m in messages if m["role"] == "assistant")
    assert assistant["usage"] is not None
    assert assistant["usage"]["cost"] == 0.0021
    assert assistant["usage"]["total_tokens"] == 1200
