"""Wave 0 RED scaffold — persona RESOLVER + REGISTRY contract (Phase 17).

Pins PERS-03 (Expert default), PERS-06 (no cross-thread bleed), D-10 (unknown-id
fallback), the D-09 tier order (thread pin → user default → system default), and the
42P01 pre-migration tolerance of the user_preferences read.

Analog: test_key_model_resolution.py — the `_db_with_key_row` MagicMock chain and the
in-function import discipline so RED is a per-TEST import/assertion failure, never a
COLLECTION error. Every symbol under test (services.persona_service.*, routers.chat.
_resolve_persona / _safe_thread_persona / _safe_user_default_persona) is imported INSIDE
the test body: authored GREEN by plans 17-04 (registry/voice) and 17-06 (chat resolver).

Runs RED today: services.persona_service does not exist and routers.chat has no
_resolve_persona sibling yet.
"""
from unittest.mock import MagicMock


def _db_with_persona_row(default_persona: str | None = None, pref_raises: bool = False):
    """Fake supabase client for _resolve_persona / _safe_user_default_persona.

    - user_preferences read returns {"default_persona": <value>} (or None when
      `default_persona` is falsy), mirroring the maybe_single() .data shape.
    - When `pref_raises` is set, the read RAISES (simulating the absent P17
      column/table → Postgres 42P01 relation-does-not-exist) so the resolver's
      tolerant fall-through is exercised.

    The read is chained .table().select().eq().maybe_single().execute() → `.data`,
    identical to _db_with_key_row in test_key_model_resolution.py.
    """
    db = MagicMock()

    def _table(name: str):
        tbl = MagicMock()
        exec_result = MagicMock()
        if name == "user_preferences":
            if pref_raises:
                tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = (
                    RuntimeError('relation "user_preferences" does not exist (42P01)')
                )
            else:
                exec_result.data = (
                    {"default_persona": default_persona} if default_persona else None
                )
                tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
                    exec_result
                )
        else:
            exec_result.data = None
            tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
                exec_result
            )
        return tbl

    db.table.side_effect = _table
    return db


def test_registry_has_exactly_two_with_one_default():
    """D-05 / PERS-03: the persona registry ships EXACTLY two entries, EXACTLY one of
    which is the default, and the default id is board_game_expert."""
    from services.persona_service import PERSONAS, DEFAULT_PERSONA_ID

    assert len(PERSONAS) == 2
    assert sum(1 for p in PERSONAS if p["is_default"]) == 1
    assert DEFAULT_PERSONA_ID == "board_game_expert"
    assert [p["id"] for p in PERSONAS if p["is_default"]] == ["board_game_expert"]


def test_null_pin_and_null_default_resolves_to_expert():
    """PERS-03: no thread pin + no user default → the Board-Game Expert voice
    (the system default persona), never an empty/None voice."""
    from routers.chat import _resolve_persona
    from services.persona_service import get_persona_voice

    db = _db_with_persona_row(default_persona=None)
    voice = _resolve_persona(db, "user-1", None, object())

    assert voice == get_persona_voice("board_game_expert")


def test_thread_pin_wins_over_user_default():
    """D-09 tier order: a per-thread pin OVERRIDES the user-level default — a thread
    pinned to general_assistant resolves the general voice even though the user
    default is board_game_expert."""
    from routers.chat import _resolve_persona
    from services.persona_service import get_persona_voice

    db = _db_with_persona_row(default_persona="board_game_expert")
    voice = _resolve_persona(db, "user-1", {"persona": "general_assistant"}, object())

    assert voice == get_persona_voice("general_assistant")
    assert voice != get_persona_voice("board_game_expert")


def test_user_default_used_when_no_thread_pin():
    """D-09 tier order: with NO thread pin, the user-level default persona is used —
    a user default of general_assistant resolves the general voice."""
    from routers.chat import _resolve_persona
    from services.persona_service import get_persona_voice

    db = _db_with_persona_row(default_persona="general_assistant")
    voice = _resolve_persona(db, "user-1", None, object())

    assert voice == get_persona_voice("general_assistant")


def test_unknown_pinned_id_falls_back_to_default():
    """D-10 / Pitfall 5 (T-17-01): a crafted/stale/removed persona id resolves to the
    DEFAULT voice and NEVER raises — a pinned id absent from the registry is validated
    down to the system default before the voice lookup."""
    from routers.chat import _resolve_persona
    from services.persona_service import (
        DEFAULT_PERSONA_ID,
        get_persona_voice,
        resolve_persona_id,
    )

    db = _db_with_persona_row(default_persona=None)
    voice = _resolve_persona(db, "user-1", {"persona": "__nonsense__"}, object())

    assert voice == get_persona_voice("board_game_expert")
    # The validator collapses an unknown id to the default WITHOUT raising (D-10).
    assert resolve_persona_id("__nonsense__") == DEFAULT_PERSONA_ID


def test_no_cross_thread_bleed():
    """PERS-06 / Pitfall 4 (T-17-02): two back-to-back resolutions with DIFFERENT
    thread pins must return DIFFERENT voices — the resolver is not cached, so one
    thread's persona can never bleed into the next."""
    from routers.chat import _resolve_persona
    from services.persona_service import get_persona_voice

    db = _db_with_persona_row(default_persona=None)
    voice_a = _resolve_persona(db, "user-1", {"persona": "board_game_expert"}, object())
    voice_b = _resolve_persona(db, "user-1", {"persona": "general_assistant"}, object())

    assert voice_a == get_persona_voice("board_game_expert")
    assert voice_b == get_persona_voice("general_assistant")
    assert voice_a != voice_b


def test_user_preferences_absent_is_tolerated():
    """42P01 tolerance: when the user_preferences read RAISES (column/table absent
    pre-migration), the resolver swallows it and falls through to the Expert default
    voice — no crash on the not-yet-present P17 schema."""
    from routers.chat import _resolve_persona
    from services.persona_service import get_persona_voice

    db = _db_with_persona_row(pref_raises=True)
    voice = _resolve_persona(db, "user-1", None, object())

    assert voice == get_persona_voice("board_game_expert")
