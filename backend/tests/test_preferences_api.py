"""Wave 0 (Plan 13-01) RED scaffolds for the preferences API — MODEL-05 + PREF-02.

Written BEFORE routers.preferences exists, so on first run these FAIL at the
`from main import app` → `routers.preferences` import (RED). They go GREEN once
Plan 13-03 ships the router (GET/PUT /api/preferences), the upsert that binds
user_id from the JWT (never the body), and main.py wiring.

Contract under test:
  - test_put_then_get_default_model     — PUT {default_model} upserts; GET returns it (MODEL-05).
  - test_get_defaults_for_new_user      — no row → GET returns {"default_model": None, "theme": "dark"}.
  - test_theme_persist_and_validate     — PUT {theme:"light"} persists; the upsert payload binds
                                          user_id from the dependency-override JWT, NEVER the body
                                          (IDOR / cross-user mitigation, T-13-02).

Patches mirror test_models_api.py exactly:
  - app.dependency_overrides[get_user_id] = lambda: "user-uuid"   (auth gate)
  - patch("routers.preferences.get_supabase", return_value=mock_db)
  - clear app.dependency_overrides in a finally.
"""
from unittest.mock import MagicMock, patch

_USER = "user-uuid"


def _mock_db_with_pref_row(row: dict | None):
    """Fake supabase whose user_preferences select().eq().maybe_single().execute()
    returns `row` (or None). The upsert chain returns the same shape so a PUT can
    read back the persisted row."""
    db = MagicMock()
    select_exec = (
        db.table.return_value.select.return_value.eq.return_value
        .maybe_single.return_value.execute
    )
    select_exec.return_value = MagicMock(data=row)
    db.table.return_value.upsert.return_value.execute.return_value = MagicMock(
        data=[row] if row else None
    )
    return db


def test_put_then_get_default_model() -> None:
    """MODEL-05: PUT {default_model:"x/y"} upserts the row; a subsequent GET returns it."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    stored = {"user_id": _USER, "default_model": "anthropic/claude-3.5-sonnet", "theme": "dark"}
    db = _mock_db_with_pref_row(stored)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.preferences.get_supabase", return_value=db):
            client = TestClient(app)
            put = client.put("/api/preferences", json={"default_model": "anthropic/claude-3.5-sonnet"})
            assert put.status_code == 200, f"PUT failed: {put.status_code} {put.text}"
            get = client.get("/api/preferences")
            assert get.status_code == 200, f"GET failed: {get.status_code} {get.text}"
            assert get.json()["default_model"] == "anthropic/claude-3.5-sonnet"
    finally:
        app.dependency_overrides.clear()


def test_get_defaults_for_new_user() -> None:
    """MODEL-05: a brand-new user with NO preferences row gets the resolved defaults
    {"default_model": None, "theme": "dark"} (maybe_single guard → endpoint fills theme)."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    db = _mock_db_with_pref_row(None)  # no row exists

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.preferences.get_supabase", return_value=db):
            resp = TestClient(app).get("/api/preferences")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"GET failed: {resp.status_code} {resp.text}"
    body = resp.json()
    # Phase 15 MODEL-08: favorite_models joined the wire shape (default []).
    assert body == {"default_model": None, "theme": "dark", "favorite_models": []}, body


def test_theme_persist_and_validate() -> None:
    """PREF-02: PUT {theme:"light"} persists; the upsert payload binds user_id from the
    dependency-override JWT, NEVER from the body (IDOR / cross-user mitigation, T-13-02)."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    stored = {"user_id": _USER, "default_model": None, "theme": "light"}
    db = _mock_db_with_pref_row(stored)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.preferences.get_supabase", return_value=db):
            # An attacker-supplied user_id in the body must be ignored.
            resp = TestClient(app).put(
                "/api/preferences",
                json={"theme": "light", "user_id": "attacker-uuid"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"PUT failed: {resp.status_code} {resp.text}"
    assert resp.json()["theme"] == "light"

    # The upsert payload MUST bind the JWT user_id, never the body's.
    upsert = db.table.return_value.upsert
    upsert.assert_called()
    payload = upsert.call_args.args[0]
    if isinstance(payload, list):
        payload = payload[0]
    assert payload["user_id"] == _USER, f"user_id not bound from JWT: {payload}"
    assert payload.get("user_id") != "attacker-uuid"
    assert payload["theme"] == "light"
    # exclude_unset upsert must NOT carry default_model when the client sent only theme.
    assert "default_model" not in payload, f"theme-only PUT clobbered default_model: {payload}"


# ----- Phase 15 MODEL-08 (D-05): favorite_models roundtrip + no-clobber -----
#
# favorite_models is a whole-array replace riding the existing partial-upsert
# (exclude_unset) mechanics. The regression pins run BOTH clobber directions
# (Pitfall 12): a favorites-only PUT must not carry theme/default_model, and a
# theme-only PUT must not carry favorite_models.

_FAVES = ["meta-llama/llama-3.3-70b-instruct:free", "anthropic/claude-3.5-sonnet"]


def _upsert_payload(db) -> dict:
    """The dict handed to user_preferences.upsert() in the PUT under test."""
    upsert = db.table.return_value.upsert
    upsert.assert_called()
    payload = upsert.call_args.args[0]
    if isinstance(payload, list):
        payload = payload[0]
    return payload


def test_preferences_get_returns_favorites_default_empty() -> None:
    """MODEL-08: a user with NO preferences row resolves favorite_models to []."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    db = _mock_db_with_pref_row(None)  # no row exists

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.preferences.get_supabase", return_value=db):
            resp = TestClient(app).get("/api/preferences")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"GET failed: {resp.status_code} {resp.text}"
    assert resp.json()["favorite_models"] == []


def test_preferences_get_returns_stored_favorites() -> None:
    """MODEL-08: a stored favorite_models array is echoed verbatim by GET."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    stored = {
        "user_id": _USER,
        "default_model": None,
        "theme": "dark",
        "favorite_models": _FAVES,
    }
    db = _mock_db_with_pref_row(stored)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.preferences.get_supabase", return_value=db):
            resp = TestClient(app).get("/api/preferences")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"GET failed: {resp.status_code} {resp.text}"
    assert resp.json()["favorite_models"] == _FAVES


def test_preferences_put_favorites_only_no_clobber() -> None:
    """Pitfall 12 (favorites→theme direction): PUT {favorite_models} upserts a
    payload carrying favorite_models + user_id + updated_at and NOTHING else —
    no theme, no default_model (those would clobber the stored row)."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    stored = {
        "user_id": _USER,
        "default_model": None,
        "theme": "dark",
        "favorite_models": _FAVES,
    }
    db = _mock_db_with_pref_row(stored)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.preferences.get_supabase", return_value=db):
            resp = TestClient(app).put(
                "/api/preferences", json={"favorite_models": _FAVES}
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"PUT failed: {resp.status_code} {resp.text}"
    payload = _upsert_payload(db)
    assert payload["favorite_models"] == _FAVES
    assert payload["user_id"] == _USER
    assert "updated_at" in payload
    assert "theme" not in payload, f"favorites-only PUT clobbered theme: {payload}"
    assert "default_model" not in payload, (
        f"favorites-only PUT clobbered default_model: {payload}"
    )


def test_preferences_put_theme_only_preserves_favorites() -> None:
    """Pitfall 12 (theme→favorites direction): a theme-only PUT's upsert payload
    must NOT carry favorite_models (exclude_unset keeps the stored array intact)."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    stored = {
        "user_id": _USER,
        "default_model": None,
        "theme": "light",
        "favorite_models": _FAVES,
    }
    db = _mock_db_with_pref_row(stored)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.preferences.get_supabase", return_value=db):
            resp = TestClient(app).put("/api/preferences", json={"theme": "light"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"PUT failed: {resp.status_code} {resp.text}"
    payload = _upsert_payload(db)
    assert "favorite_models" not in payload, (
        f"theme-only PUT clobbered favorite_models: {payload}"
    )


def test_preferences_put_echo_includes_favorites() -> None:
    """MODEL-08: the PUT echo (read-back response) carries favorite_models."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    stored = {
        "user_id": _USER,
        "default_model": None,
        "theme": "dark",
        "favorite_models": _FAVES,
    }
    db = _mock_db_with_pref_row(stored)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.preferences.get_supabase", return_value=db):
            resp = TestClient(app).put(
                "/api/preferences", json={"favorite_models": _FAVES}
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"PUT failed: {resp.status_code} {resp.text}"
    assert resp.json()["favorite_models"] == _FAVES, (
        f"PUT echo dropped favorite_models: {resp.json()}"
    )


# ----- Phase 17 PERS-04 (Wave 0 RED): default_persona roundtrip + no-clobber -----
#
# default_persona is a plain-TEXT user default riding the SAME partial-upsert
# (exclude_unset) mechanics as default_model/favorite_models. These clone the
# favorite_models block; they FAIL RED until 17-07 threads default_persona through
# the GET/PUT select strings + return dicts and adds it to PreferencesUpdate/Response.
# Every test name contains "persona" so `pytest -k persona` selects EXACTLY these four.


def test_preferences_get_returns_default_persona_none_for_new_user() -> None:
    """PERS-04: a user with NO preferences row resolves default_persona to None
    (the picker falls back to the system default when unset)."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    db = _mock_db_with_pref_row(None)  # no row exists

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.preferences.get_supabase", return_value=db):
            resp = TestClient(app).get("/api/preferences")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"GET failed: {resp.status_code} {resp.text}"
    body = resp.json()
    assert "default_persona" in body, f"new-user GET missing default_persona key: {body}"
    assert body["default_persona"] is None, body


def test_preferences_put_default_persona_roundtrip() -> None:
    """PERS-04: PUT {default_persona} upserts a payload carrying default_persona +
    user_id + updated_at; the read-back GET returns default_persona verbatim."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    stored = {
        "user_id": _USER,
        "default_model": None,
        "theme": "dark",
        "favorite_models": [],
        "default_persona": "general_assistant",
    }
    db = _mock_db_with_pref_row(stored)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.preferences.get_supabase", return_value=db):
            client = TestClient(app)
            put = client.put(
                "/api/preferences", json={"default_persona": "general_assistant"}
            )
            assert put.status_code == 200, f"PUT failed: {put.status_code} {put.text}"
            payload = _upsert_payload(db)
            assert "default_persona" in payload, (
                f"PUT did not persist default_persona: {payload}"
            )
            assert payload["default_persona"] == "general_assistant"
            assert payload["user_id"] == _USER
            assert "updated_at" in payload
            get = client.get("/api/preferences")
            assert get.status_code == 200, f"GET failed: {get.status_code} {get.text}"
            assert "default_persona" in get.json(), (
                f"GET read-back missing default_persona: {get.json()}"
            )
            assert get.json()["default_persona"] == "general_assistant"
    finally:
        app.dependency_overrides.clear()


def test_preferences_put_theme_only_preserves_default_persona() -> None:
    """Pitfall 12 (theme→persona direction): a theme-only PUT's upsert payload must
    NOT carry default_persona (exclude_unset keeps the stored persona default intact),
    mirroring test_preferences_put_theme_only_preserves_favorites."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    stored = {
        "user_id": _USER,
        "default_model": None,
        "theme": "light",
        "favorite_models": [],
        "default_persona": "general_assistant",
    }
    db = _mock_db_with_pref_row(stored)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.preferences.get_supabase", return_value=db):
            resp = TestClient(app).put("/api/preferences", json={"theme": "light"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"PUT failed: {resp.status_code} {resp.text}"
    payload = _upsert_payload(db)
    assert "default_persona" not in payload, (
        f"theme-only PUT clobbered default_persona: {payload}"
    )


def test_preferences_put_default_persona_only_no_clobber() -> None:
    """Pitfall 12 (persona→siblings direction): a default_persona-only PUT's upsert
    payload must NOT carry default_model or theme (those would clobber the stored row)."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    stored = {
        "user_id": _USER,
        "default_model": None,
        "theme": "dark",
        "favorite_models": [],
        "default_persona": "general_assistant",
    }
    db = _mock_db_with_pref_row(stored)

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        with patch("routers.preferences.get_supabase", return_value=db):
            resp = TestClient(app).put(
                "/api/preferences", json={"default_persona": "general_assistant"}
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"PUT failed: {resp.status_code} {resp.text}"
    payload = _upsert_payload(db)
    assert "default_model" not in payload, (
        f"persona-only PUT clobbered default_model: {payload}"
    )
    assert "theme" not in payload, f"persona-only PUT clobbered theme: {payload}"
