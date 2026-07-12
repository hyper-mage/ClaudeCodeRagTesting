# Phase 17: Agent Personas - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-12
**Phase:** 17-agent-personas
**Areas discussed:** Prompt composition, Persona catalog, General Assistant scope, Persona storage, UI attribution

---

## Prompt composition

| Option | Description | Selected |
|--------|-------------|----------|
| Base + voice overlay | Extract operational rules into a shared base always applied; each persona contributes a short voice block. General Assistant keeps tool behavior automatically; rules maintained in one place. | ✓ |
| Full prompt per persona | Each persona is a complete standalone prompt. Simplest to wire, but operational rules get duplicated; General Assistant must re-state citation/routing/error rules or lose them. | |
| You decide | Planner picks the cleanest seam as long as General Assistant provably retains full tool behavior. | |

**User's choice:** Base + voice overlay
**Notes:** Surfaced a refinement — the current `system_prompt`'s "prefer the KB for game rules" line is Board-Game Expert *voice*, not operational base, so it moves into the Expert voice block (CONTEXT D-03). Base keeps only persona-agnostic rules: citation format, tool-error handling, markdown tables, `analyze_document`-by-name (D-02). `TOOL_SELECTION_GUIDE` still appended for all personas (D-04).

---

## Persona catalog

| Option | Description | Selected |
|--------|-------------|----------|
| Exactly 2 | Board-Game Expert (default) + General Assistant. Smallest surface; satisfies PERS-02/03 exactly. More personas addable later as pure registry data. | ✓ |
| Curated set of 3-4 | The 2 required plus 1-2 more (e.g. Rules Referee, Game Recommender). More value, more prompt authoring + picker testing. | |
| You decide | Start with 2; add a third as data if obvious during planning. | |

**User's choice:** Exactly 2
**Notes:** Adding more later is pure registry data, no new code (D-05).

---

## General Assistant scope

| Option | Description | Selected |
|--------|-------------|----------|
| Truly general, tools on | Plain general-assistant voice, no board-game framing, no KB-first bias. All tools callable; operational base still governs cite/error handling. Matches "behaves like a vanilla model." | ✓ |
| Board-game-aware, casual | Keeps KB-first bias, lighter tone. Less contrast with the Expert — arguably not a distinct persona. | |
| You decide | Planner picks, keeping General Assistant non-board-game-specialized with all tools available. | |

**User's choice:** Truly general, tools on
**Notes:** Confirms the D-03 split — KB-first source bias belongs to Expert voice, not the base, so General Assistant sheds it while keeping all tools (D-06).

---

## Persona storage

| Option | Description | Selected |
|--------|-------------|----------|
| Backend registry + endpoint | Python constant (id → {label, voice_block, is_default}) served via `GET /api/personas`. No catalog migration; prompts version with code. Pin columns still DB. | ✓ |
| DB table + migration | `personas` table seeded by migration (mirrors model_cache). Queryable but heavier; prompt edits become data migrations. Overkill for 2 non-editable personas. | |
| Backend registry, hardcoded picker | Same registry, FE hardcodes the list. Fewer parts now; FE/BE drift risk, needs a pin validation guard. | |

**User's choice:** Backend registry + endpoint
**Notes:** Picker fetches from `/api/personas` to avoid FE/BE drift (D-07). Pin columns (`threads.persona`, `user_preferences.default_persona`) remain DB (D-08).

---

## UI attribution (per-message persona badge)

| Option | Description | Selected |
|--------|-------------|----------|
| Picker-only, no badge | Chat picker shows the thread's current persona; no per-message label, no `messages` schema change. Consistent with the model pin (no per-message model badge). | ✓ |
| Badge on each bubble | Persist persona per assistant message + render a badge. More transparent on mid-thread switches, but needs a messages column + backfill + UI. | |
| You decide | Planner's call; default to picker-only unless a message-level column is warranted. | |

**User's choice:** Picker-only, no badge
**Notes:** Matches how per-thread model works today (D-12).

---

## Claude's Discretion

- Exact voice-block wording per persona (Expert must encode D-03's KB-first bias; General Assistant must read as non-board-game-specialized per D-06).
- Precise refactor seam for splitting `settings.system_prompt` into base + Expert voice (e.g. a `PERSONA_BASE_PROMPT` constant + `voice_block` per registry entry, composed in `stream_chat_completion`).
- Whether a `body.persona` per-message override param is added now or left as a future seam.
- Persona picker component structure/placement (reuse vs. adapt `ModelSelector`).

## Deferred Ideas

- User-editable custom persona prompts — PERS-F1, future milestone.
- Per-persona tool allowlists — PERS-F2, future milestone.
- Curated set of 3-4 personas — deferred; ship exactly 2 now, addable later as data.
- Per-message persona badge on assistant bubbles — deferred; picker-only for v1.3.
- `body.persona` per-message override — optional seam; per-thread pin is the primary path.
