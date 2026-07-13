"""Wave 0 RED scaffold — base + voice PROMPT-COMPOSITION contract (Phase 17).

Pins the D-01/D-02/D-03/D-04 split and PERS-02 tools-independence:
  - the persona VOICE leads, then the operational BASE, then the tool_guide (Pitfall 2)
  - General Assistant carries NO board-game framing / NO KB-first bias (PERS-02/D-06)
  - the Expert voice carries the KB-first bias (D-03)
  - the base operational rules (citation + analyze_document) apply to EVERY persona (D-02)
  - persona changes ONLY the system message, NEVER the tools list (PERS-02/D-04, T-17-03)

The composition seam is services.llm_service.stream_chat_completion, which will gain a
`persona_voice` kwarg (plan 17-04). The generator yields the FINAL composed prompt as its
first {"type": "system_content"} event BEFORE any network call, so we drive it only far
enough to read that event and patch get_llm_client so no client is ever built.

In-function imports (get_persona_voice from services.persona_service; the persona_voice
kwarg on stream_chat_completion) keep RED a per-TEST failure, not a collection error. Runs
RED today: services.persona_service does not exist and persona_voice is not a kwarg yet.
"""
from unittest.mock import MagicMock, patch


def _drive(monkeypatch, persona_voice, tool_guide=None, tools=None, full=False):
    """Compose a turn via stream_chat_completion and return (system_content, create_kwargs).

    - get_llm_client is patched so NO OpenAI client / network call happens.
    - get_settings is patched to a fresh env-isolated config.Settings() (SYSTEM_PROMPT
      removed) so a local .env override cannot mask the shipped operational base — mirrors
      test_web_search::test_system_prompt_citation_guidance.
    - full=False reads ONLY the first event (system_content, yielded before create());
      full=True drains the whole generator so client.chat.completions.create() is invoked
      and its kwargs (incl. `tools`) are captured.
    """
    import config
    from services import llm_service

    monkeypatch.delenv("SYSTEM_PROMPT", raising=False)
    base_settings = config.Settings()

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = iter([])  # empty stream drains clean

    with patch.object(llm_service, "get_llm_client", return_value=fake_client), \
         patch.object(llm_service, "get_settings", return_value=base_settings):
        gen = llm_service.stream_chat_completion(
            [{"role": "user", "content": "hi"}],
            tools=tools,
            tool_guide=tool_guide,
            persona_voice=persona_voice,
        )
        first = next(gen)
        if full:
            for _ in gen:
                pass
        else:
            gen.close()

    assert first["type"] == "system_content"
    call = fake_client.chat.completions.create.call_args
    return first["content"], (call.kwargs if call is not None else None)


def test_general_assistant_prompt_has_no_board_game_framing(monkeypatch):
    """PERS-02 / D-06: the General Assistant composed prompt contains the general voice
    but NO board-game-expert framing and NO KB-first bias — a vanilla assistant."""
    from services.persona_service import get_persona_voice

    voice = get_persona_voice("general_assistant")
    content, _ = _drive(monkeypatch, voice)

    assert voice in content
    assert "board-game expert" not in content.lower()
    assert "prefer the knowledge base" not in content.lower()


def test_expert_prompt_carries_kb_first_bias(monkeypatch):
    """D-03: the Board-Game Expert voice carries the KB-first bias ("Prefer the knowledge
    base") — the bias moved OUT of the operational base INTO the Expert voice_block."""
    from services.persona_service import get_persona_voice

    voice = get_persona_voice("board_game_expert")
    content, _ = _drive(monkeypatch, voice)

    assert "prefer the knowledge base" in content.lower()


def test_base_operational_rules_present_for_both_personas(monkeypatch):
    """D-02: the persona-agnostic operational base (citation "Sources:" guidance +
    analyze_document guidance) is present for EVERY persona, not just the Expert."""
    from services.persona_service import get_persona_voice

    for persona_id in ("board_game_expert", "general_assistant"):
        content, _ = _drive(monkeypatch, get_persona_voice(persona_id))
        assert "Sources:" in content, persona_id
        assert "analyze_document" in content, persona_id


def test_voice_leads_then_base(monkeypatch):
    """Pitfall 2: the persona voice is composed FIRST (exactly one "You are…" opener),
    so the voice substring appears BEFORE the base "Sources:" citation guidance."""
    from services.persona_service import get_persona_voice

    voice = get_persona_voice("board_game_expert")
    content, _ = _drive(monkeypatch, voice)

    assert voice in content
    assert content.find(voice) < content.find("Sources:")


def test_tools_are_persona_independent(monkeypatch):
    """PERS-02 / D-04 (T-17-03): switching persona changes ONLY the system message —
    the `tools` list handed to the model is IDENTICAL across personas. No tool is ever
    gated by persona; the General Assistant keeps full tool access."""
    from services.persona_service import get_persona_voice

    tools = [{"type": "function", "function": {"name": "kb_ls"}}]

    content_expert, kw_expert = _drive(
        monkeypatch, get_persona_voice("board_game_expert"), tools=tools, full=True
    )
    content_general, kw_general = _drive(
        monkeypatch, get_persona_voice("general_assistant"), tools=tools, full=True
    )

    # The system message DOES change with persona ...
    assert content_expert != content_general
    # ... but the tools list is passed through UNCHANGED for every persona.
    assert kw_expert["tools"] == kw_general["tools"] == tools
