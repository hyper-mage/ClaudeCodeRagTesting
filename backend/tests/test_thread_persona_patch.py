"""Wave 0 (Plan 17-02) RED scaffolds for PATCH /api/threads/{id} {persona} — PERS-01 / PERS-05.

Clones test_thread_model_patch.py's _mock_db(owned) helper and patch targets. Written
BEFORE the PATCH endpoint accepts a persona field: today it hardcodes {"model": body.model}
(threads.py:81-89) against a ThreadModelUpdate body that has NO persona field, so a
persona-only PATCH is silently coerced to {"model": None}. These FAIL RED until 17-07
switches the endpoint to body.model_dump(exclude_unset=True) over a ThreadUpdate body
(model? + persona?), keeping the ownership re-check (.eq id + user_id) verbatim.

Contract under test:
  - test_patch_sets_persona                    — PATCH {persona} → threads.update patch carries
                                                 persona, scoped by id AND user_id (IDOR re-check).
  - test_patch_persona_only_does_not_clobber_model — a persona-only body's update patch does NOT
                                                 contain "model" (exclude_unset — Pattern 4 /
                                                 no-clobber). FORCES the switch off {"model": body.model}.
  - test_patch_model_only_still_works          — regression: PATCH {model} → patch == {"model":...},
                                                 NO "persona" key (the model-pin path stays intact).
  - test_patch_persona_404_non_owned           — ownership re-check finds no row → 404, update
                                                 NOT called (IDOR, T-17-04).

Patches mirror test_thread_model_patch.py:
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
    records the payload and returns the updated row (carries model + persona columns)."""
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
        data=[{"id": _TID, "user_id": _USER, "title": None, "model": None, "persona": None}]
    )
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
    ownership re-check returns no row → 404, and the update is NEVER attempted."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    db = _mock_db(owned=False)  # ownership re-check finds no row

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
    db.table.return_value.update.assert_not_called()
