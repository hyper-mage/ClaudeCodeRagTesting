"""Phase 17 — agent-persona registry + resolution helpers (PERS-02/03, D-05/D-06/D-07/D-10).

The persona catalog is a CODE constant, mirroring how `settings.system_prompt` and
`TOOL_SELECTION_GUIDE` live in code (D-07) — NO DB, NO cache, NO seed/migration. Both the
chat resolver (`routers.chat`) and the catalog endpoint (`routers.personas`) import this
module; splitting it out of `chat.py` keeps the endpoint decoupled from the chat router
(mirrors the `models.py` ↔ `model_catalog_service.py` split).

Each persona contributes only a short VOICE block; the persona-agnostic operational rules
(citation format, tool-error handling, markdown tables, analyze_document) live in
`settings.system_prompt` and are composed in `llm_service.stream_chat_completion` (voice
FIRST, then base, then tool_guide — D-01/D-02/D-04). The KB-first source bias is Expert
VOICE, not operational base (D-03), so it lives here on the Board-Game Expert entry only.

Security posture (T-17-09/T-17-10): the voice_block strings are the ONLY persona text that
ever reaches the LLM system message. `resolve_persona_id` validates any pinned id back to a
registry entry (D-10), so no user-controlled string can be injected as a persona voice, and
`list_personas` withholds voice_block from the public `GET /api/personas` catalog (A5).
"""

DEFAULT_PERSONA_ID = "board_game_expert"

# Exactly 2 personas ship in v1.3 (D-05). Board-Game Expert is the default (PERS-03) and
# carries the KB-first bias (D-03); General Assistant is board-game-agnostic (D-06).
PERSONAS: list[dict] = [
    {
        "id": "board_game_expert",
        "label": "Board-Game Expert",
        "is_default": True,
        "voice_block": (
            "You are a board-game expert with access to tools. Answer questions clearly and "
            "concisely. Prefer the knowledge base for game rules and mechanics; use web_search "
            "only for current or external facts the knowledge base cannot answer (prices, "
            "availability, upcoming expansions, BGG rankings, designer/publisher news)."
        ),
    },
    {
        "id": "general_assistant",
        "label": "General Assistant",
        "is_default": False,
        "voice_block": (
            "You are a helpful, general-purpose assistant with access to tools. Answer questions "
            "clearly and concisely across any topic. Use the tools available when they help, but "
            "do not assume the user's question is about board games."
        ),
    },
]


def list_personas() -> list[dict]:
    """Public catalog for GET /api/personas — id/label/is_default ONLY (never voice_block, A5)."""
    return [
        {"id": p["id"], "label": p["label"], "is_default": p["is_default"]}
        for p in PERSONAS
    ]


def resolve_persona_id(pinned: str | None) -> str:
    """D-10: a pin that maps to a registry entry wins; anything else → the system default.

    Never raises — a crafted/stale/removed id collapses to DEFAULT_PERSONA_ID so no
    user-controlled string can reach the persona voice lookup (T-17-09).
    """
    ids = {p["id"] for p in PERSONAS}
    return pinned if pinned in ids else DEFAULT_PERSONA_ID


def get_persona_voice(persona_id: str) -> str:
    """Return the voice_block for `persona_id`, falling back to the default on any miss."""
    by_id = {p["id"]: p for p in PERSONAS}
    return by_id.get(persona_id, by_id[DEFAULT_PERSONA_ID])["voice_block"]
