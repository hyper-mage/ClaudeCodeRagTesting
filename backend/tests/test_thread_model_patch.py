"""Wave 0 (Plan 13-01) RED scaffolds for PATCH /api/threads/{id} — MODEL-06.

Written BEFORE the PATCH endpoint exists on routers.threads, so on first run these
FAIL with 404/405 (no route) — RED. They go GREEN once Plan 13-03 adds the PATCH
endpoint that re-checks ownership (.eq("id",tid).eq("user_id",uid)) before writing
the model column, and writes {model: None} EXPLICITLY on a null clear (D-05).

Contract under test:
  - test_patch_sets_model    — PATCH {model:"x/y"} → threads.update({"model":"x/y"})
                               scoped by .eq("id",tid).eq("user_id",uid) (IDOR re-check).
  - test_patch_null_clears   — PATCH {model:null} → update({"model": None}) EXPLICITLY,
                               not skipped (the clear-to-default path, D-05).
  - test_patch_404_non_owned — ownership re-check returns no row → 404.

Patches mirror test_models_api.py:
  - app.dependency_overrides[get_user_id] = lambda: "user-uuid"
  - patch("routers.threads.get_supabase", return_value=mock_db)
  - clear app.dependency_overrides in a finally.
"""
from unittest.mock import MagicMock, patch

_USER = "user-uuid"
_TID = "thread-123"


def _mock_db(owned: bool):
    """Fake supabase. The ownership re-check select().eq().eq().maybe_single().execute()
    returns a row when `owned`, else None. The update().eq().eq().execute() chain
    records the payload and returns the updated row."""
    db = MagicMock()
    owner_row = {"id": _TID, "user_id": _USER} if owned else None
    (
        db.table.return_value.select.return_value.eq.return_value.eq.return_value
        .maybe_single.return_value.execute.return_value
    ) = MagicMock(data=owner_row)
    (
        db.table.return_value.update.return_value.eq.return_value.eq.return_value
        .execute.return_value
    ) = MagicMock(
        data=[{"id": _TID, "user_id": _USER, "title": None, "model": None}]
    )
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
    """MODEL-06: PATCH on a thread the caller does not own → ownership re-check returns
    no row → 404 (never leak/modify another user's thread)."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    db = _mock_db(owned=False)  # ownership re-check finds no row

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.threads.get_supabase", return_value=db):
            resp = TestClient(app).patch(f"/api/threads/{_TID}", json={"model": "x/y"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404, f"expected 404 for non-owned thread, got {resp.status_code}: {resp.text}"
    # Must NOT have attempted to update a thread it does not own.
    db.table.return_value.update.assert_not_called()
