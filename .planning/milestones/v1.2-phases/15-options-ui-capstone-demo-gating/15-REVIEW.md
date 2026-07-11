---
phase: 15-options-ui-capstone-demo-gating
reviewed: 2026-07-07T19:53:57Z
depth: standard
files_reviewed: 27
files_reviewed_list:
  - backend/models/schemas.py
  - backend/routers/chat.py
  - backend/routers/keys.py
  - backend/routers/preferences.py
  - backend/tests/test_key_model_resolution.py
  - backend/tests/test_keys_status.py
  - backend/tests/test_preferences_api.py
  - frontend/src/components/ChatContainer.test.tsx
  - frontend/src/components/ChatContainer.tsx
  - frontend/src/components/ConfirmDialog.tsx
  - frontend/src/components/DefaultModelSelector.test.tsx
  - frontend/src/components/DefaultModelSelector.tsx
  - frontend/src/components/ErrorMessageBubble.tsx
  - frontend/src/components/ModelSelector.test.tsx
  - frontend/src/components/ModelSelector.tsx
  - frontend/src/hooks/useChat.test.tsx
  - frontend/src/hooks/useChat.ts
  - frontend/src/hooks/useKeyGate.test.tsx
  - frontend/src/hooks/useKeyGate.tsx
  - frontend/src/hooks/useKeyStatus.ts
  - frontend/src/lib/fuzzy.test.ts
  - frontend/src/lib/fuzzy.ts
  - frontend/src/pages/ChatPage.tsx
  - frontend/src/pages/OAuthCallbackPage.test.tsx
  - frontend/src/pages/OAuthCallbackPage.tsx
  - frontend/src/pages/SettingsPage.tsx
  - supabase/migrations/20240301000033_add_favorite_models.sql
findings:
  critical: 2
  warning: 4
  info: 6
  total: 12
status: issues_found
---

# Phase 15: Code Review Report

**Reviewed:** 2026-07-07T19:53:57Z
**Depth:** standard
**Files Reviewed:** 27
**Status:** issues_found

## Summary

Reviewed the Phase 15 key-gated model selection surface: backend demo resolution
(`_demo_model_for` free-guard + `use_demo` override in `chat.py`), the
`demo_enabled` flag on `/api/keys/status`, `favorite_models` on the preferences
API + migration, and the frontend picker/gate/OAuth-resume/demo-banner stack.

The named security seams mostly hold: the `use_demo` override is gated on
`demo_fallback_enabled` in the same condition BEFORE the user-key branch
(chat.py:212), the free-guard requires `is_free is True` (unknown ≠ free,
chat.py:170), `demo_enabled` is set explicitly in both `/status` branches
(keys.py:101,106), the sessionStorage stash carries only
`{kind, modelId, threadId?, returnTo}` (no secret material, useKeyGate.tsx:100-108),
and the OAuth `returnTo` is allowlisted and applied via `navigate()`
(OAuthCallbackPage.tsx:22,111-114). Test coverage on those seams is strong.

However, two blockers were found by tracing the resolution path end-to-end:
the pre-existing deprecated-pin fallback in `send_message` overrides the
already-free-guarded demo model with an unguarded (potentially paid) default —
running a paid model on the OWNER key in demo mode — and the rewritten
ModelSelector renders a permanently empty panel when the `models` prop arrives
after mount (the common Settings-page timing).

## Critical Issues

### CR-01: Deprecated-pin fallback bypasses the D-03 demo free-guard — owner-key spend on a paid model

**File:** `backend/routers/chat.py:856-890` (interaction with `_resolve_key_and_model`, chat.py:212-247)
**Issue:** `_resolve_key_and_model` correctly free-guards the model on both demo
branches via `_demo_model_for` (picked model runs only when
`model_cache.is_free is True`, else the pinned `settings.demo_fallback_model`).
But the deprecated-pin fallback block that runs AFTER resolution overrides the
turn's model unconditionally:

```python
if cached_ids and thread_model not in cached_ids:
    default_model = (
        _safe_user_default_model(db, user_id)
        or settings.llm_model
    )
    ...
    # OVERRIDE the resolved model for THIS turn (fallback).
    model = default_model
```

This override has no `mode` check and no free-guard. Reachable path:
keyless user (or connected user clicking [Use demo]) + `DEMO_FALLBACK_ENABLED=true`
+ a thread pinned to a model that has dropped out of a non-empty `model_cache`.
The resolver returns `(owner_key, demo_fallback_model, "demo", False)` — then this
block replaces `model` with `user_preferences.default_model` or `settings.llm_model`,
either of which can be a PAID model. The turn then runs that paid model on the
OWNER key, defeating exactly the invariant `_demo_model_for` exists to enforce
(SEC-03 / D-03 — the only remaining backstop is the provider-side $0.10 guardrail).
The block predates this phase, but this phase introduced the free-guard it silently
bypasses, and none of the new `test_key_model_resolution.py` cases cover the
deprecated-pin + demo interaction.
**Fix:**
```python
if cached_ids and thread_model not in cached_ids:
    default_model = (
        _safe_user_default_model(db, user_id)
        or settings.llm_model
    )
    if mode == "demo":
        # Re-apply the D-03 free-guard: a demo turn must never run an
        # unguarded default on the owner key.
        default_model = _demo_model_for(db, default_model, settings)
    ...
    model = default_model
```
Add a regression test: demo mode + deprecated thread pin + paid user default →
model resolves to `settings.demo_fallback_model`, never the paid default.

### CR-02: ModelSelector opens to a permanently empty panel when `models` prop arrives after mount

**File:** `frontend/src/components/ModelSelector.tsx:122-126, 201-212, 414-436`
**Issue:** `state` is initialized once from the mount-time prop
(`useState<LoadState>(suppliedModels ? 'loaded' : 'idle')`). When the parent's
async catalog fetch resolves AFTER ModelSelector mounts (SettingsPage always
mounts `DefaultModelSelector` immediately while `/api/models` is still in
flight; ChatPage does the same if a thread is selected before the fetch lands),
`suppliedModels` becomes defined but `state` stays `'idle'`. On open,
`openMenu` calls `loadModels()`, which early-returns:

```ts
const loadModels = useCallback(async () => {
  if (suppliedModels) return // caller-supplied non-empty list — never fetch
  setState('loading')
  ...
```

`state` never leaves `'idle'`, and every rendered block below the search row is
gated on `state === 'loading' | 'error' | 'loaded'` — so the open panel shows
ONLY the search input: no options, no loading text, no error, no empty-state.
The picker is inoperable until remount. The pattern predates this phase, but
the component was rewritten wholesale here and all tests either pass `models`
at mount (state seeds `'loaded'`) or omit it entirely (lazy fetch works), so
the late-arrival path — the common real-world timing on the Settings page —
is both broken and untested.
**Fix:** Treat a supplied catalog as authoritative regardless of fetch state,
e.g. derive the effective state at render:
```ts
const effectiveState: LoadState = suppliedModels ? 'loaded' : state
```
and gate the panel blocks on `effectiveState` (or add
`useEffect(() => { if (suppliedModels) setState('loaded') }, [suppliedModels])`).
Add a test that renders with `models={undefined}`, rerenders with a non-empty
catalog, opens, and asserts the option rows render.

## Warnings

### WR-01: `PUT /api/preferences {"favorite_models": null}` causes an unhandled 500 (NOT NULL violation)

**File:** `backend/routers/preferences.py:75-80`, `backend/models/schemas.py:70`, `supabase/migrations/20240301000033_add_favorite_models.sql:14`
**Issue:** `favorite_models: list[str] | None = None` accepts an explicit JSON
`null`, and `model_dump(exclude_unset=True)` INCLUDES explicitly-set nulls. The
upsert then writes `favorite_models = NULL` into a column declared
`TEXT[] NOT NULL DEFAULT '{}'` → Postgres 23502 → supabase-py `APIError` →
uncaught → HTTP 500. Any authenticated client can trigger this with a one-line
body. (`{"theme": null}` hits the same NOT NULL trap on the pre-existing theme
column; `default_model: null` is fine — that column is nullable and null is the
legitimate "clear" value.)
**Fix:** Strip the null-invalid keys from the patch before the upsert (keeping
`default_model: null` intact as the deliberate clear):
```python
patch = body.model_dump(exclude_unset=True)
for k in ("favorite_models", "theme"):
    if k in patch and patch[k] is None:
        patch.pop(k)
```
or reject explicit nulls with a Pydantic `field_validator` (422 instead of 500).

### WR-02: `lastTurnWasDemo` latch never clears on a subsequent non-demo turn — stale "Demo mode" banner

**File:** `frontend/src/hooks/useChat.ts:268` (render condition ChatContainer.tsx:70)
**Issue:** The done-event handler only ever sets the latch true
(`if (parsed.mode === 'demo') setLastTurnWasDemo(true)`), and the only reset is
a thread switch. Sequence: user hits a 403 → clicks [Use demo] (demo turn,
latch true) → reconnects/fixes their key → next turn on the SAME thread runs on
their own key — yet the banner keeps asserting "Demo mode — a free model is in
use" until they switch threads. The banner copy is now factually wrong while
the user is being billed on their own key. `useChat.test.tsx` Demo 1-3 cover
set-and-reset-on-switch but not the demo→user transition within a thread.
**Fix:** Make the done handler reflect the last completed turn:
```ts
if (parsed.message_id) {
  setLastTurnWasDemo(parsed.mode === 'demo')
  ...
}
```
(If the sticky-latch behavior is genuinely the locked D-10 design, rename the
field — `lastTurnWasDemo` is a misnomer for "anyTurnWasDemo" — and document the
misleading-banner tradeoff; but the copy "is in use" argues for clearing.)

### WR-03: `?retry=true` cleanup can delete the previous GOOD assistant message (data loss on network-failed sends)

**File:** `backend/routers/chat.py:747-763` (frontend trigger: useChat.ts:368-387)
**Issue:** Pre-existing (Phase 8), flagged because chat.py is in scope and the
new `retryWithDemo` rides the same path. The retry branch deletes the
most-recent assistant row for the thread on the assumption that the prior
attempt left an orphan placeholder. But when the failed send never reached the
server (network error, backend down — the generic Retry bubble path), no orphan
exists: the DELETE removes the assistant reply from the last SUCCESSFUL turn,
and `if not retry` also skips persisting the user message, so the retried user
turn is stored only client-side. Net effect: one good assistant message is
permanently deleted and one user message never persisted. ([Use demo] itself is
safe in practice — it only renders on 403s, which occur after the placeholder
insert — the exposure is the generic Retry.)
**Fix:** Only delete when the newest assistant row actually looks like an
orphan, e.g. select `id, content` and delete only if `content` is empty or one
of the known placeholder strings (`"[An error occurred while generating the response]"`,
`"[Response interrupted]"`); otherwise treat the retry as a fresh send
(including the user-message insert).

### WR-04: `favorite_models` items are unbounded strings — only the list length is validated

**File:** `backend/models/schemas.py:70`
**Issue:** `Field(default=None, max_length=200)` bounds the COUNT (Open Q3) but
each element is an unconstrained `str`. An authenticated user can PUT 200
multi-megabyte strings and the whole-array replace stores them verbatim
(request body size is not otherwise limited in the FastAPI app), bloating the
row and every subsequent GET /api/preferences and picker seed. Model ids are
short slugs; there is no reason to accept arbitrary-length entries.
**Fix:**
```python
from pydantic import StringConstraints
from typing import Annotated

favorite_models: list[Annotated[str, StringConstraints(max_length=200)]] | None = Field(
    default=None, max_length=200
)
```

## Info

### IN-01: OAuth CSRF check passes when both state values are null

**File:** `frontend/src/pages/OAuthCallbackPage.tsx:65`
**Issue:** `returnedState !== storedState` is false when the URL has no `state`
param AND `or_pkce_state` is absent (`null !== null`). Today `pkce.ts:38-39`
always writes verifier+state together, so the gap is unreachable through normal
flows — but the check should not depend on that invariant holding forever.
**Fix:** `if (!code || !verifier || !storedState || returnedState !== storedState) throw new Error('csrf')`

### IN-02: `toggleFavorite` computes the next array from a stale closure

**File:** `frontend/src/components/ModelSelector.tsx:315-322`
**Issue:** `next` is derived from the render-captured `favorites`; two toggles
processed before a re-render (double-fire, rapid Shift+Enter) can drop the
first toggle both locally and in the whole-array PUT.
**Fix:** Use a functional update and fire the PUT from the computed value:
`setFavorites(prev => { const next = ...; queuePut(next); return next })`.

### IN-03: Stale "Wave 0 stub" docstring + dead code in the resolution test module

**File:** `backend/tests/test_key_model_resolution.py:1-22`
**Issue:** The module docstring still claims "Every function below is a Wave 0
STUB … un-skipped and implemented by plan 11-04", but all tests are fully
implemented. `_WAVE0` (line 22) and the `pytest` import (line 20) are unused.
**Fix:** Update the docstring to describe the current coverage; delete `_WAVE0`
and the unused `pytest` import.

### IN-04: Empty-state copy uses dark-only tokens on the theme-aware chat surface

**File:** `frontend/src/components/ChatContainer.tsx:118-143`
**Issue:** Pre-existing (untouched this phase). The container is
`bg-white … dark:bg-gray-950`, but the empty-state block hardcodes dark-theme
tokens (`text-gray-200` headline, `bg-gray-800` chips, `text-gray-400` copy) —
in light mode the headline is near-white on white and the chips are an orphan
dark panel.
**Fix:** Mirror the sibling pattern: `text-gray-900 dark:text-gray-200`,
`bg-gray-100 dark:bg-gray-800`, etc.

### IN-05: `parsePendingSelection` does not validate field types

**File:** `frontend/src/pages/OAuthCallbackPage.tsx:24-32, 86-105`
**Issue:** A crafted stash object (only writable by the user themselves) with a
missing/non-string `modelId` passes the object check; the toast then renders
"Connected — undefined is now your default model." and the PUT body serializes
to `{}` (harmless upsert). Self-inflicted only, but cheap to harden.
**Fix:** Require `typeof parsed.modelId === 'string' && (parsed.kind === 'thread' || parsed.kind === 'default')`
before returning the stash; otherwise fall to the legacy path.

### IN-06: Module-level key-status store persists across logout/login in the same tab

**File:** `frontend/src/hooks/useKeyStatus.ts:55-61, 109-124`
**Issue:** `store` lives at module scope and is never reset on auth change; the
error path keeps last-known status. After sign-out/sign-in as a different user,
the sidebar dot and masked label briefly (or, on repeated fetch failure,
indefinitely) show the PREVIOUS user's connection state. Display-only,
non-secret (masked tail), but incorrect cross-user UI state.
**Fix:** Reset the store (status/balance → null) when the auth session user id
changes, or key the store by user id.

---

_Reviewed: 2026-07-07T19:53:57Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
