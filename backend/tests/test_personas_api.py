"""Wave 0 (Plan 17-02) RED scaffold for GET /api/personas — PERS-01 / D-07.

Written BEFORE routers.personas exists (and BEFORE it is wired into main.py), so on
first run these FAIL RED: the /api/personas route is not registered, so the GET returns
404 (or, if a partial router lands, an ImportError). They go GREEN once 17-06 ships the
personas router (Depends(get_user_id) + list[PersonaResponse]) and main.py includes it.

Contract under test (mirrors routers/models.py — auth-gated catalog GET, code constant):
  - test_get_personas_returns_catalog            — GET → 200; a list of length 2; each item
                                                    has EXACTLY {id,label,is_default} and NO
                                                    voice_block (A5 — prompt text stays
                                                    server-side, never shipped to the client).
  - test_exactly_one_default_and_expert_is_it     — exactly one item.is_default is True and its
                                                    id == "board_game_expert" (PERS-03 / D-05).
  - test_personas_requires_auth                   — with NO dependency override, GET is
                                                    auth-gated → 401/403 (D-07). get_user_id
                                                    raises HTTPException(401) on a missing
                                                    Authorization header (auth.py:21-22).

Patches mirror test_models_api.py exactly:
  - app.dependency_overrides[get_user_id] = lambda: "user-uuid"   (auth gate, A4)
  - clear app.dependency_overrides in a finally.
The catalog is a code constant (services.persona_service.list_personas), so NO DB patch
is required here — unlike test_models_api.py which patches routers.models.get_supabase.
"""

_USER = "user-uuid"


def test_get_personas_returns_catalog() -> None:
    """PERS-01 / D-07: GET /api/personas returns the curated 2-item catalog as
    [{id,label,is_default}]. The voice_block (prompt text) is NEVER in the wire shape
    (A5 — server-side only)."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        resp = TestClient(app).get("/api/personas")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert isinstance(body, list), f"catalog is not a list: {body!r}"
    assert len(body) == 2, f"expected exactly 2 personas, got {len(body)}: {body}"
    for item in body:
        # Exactly the public keys — no more, no less.
        assert set(item.keys()) == {"id", "label", "is_default"}, (
            f"unexpected persona keys (voice_block must never ship, A5): {item.keys()}"
        )
        # Belt-and-suspenders: the prompt text field is explicitly absent.
        assert "voice_block" not in item, f"voice_block leaked to the client: {item}"


def test_exactly_one_default_and_expert_is_it() -> None:
    """PERS-03 / D-05: exactly one persona is the default, and it is the board-game
    expert (id == 'board_game_expert')."""
    from fastapi.testclient import TestClient

    from auth import get_user_id
    from main import app

    app.dependency_overrides[get_user_id] = lambda: _USER
    try:
        resp = TestClient(app).get("/api/personas")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    defaults = [p for p in body if p.get("is_default") is True]
    assert len(defaults) == 1, f"expected exactly one default persona, got {defaults}"
    assert defaults[0]["id"] == "board_game_expert", (
        f"the default persona must be the board-game expert, got: {defaults[0]}"
    )


def test_personas_requires_auth() -> None:
    """D-07: GET /api/personas is auth-gated. With NO dependency override, the real
    get_user_id dependency runs against a request that carries no Authorization header
    and raises HTTPException(401) → the route is refused (401/403), never served."""
    from fastapi.testclient import TestClient

    from main import app

    # Deliberately NO app.dependency_overrides[get_user_id] — exercise the real gate.
    resp = TestClient(app).get("/api/personas")

    assert resp.status_code in (401, 403), (
        f"GET /api/personas must be auth-gated (401/403), got {resp.status_code}: {resp.text}"
    )
