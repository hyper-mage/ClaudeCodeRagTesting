"""Regression coverage for PATCH /api/threads/{id} — MODEL-06.

The endpoint enforces ownership with a SINGLE scoped UPDATE
(.eq("id",tid).eq("user_id",uid)): a non-owned thread matches 0 rows → 404, so the
UPDATE itself is the IDOR gate (there is no separate ownership SELECT). The write
payload is body.model_dump(exclude_unset=True), so {model: None} is written
EXPLICITLY on a null clear (D-05) and only sent keys are written.

Contract under test:
  - test_patch_sets_model    — PATCH {model:"x/y"} → threads.update({"model":"x/y"})
                               scoped by .eq("id",tid).eq("user_id",uid) (IDOR gate).
  - test_patch_null_clears   — PATCH {model:null} → update({"model": None}) EXPLICITLY,
                               not skipped (the clear-to-default path, D-05).
  - test_patch_404_non_owned — the scoped UPDATE matches 0 rows → 404 (still scoped
                               by id AND user_id).

Patches mirror test_models_api.py:
  - app.dependency_overrides[get_user_id] = lambda: "user-uuid"
  - patch("routers.threads.get_supabase", return_value=mock_db)
  - clear app.dependency_overrides in a finally.
"""
from unittest.mock import MagicMock, patch

_USER = "user-uuid"
_TID = "thread-123"


def _mock_db(owned: bool):
    """Fake supabase for the collapsed single-UPDATE mechanism. The
    update().eq().eq().execute() chain records the payload and returns the updated
    row when `owned`, else an empty list (0 rows updated → 404)."""
    db = MagicMock()
    updated_row = {"id": _TID, "user_id": _USER, "title": None, "model": None}
    (
        db.table.return_value.update.return_value.eq.return_value.eq.return_value
        .execute.return_value
    ) = MagicMock(data=[updated_row] if owned else [])
    return db


def test_patch_sets_model() -> None:
    """MODEL-06: PATCH /api/threads/{id} {model:"x/y"} updates the thread's model,
    scoped by both id AND user_id (ownership re-check, IDOR mitigation)."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    db = _mock_db(owned=True)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.threads.get_supabase", return_value=db):
            resp = TestClient(app).patch(f"/api/threads/{_TID}", json={"model": "x/y"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"PATCH failed: {resp.status_code} {resp.text}"
    update = db.table.return_value.update
    update.assert_called_once()
    assert update.call_args.args[0] == {"model": "x/y"}, update.call_args.args[0]
    # The update must be scoped by id AND user_id (ownership re-check).
    eq_chain = update.return_value.eq
    eq_calls = {(c.args[0], c.args[1]) for c in eq_chain.call_args_list} | {
        (c.args[0], c.args[1]) for c in eq_chain.return_value.eq.call_args_list
    }
    assert ("id", _TID) in eq_calls, eq_calls
    assert ("user_id", _USER) in eq_calls, eq_calls


def test_patch_null_clears() -> None:
    """MODEL-06 / D-05: PATCH {model:null} writes {"model": None} EXPLICITLY (the
    clear-to-default path) — null is a real value, not a skipped/exclude_unset field."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    db = _mock_db(owned=True)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.threads.get_supabase", return_value=db):
            resp = TestClient(app).patch(f"/api/threads/{_TID}", json={"model": None})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"PATCH failed: {resp.status_code} {resp.text}"
    update = db.table.return_value.update
    update.assert_called_once()
    assert update.call_args.args[0] == {"model": None}, (
        f"null clear was not written explicitly: {update.call_args.args[0]}"
    )


def test_patch_404_non_owned() -> None:
    """MODEL-06: PATCH on a thread the caller does not own → the single scoped UPDATE
    (.eq id + user_id) matches 0 rows → 404. The UPDATE is now the ownership gate, so it
    IS issued (but scoped) and returns no rows; another user's thread is never modified."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    db = _mock_db(owned=False)  # scoped UPDATE matches 0 rows

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.threads.get_supabase", return_value=db):
            resp = TestClient(app).patch(f"/api/threads/{_TID}", json={"model": "x/y"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404, f"expected 404 for non-owned thread, got {resp.status_code}: {resp.text}"
    # The single scoped UPDATE IS the ownership gate — it must be scoped by id AND user_id.
    update = db.table.return_value.update
    update.assert_called_once()
    eq_chain = update.return_value.eq
    eq_calls = {(c.args[0], c.args[1]) for c in eq_chain.call_args_list} | {
        (c.args[0], c.args[1]) for c in eq_chain.return_value.eq.call_args_list
    }
    assert ("id", _TID) in eq_calls, eq_calls
    assert ("user_id", _USER) in eq_calls, eq_calls
