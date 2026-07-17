"""Regression coverage for PATCH /api/threads/{id} {persona} — PERS-01 / PERS-05.

The endpoint writes body.model_dump(exclude_unset=True) over a ThreadUpdate body
(model? + persona?) via a SINGLE scoped UPDATE (.eq id + user_id): a non-owned thread
matches 0 rows → 404, so the UPDATE itself is the IDOR gate (T-17-04) — there is no
separate ownership SELECT. exclude_unset keeps the no-clobber contract: a persona-only
PATCH never carries "model", a model-only PATCH never carries "persona".

Contract under test:
  - test_patch_sets_persona                    — PATCH {persona} → threads.update patch carries
                                                 persona, scoped by id AND user_id (IDOR gate).
  - test_patch_persona_only_does_not_clobber_model — a persona-only body's update patch does NOT
                                                 contain "model" (exclude_unset — Pattern 4 /
                                                 no-clobber).
  - test_patch_model_only_still_works          — regression: PATCH {model} → patch == {"model":...},
                                                 NO "persona" key (the model-pin path stays intact).
  - test_patch_persona_404_non_owned           — the scoped UPDATE matches 0 rows → 404 (still
                                                 scoped by id AND user_id, IDOR gate T-17-04).

Patches mirror test_thread_model_patch.py:
  - app.dependency_overrides[get_user_id] = lambda: "user-uuid"
  - patch("routers.threads.get_supabase", return_value=mock_db)
  - clear app.dependency_overrides in a finally.
"""
from unittest.mock import MagicMock, patch

_USER = "user-uuid"
_TID = "thread-123"


def _mock_db(owned: bool):
    """Fake supabase for the collapsed single-UPDATE mechanism. The
    update().eq().eq().execute() chain records the payload and returns the updated row
    (carries model + persona columns) when `owned`, else an empty list (0 rows → 404)."""
    db = MagicMock()
    updated_row = {
        "id": _TID, "user_id": _USER, "title": None, "model": None, "persona": None
    }
    (
        db.table.return_value.update.return_value.eq.return_value.eq.return_value
        .execute.return_value
    ) = MagicMock(data=[updated_row] if owned else [])
    return db


def test_patch_sets_persona() -> None:
    """PERS-01: PATCH /api/threads/{id} {persona:"general_assistant"} updates the thread's
    persona, scoped by both id AND user_id (ownership re-check, IDOR mitigation T-17-04)."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    db = _mock_db(owned=True)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.threads.get_supabase", return_value=db):
            resp = TestClient(app).patch(
                f"/api/threads/{_TID}", json={"persona": "general_assistant"}
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"PATCH failed: {resp.status_code} {resp.text}"
    update = db.table.return_value.update
    update.assert_called_once()
    patch_dict = update.call_args.args[0]
    assert "persona" in patch_dict, f"persona not written to the update patch: {patch_dict}"
    assert patch_dict["persona"] == "general_assistant", patch_dict
    # The update must be scoped by id AND user_id (ownership re-check).
    eq_chain = update.return_value.eq
    eq_calls = {(c.args[0], c.args[1]) for c in eq_chain.call_args_list} | {
        (c.args[0], c.args[1]) for c in eq_chain.return_value.eq.call_args_list
    }
    assert ("id", _TID) in eq_calls, eq_calls
    assert ("user_id", _USER) in eq_calls, eq_calls


def test_patch_persona_only_does_not_clobber_model() -> None:
    """PERS-05 / T-17-05 (no-clobber): a persona-only PATCH's update patch must NOT
    contain the key "model" — exclude_unset semantics keep the stored model pin intact.
    This is the test that FORCES the switch away from the hardcoded {"model": body.model}."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    db = _mock_db(owned=True)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.threads.get_supabase", return_value=db):
            resp = TestClient(app).patch(
                f"/api/threads/{_TID}", json={"persona": "general_assistant"}
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"PATCH failed: {resp.status_code} {resp.text}"
    update = db.table.return_value.update
    update.assert_called_once()
    patch_dict = update.call_args.args[0]
    assert "model" not in patch_dict, (
        f"persona-only PATCH clobbered the model pin: {patch_dict}"
    )


def test_patch_model_only_still_works() -> None:
    """Regression: PATCH {model:"x/y"} → the update patch is exactly {"model":"x/y"} and
    carries NO "persona" key — the model-pin path stays intact under exclude_unset."""
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
    patch_dict = update.call_args.args[0]
    assert patch_dict == {"model": "x/y"}, patch_dict
    assert "persona" not in patch_dict, f"model-only PATCH leaked a persona key: {patch_dict}"


def test_patch_persona_404_non_owned() -> None:
    """PERS-01 / T-17-04 (IDOR): PATCH {persona} on a thread the caller does not own →
    the single scoped UPDATE (.eq id + user_id) matches 0 rows → 404. The UPDATE is the
    ownership gate, so it IS issued (but scoped); another user's thread is never modified."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    db = _mock_db(owned=False)  # scoped UPDATE matches 0 rows

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.threads.get_supabase", return_value=db):
            resp = TestClient(app).patch(
                f"/api/threads/{_TID}", json={"persona": "general_assistant"}
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404, (
        f"expected 404 for non-owned thread, got {resp.status_code}: {resp.text}"
    )
    # The single scoped UPDATE IS the ownership gate — it must be scoped by id AND user_id.
    update = db.table.return_value.update
    update.assert_called_once()
    eq_chain = update.return_value.eq
    eq_calls = {(c.args[0], c.args[1]) for c in eq_chain.call_args_list} | {
        (c.args[0], c.args[1]) for c in eq_chain.return_value.eq.call_args_list
    }
    assert ("id", _TID) in eq_calls, eq_calls
    assert ("user_id", _USER) in eq_calls, eq_calls
