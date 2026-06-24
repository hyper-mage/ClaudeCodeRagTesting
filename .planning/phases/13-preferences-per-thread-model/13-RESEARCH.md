# Phase 13: Preferences + Per-Thread Model - Research

**Researched:** 2026-06-24
**Domain:** Server-persisted user preferences (default model, theme) + per-thread model column; Tailwind v4 class-strategy theming retrofit onto a dark-only React 19 app; deprecated-model send-time fallback
**Confidence:** HIGH (codebase integration verified by reading source; Tailwind v4 pattern verified against official docs; one MEDIUM decision flagged — light-mode retrofit strategy)

## Summary

Phase 13 ships the **write + UI** half of model/theme preferences. The chat-path **read** side already exists and is verified live: `backend/routers/chat.py:122-207` resolves model in three tiers (`body.model? → thread.model? → user_preferences.default_model? → owner default`), and both `_safe_thread_model` and `_safe_user_default_model` are **already tolerant** of the absent P13 schema (absent-key read returns None; the `user_preferences` query is wrapped in try/except for the 42P01 relation-does-not-exist case). Phase 13 makes the schema real (a `user_preferences` table + a nullable `threads.model` column), adds three write endpoints (`GET`/`PUT /api/preferences`, `PATCH /api/threads/{id}`), wires a minimal `ModelSelector` + `ThemeToggle` into the frontend, and adds a send-time deprecation-fallback notice. **Resolution logic needs zero change** — once the table/column exist, the existing helpers read real data instead of falling through. This is verified: the live `_safe_user_default_model` already does `db.table("user_preferences").select("default_model").eq("user_id", user_id).maybe_single().execute()`, which is exactly the shape that works once the table is created.

The two genuinely-new technical domains are (1) **theming**: the app is dark-only with *bare* hardcoded utilities (`bg-gray-900`, not `dark:bg-gray-900`) and no ThemeProvider, so wiring Tailwind v4 class-strategy dark mode is greenfield and has a real retrofit decision (covered in Open Questions); and (2) **deprecation fallback**: detecting a thread pinned to a model now absent from the Phase 12 `model_cache` at send time, and inserting a persisted inline notice message rather than crashing. Everything else (migrations with per-user RLS, FastAPI/Pydantic upsert endpoints, hand-rolled Tailwind dropdown) follows patterns already established in the codebase — the migration RLS pattern is in `20240301000025_create_user_api_keys.sql`, the upsert endpoint pattern is in `keys.py:60-71`, and the selector data source (`GET /api/models`) already ships render-ready rows.

**Primary recommendation:** Reuse, don't rebuild. (1) One combined migration creating `user_preferences` (PK `user_id`, own-row RLS modeled on `user_api_keys`) + `ALTER TABLE threads ADD COLUMN model TEXT` (nullable, no backfill, inherits existing threads RLS). (2) A `preferences` router doing `upsert` keyed on `user_id` (mirror `keys.py`). (3) `PATCH /api/threads/{id}` that sets/clears `threads.model`. (4) Tailwind v4 `@custom-variant dark` + a pre-mount inline script in `index.html` reading `localStorage.theme` (official FOUC pattern), with light overrides added only on the four core surfaces. (5) Detect deprecation at send time in `chat.py` right after `_resolve_key_and_model` by checking the resolved model against `model_cache`, and insert a `role:"notice"` (or system) message row before the assistant row.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Theme scope (PREF-02)**
- **D-01:** Ship a **usable light palette on the core surfaces** (chat, sidebar, login, composer) — wire the theme mechanism (root class / CSS variables) plus a real light palette where it matters. Pixel-polish on secondary UI is deferred. Rationale: app is currently dark-only (no `dark:` variants, hardcoded gray palette); a toggle that produces a broken/ugly light mode is bad UX, but full-app re-theming overlaps P14/P15 work. Meets SC#3 (persist + flash-free) with a toggle that looks right where users actually spend time.
- **D-02:** Theme persists server-side in `user_preferences.theme` AND mirrors to `localStorage` so first paint is flash-free (no FOUC) before the preferences fetch resolves.

**Model selector UX + placement**
- **D-03:** Per-thread model selector = a **compact dropdown in the active thread's header**, reusing Phase 12 `model_cache` catalog data (searchable list, free/paid, price/context hints). Minimal, NOT the P15 rich picker (no favorites/pinning/key-gating here).
- **D-04:** Default-model control uses the **same minimal selector component in a small temporary inline spot** (sidebar/header menu) until the Phase 14 settings page exists and absorbs it.

**New-thread model inheritance**
- **D-05:** On thread create, `threads.model` is left **null** → resolution falls through to `user_preferences.default_model` (matches the existing tolerant chain at `chat.py:174-175`). The thread always tracks the user's *current* default. The column is only written when the user **explicitly** picks a per-thread model. No snapshot of the default onto the row.

**Deprecated-model fallback notice (SC#4)**
- **D-06:** When a thread is pinned to a model that is **absent from the Phase 12 `model_cache` at send time**, resolution falls back to the user's default and the user is told via an **inline thread notice message** (a non-AI system/notice line, e.g. "Model X is no longer available — using <default> instead"). Chosen over toast/banner because it persists in thread context and is visible on reload. Must not crash the thread.

### Claude's Discretion
- Preferences API row shape (single upsert row per user), exact migration split (one combined migration vs `user_preferences` + `threads.model` separately), CSS-variable vs Tailwind `dark:`-class strategy for theming, and the precise wording/styling of the deprecation notice line — planner/researcher decide.

### Deferred Ideas (OUT OF SCOPE)
- **Rich model picker** (favorites/pinning, key-gated selection, demo banner) — **Phase 15** (MODEL-08, KEY-05, SEC-03, DEMO-01/02).
- **Settings/account page** consolidating key status + default model + theme + profile — **Phase 14** (PREF-01). P13's temporary default-model control migrates here.
- **Usage/cost display** (per-message cost, balance, low-balance warning, per-thread totals) — **Phase 14** (COST-01..04).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MODEL-05 | User can set a default model | `PUT /api/preferences {default_model}` upsert into `user_preferences` (PK `user_id`); read via existing `_safe_user_default_model` (chat.py:131-149); default-model selector wired into sidebar footer + mobile drawer (D-04). Selector data from existing `GET /api/models`. |
| MODEL-06 | User can select a model per chat thread, persisted on the thread | `ALTER TABLE threads ADD COLUMN model TEXT` (nullable); `PATCH /api/threads/{id} {model}` sets it, `{model:null}` clears to default (D-05); read via existing `_safe_thread_model` (chat.py:122-128) off the already-`SELECT *` thread row; per-thread selector in a NEW `ChatContainer` header row. |
| PREF-02 | User can toggle light/dark theme, persisted per user | `user_preferences.theme` ("light"/"dark") via `PUT /api/preferences {theme}`; mirrored to `localStorage.theme`; Tailwind v4 `@custom-variant dark` class strategy + pre-mount inline script in `index.html` for flash-free first paint (D-02); `ThemeToggle` (lucide Sun/Moon) in temporary spots. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Persist default model + theme | Database / Storage | API / Backend | One row per user in `user_preferences`; RLS enforces per-user isolation; backend owns the upsert via service-role client. |
| Persist per-thread model | Database / Storage | API / Backend | A nullable `threads.model` column on the existing row; inherits existing threads RLS; backend `PATCH` owns the write. |
| Read/resolve model into chat path | API / Backend | — | Three-tier resolution already lives server-side in `chat.py:_resolve_key_and_model`; the FE never resolves model — it only sets it. |
| Detect deprecated model + insert notice | API / Backend | Database / Storage | Deprecation = "absent from `model_cache`", a server-side catalog the FE doesn't own; notice is a persisted message row so it survives reload. |
| Theme application (root class) + FOUC prevention | Browser / Client | — | `localStorage` mirror is the paint-time source of truth; an inline script sets the `<html>` class before React mounts. No SSR in this Vite SPA, so the client owns first paint entirely. |
| Theme/default-model/per-thread selector UI | Browser / Client | API / Backend | Hand-rolled Tailwind controls; they POST/PATCH to the backend but render purely client-side. |
| Model catalog for selectors | API / Backend | Database / Storage | Existing `GET /api/models` serves render-ready rows from `model_cache`; selectors are pure consumers. |

## Standard Stack

No new dependencies. Every library needed already ships in this repo. Project rule (CLAUDE.md): "no new stack/libraries"; UI-SPEC: "Do not run `npx shadcn init` in Phase 13."

### Core (already installed — verified via `npm ls` / `requirements.txt` / source)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tailwindcss | 4.2.2 | Class-strategy dark mode via `@custom-variant` | `[VERIFIED: npm ls]` Already the styling system (`@tailwindcss/vite` 4.2.2). v4 supports class-based dark mode with one CSS line. |
| lucide-react | ^0.577.0 | `Sun`/`Moon`/`ChevronDown`/`Check`/`Info` icons | `[VERIFIED: package.json]` Already the project icon library (UI-SPEC). |
| react / react-dom | ^19.2.4 | Selector + toggle components, hooks | `[VERIFIED: package.json]` |
| FastAPI | 0.115.12 | `preferences` router + `PATCH /api/threads/{id}` | `[VERIFIED: CLAUDE.md/requirements]` Existing router framework. |
| pydantic | 2.11.1 | Request/response models (`PreferencesResponse`, `ThreadModelUpdate`) | `[VERIFIED: requirements]` Project rule: Pydantic for structured I/O. |
| supabase (python) | 2.13.0 | `upsert` / `update` on the service-role client | `[VERIFIED: requirements]` Already used; `upsert(...on_conflict=...)` pattern proven in `keys.py:60`. |

### Supporting (test infra — already installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| vitest | 4.1.9 | Frontend unit/component tests | `[VERIFIED: npm ls]` Config at `frontend/vitest.config.ts` (jsdom, globals, setup `./src/test/setup.ts`). |
| @testing-library/react | 16.3.2 | Render + interact with selector/toggle | `[VERIFIED: npm ls]` |
| @testing-library/user-event | ^14.6.1 | Keyboard/click interaction in selector tests | `[VERIFIED: package.json]` |
| jsdom | 29.1.1 | DOM env for vitest | `[VERIFIED: npm ls]` |
| pytest | (in venv) | Backend endpoint + resolution tests | `[VERIFIED: backend/tests/]` 36 test files; `conftest.py` provides JWT/db mocks. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Tailwind `@custom-variant dark` (class) | CSS custom properties for palette tokens | UI-SPEC explicitly allows either; the contract specifies resolved color values for both. Custom properties avoid touching every utility but require a token layer that doesn't exist yet. See Open Question 1 — they interact differently with the *bare* existing utilities. |
| Inline `index.html` script for FOUC | Set class in `main.tsx` before render | `main.tsx` runs after the bundle loads — too late, FOUC visible. Official Tailwind guidance is an inline `<head>` script. `[CITED: tailwindcss.com/docs/dark-mode]` |
| `role:"notice"` message row for deprecation | Reuse `role:"assistant"` with a marker, or a toast | Toast doesn't persist on reload (D-06 rejects it). A distinct role keeps it out of the LLM history mapping (`chat.py:743` maps role/content into the model context — a notice must NOT be sent to the model). |

**Installation:** None. All dependencies present.

**Version verification (run against the live tree):**
```
npm ls tailwindcss @tailwindcss/vite vitest @testing-library/react jsdom
# → tailwindcss@4.2.2, @tailwindcss/vite@4.2.2, vitest@4.1.9,
#   @testing-library/react@16.3.2, jsdom@29.1.1   [VERIFIED: 2026-06-24]
```

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────────────────────────────────────┐
  THEME PATH        │  index.html <head> inline script (runs BEFORE React)    │
  (browser-owned)   │    reads localStorage.theme → sets <html class="dark">  │
                    │    → flash-free first paint (D-02)                      │
                    └───────────────────────┬─────────────────────────────────┘
                                            │ React mounts
                                            ▼
   ThemeToggle ──click──► toggle <html> class + write localStorage.theme (sync, source of truth)
        │                                   └──fire-and-forget──► PUT /api/preferences {theme}
        ▼
   (on login/app load) GET /api/preferences ──► {default_model, theme}
        │                          theme reconciles localStorage (server wins if differs)

  MODEL PATHS (backend-owned resolution)
  ────────────────────────────────────────
   Default-model selector ──select──► PUT /api/preferences {default_model}  ─► user_preferences (upsert PK user_id)
   Per-thread selector    ──select──► PATCH /api/threads/{id} {model}        ─► threads.model (set)
                          ──"use default"──► PATCH /api/threads/{id} {model:null} ─► threads.model (clear)

   SEND PATH  POST /api/threads/{id}/messages
   ──────────────────────────────────────────
   chat.py event_generator:
     _resolve_key_and_model(db,user,thread_row,body)          ← UNCHANGED (chat.py:787)
        body.model? → thread.model? → user_pref.default_model? → owner default
            │
            ▼  NEW: deprecation check (D-06)
     if thread.model AND thread.model NOT in model_cache:
            resolved = user default (already happens IF thread.model is the
            stale one — see Open Question 2 about the precedence subtlety)
            insert messages row {role:"notice", content:"Model … no longer available …"}
            ── streamed/persisted, survives reload, NOT sent to the LLM
            ▼
     insert assistant row → stream_chat_completion(model=resolved) → SSE deltas
```

### Recommended Project Structure
```
backend/
├── routers/
│   ├── preferences.py        # NEW: GET/PUT /api/preferences (mirror keys.py shape)
│   └── threads.py            # EDIT: add PATCH /{thread_id} for model set/clear
├── models/schemas.py         # EDIT: + PreferencesResponse, PreferencesUpdate, ThreadModelUpdate
│                             #       + add `model: str | None` to ThreadResponse
├── routers/chat.py           # EDIT: deprecation check + notice insert after _resolve_key_and_model
└── main.py                   # EDIT: app.include_router(preferences.router)
supabase/migrations/
└── 20240301000032_create_user_preferences_and_thread_model.sql   # NEW (one combined)
frontend/
├── index.html                # EDIT: pre-mount inline theme script in <head>
├── src/index.css             # EDIT: + @custom-variant dark (...)
├── src/components/
│   ├── ModelSelector.tsx     # NEW: reusable hand-rolled dropdown (listbox a11y)
│   ├── ThemeToggle.tsx       # NEW: Sun/Moon neutral icon button
│   ├── DeprecationNotice.tsx # NEW: persisted inline system line
│   └── ChatContainer.tsx     # EDIT: add shrink-0 h-12 header row hosting per-thread selector
├── src/hooks/
│   ├── useTheme.ts           # NEW (optional): toggle + localStorage + PUT
│   └── usePreferences.ts     # NEW (optional): GET/PUT default_model
└── src/lib/api.ts            # UNCHANGED: apiFetch covers GET/PUT/PATCH (JSON helper)
```

### Pattern 1: Own-row preferences table + per-user RLS (mirror `user_api_keys`)
**What:** A `user_preferences` table with `user_id` as PK and own-row RLS (SELECT/INSERT/UPDATE/DELETE all `auth.uid() = user_id`).
**When to use:** Any per-user singleton settings row.
**Example:**
```sql
-- Source: pattern verified in supabase/migrations/20240301000025_create_user_api_keys.sql
CREATE TABLE user_preferences (
  user_id       UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  default_model TEXT,                                  -- nullable: null → owner default
  theme         TEXT NOT NULL DEFAULT 'dark'
                CHECK (theme IN ('light','dark')),     -- guard invalid values
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own preferences"   ON user_preferences FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own preferences" ON user_preferences FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own preferences" ON user_preferences FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own preferences" ON user_preferences FOR DELETE USING (auth.uid() = user_id);
-- NOTE: unlike user_api_keys, do NOT REVOKE SELECT from authenticated — prefs are non-secret.
```
Note: `default_model` is intentionally NOT a foreign key to `model_cache` — `model_cache` is a refreshable cache (rows can disappear on refresh per Phase 12), so an FK would break D-06's whole premise (a pinned model that *leaves* the cache must remain a valid stored string, not a constraint violation).

### Pattern 2: Upsert endpoint keyed on user_id (mirror `keys.py:60-71`)
**What:** `PUT /api/preferences` upserts one row per user; backend uses the service-role client.
**Example:**
```python
# Source: pattern verified in backend/routers/keys.py:60-71 (upsert) + status (read)
@router.put("/api/preferences", response_model=PreferencesResponse)
async def update_preferences(body: PreferencesUpdate, user_id: str = Depends(get_user_id)):
    db = get_supabase()
    # Build a partial payload — only the fields the client sent, so a theme PUT
    # doesn't clobber default_model and vice-versa (exclude_unset).
    patch = body.model_dump(exclude_unset=True)
    patch["user_id"] = user_id
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()  # ON CONFLICT skips defaults (keys.py:67 Pitfall 4)
    db.table("user_preferences").upsert(patch, on_conflict="user_id").execute()
    row = db.table("user_preferences").select("default_model, theme").eq("user_id", user_id).maybe_single().execute()
    return {"default_model": row.data.get("default_model"), "theme": row.data.get("theme", "dark")}
```
**GET** mirrors `keys.py:status` — `maybe_single()`, return a default-filled object when no row exists (a brand-new user has no prefs row yet → `{default_model: null, theme: "dark"}`).

### Pattern 3: PATCH thread model (set + clear-to-default)
**What:** `PATCH /api/threads/{id}` writes `threads.model`; `{model: null}` clears it (D-05 "use my default").
**Example:**
```python
# Source: ownership-check pattern from threads.py:34-45 (get_thread) + delete_thread:61-69
@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread_model(thread_id: str, body: ThreadModelUpdate, user_id: str = Depends(get_user_id)):
    db = get_supabase()
    owned = db.table("threads").select("id").eq("id", thread_id).eq("user_id", user_id).maybe_single().execute()
    if not owned.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    # model is Optional[str]; null is a valid value (clears the pin). Use exclude_unset
    # is WRONG here — null must be written. Send {"model": body.model} explicitly.
    db.table("threads").update({"model": body.model}).eq("id", thread_id).eq("user_id", user_id).execute()
    updated = db.table("threads").select("*").eq("id", thread_id).maybe_single().execute()
    return updated.data
```
Caution: `ThreadModelUpdate.model` must be `str | None` and the update must write `None` through (not skip it) so "use default" actually clears the column. This is the inverse of the `exclude_unset` advice in Pattern 2 — be explicit per endpoint.

### Pattern 4: Tailwind v4 class-strategy dark mode + FOUC-free inline script
**What:** One CSS line redefines the `dark` variant to a `.dark` class; an inline `<head>` script sets the class before React mounts.
**Example:**
```css
/* Source: tailwindcss.com/docs/dark-mode (verified 2026-06-24) — add to frontend/src/index.css */
@import "tailwindcss";
@plugin "@tailwindcss/typography";
@custom-variant dark (&:where(.dark, .dark *));
```
```html
<!-- Source: tailwindcss.com/docs/dark-mode — inline in frontend/index.html <head>, BEFORE the module script -->
<script>
  document.documentElement.classList.toggle(
    "dark",
    localStorage.theme === "dark" ||
      (!("theme" in localStorage) && window.matchMedia("(prefers-color-scheme: dark)").matches)
  );
</script>
```
**Critical retrofit note:** This pattern scopes only `dark:`-prefixed utilities. The existing app uses **bare** utilities (`bg-gray-900`), so `@custom-variant dark` alone changes nothing visually. See Open Question 1 for the two viable retrofit strategies — the planner MUST pick one. The UI-SPEC color contract specifies resolved values for both themes, so either works.

### Pattern 5: Deprecation detection at send time (D-06)
**What:** After model resolution in `chat.py`, if the thread is pinned to a model absent from `model_cache`, insert a persisted notice row and let resolution fall back.
**Where:** `chat.py` `event_generator`, between `_resolve_key_and_model` (line 787) and the assistant-row insert (line 816).
**Example:**
```python
# Source: integration point verified in backend/routers/chat.py:787-823
thread_model = thread.data.get("model")  # the pinned model (None if following default)
if thread_model:
    cached = db.table("model_cache").select("model_id").eq("model_id", thread_model).maybe_single().execute()
    if not (cached and cached.data):           # absent from cache → deprecated
        default_model = _safe_user_default_model(db, user_id) or settings.llm_model
        db.table("messages").insert({
            "thread_id": thread_id, "user_id": user_id,
            "role": "notice",                  # distinct role → excluded from LLM history map
            "content": f'Model "{thread_model}" is no longer available — using {default_model} instead.',
        }).execute()
        # ensure resolution used the default (see Open Question 2 re: helper precedence)
```
The history map at `chat.py:743` (`[{"role": m["role"], "content": m["content"]} ...]`) and the FE message render must both treat `role:"notice"` specially — the LLM must not receive it, and the UI renders it as a `DeprecationNotice`, not a bubble.

### Anti-Patterns to Avoid
- **FK from `user_preferences.default_model` / `threads.model` to `model_cache`:** breaks D-06 — a pinned model that leaves the cache must persist as a plain string.
- **`exclude_unset` on the thread-model PATCH:** would silently drop a `null`, making "use my default" a no-op. Write `model` explicitly.
- **Setting the theme class in `main.tsx`/React effect only:** runs after bundle load → visible FOUC. Must be an inline `<head>` script.
- **Re-theming the whole app:** D-01 scopes light mode to four core surfaces only; secondary UI (Documents, tool cards) may stay dark this phase.
- **Sending the deprecation notice to the LLM:** it must be filtered out of the history map (`chat.py:743`), or the model sees a fake "system" turn.
- **`:is()` instead of `:where()` in the custom-variant:** `:is()` raises specificity of every dark utility and causes override bugs `[CITED: schoen.world / Tailwind discussion #15083]`. Use `:where()` (zero specificity) — exactly what the official one-liner uses.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Model catalog (free/paid, price, context) | A new fetch/parse of OpenRouter | `GET /api/models` (Phase 12, `models.py`) | Already serves render-ready `ModelResponse` rows from `model_cache`; FE never recomputes is_free (Phase 12 D-02). |
| "Is this model deprecated?" | A deprecation list/registry | Absence from `model_cache` (`db.table("model_cache").select("model_id").eq(...)`) | Phase 12 made `model_cache` the source of truth (CONTEXT canonical ref). |
| Three-tier model resolution | New resolution code in the FE or a new endpoint | `chat.py:_resolve_key_and_model` (UNCHANGED) | Already tolerant of the schema; verified live by `test_key_model_resolution.py`. |
| Per-user data isolation | App-level user_id filters everywhere | Per-user RLS policies (`auth.uid() = user_id`) | Project rule (CLAUDE.md). Pattern proven in `user_api_keys` / `threads`. |
| Auth bearer attach for new endpoints | New fetch wrapper | `apiFetch` (`lib/api.ts`) | Already attaches the Supabase bearer; handles 204 + JSON; covers GET/PUT/PATCH. |
| FOUC-free theme bootstrap | A custom hydration scheme | Official Tailwind inline `<head>` script + `localStorage.theme` | `[CITED: tailwindcss.com/docs/dark-mode]` |
| Component library / Combobox | `npx shadcn init` | Hand-rolled Tailwind dropdown | UI-SPEC: shadcn deferred to Phase 15 (locked roadmap decision). Initializing here contradicts STATE.md. |

**Key insight:** Phase 13's value is wiring, not invention. Every "hard" sub-problem (catalog, deprecation source of truth, resolution, RLS, auth) was already solved in Phases 9–12. The only genuinely-new build is the theming retrofit and the notice row, both of which have a single correct shape documented above.

## Runtime State Inventory

Phase 13 is additive schema + new endpoints + new UI — **not** a rename/refactor/migration of existing data. There is no string being renamed across stored data, services, or OS state. The one stored-data consideration is forward-looking (the `localStorage.theme` mirror), documented for completeness:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | New: `user_preferences` rows + `threads.model` values + `localStorage.theme` (browser). No EXISTING data is renamed or migrated. `threads.model` is added nullable with no backfill — existing threads resolve via the default tier (D-05). | None (additive). Existing threads keep working unchanged. |
| Live service config | None — no external service (n8n, Datadog, Tailscale, etc.) holds a P13 string. Supabase schema is the only "service config" and it's in git migrations. | None. |
| OS-registered state | None — no Task Scheduler / pm2 / systemd entries reference P13 names. | None. |
| Secrets/env vars | None — no new env var or secret key. (Confirmed: `config.py` is untouched; resolution already reads `settings.llm_model` as the owner default.) | None. |
| Build artifacts | None — no package rename, no egg-info, no Docker tag affected. Frontend bundle rebuilds normally; `index.html` inline-script edit is picked up by Vite. | None. |

**Verified by:** reading `chat.py` (no env dependency added), `config.json`, migration list (latest `...000031`), and CLAUDE.md (single `.env`, dual-env dev/prod per MEMORY.md).

## Common Pitfalls

### Pitfall 1: `db push` replays old migrations / "already exists"
**What goes wrong:** `supabase db push` on the dev DB tries to replay the entire migration series and errors with "relation already exists" on tables created long ago.
**Why it happens:** The remote migration history table is out of sync with the local `supabase/migrations/` directory (the dev project pre-dates timestamped migrations being tracked). `[VERIFIED: MEMORY.md — "Supabase migration history repair"]`
**How to avoid:** Before pushing the new `...000032` migration, run `supabase migration repair --status applied <range>` to mark the prior migrations as already applied, THEN `db push` only the new one. The new migration is purely additive (CREATE TABLE + ADD COLUMN), so a clean push of just it is safe.
**Warning signs:** `db push` output listing 30+ migrations to apply, or a 42P07 "already exists" error.

### Pitfall 2: Light mode does nothing after adding `@custom-variant dark`
**What goes wrong:** The toggle flips the `<html>` class but the UI stays dark.
**Why it happens:** Existing utilities are bare (`bg-gray-900`), not `dark:bg-gray-900`. The custom-variant only governs `dark:`-prefixed classes, of which there are currently zero. `[VERIFIED: ChatPage.tsx:104, ThreadSidebar.tsx:73 — bare utilities, grep for `dark:` returns nothing]`
**How to avoid:** Pick a retrofit strategy (Open Question 1). Either invert (make existing bare classes the light baseline, add `dark:` overrides) or use CSS custom-property tokens for the four core surfaces. Don't expect the one-liner alone to produce light mode.
**Warning signs:** Toggle changes the class in devtools but no color change on chat/sidebar/login/composer.

### Pitfall 3: Deprecation notice gets sent to the LLM as a turn
**What goes wrong:** The model receives a "Model X is no longer available" message as conversation history and responds to it.
**Why it happens:** `chat.py:743` maps ALL message rows into the LLM context. A notice row with `role:"notice"` (or worse, `role:"system"`/`role:"assistant"`) would flow into the model unless filtered.
**How to avoid:** Use a distinct role (`"notice"`) and filter it from the history map: `[... for m in history.data if m["role"] in ("user","assistant")]`. Verify the FE render also special-cases it.
**Warning signs:** The assistant references "the unavailable model" in its reply, or the notice appears as a chat bubble.

### Pitfall 4: `maybe_single()` 406 / coupling on a brand-new user
**What goes wrong:** `GET /api/preferences` for a user who has never set a preference errors instead of returning a default.
**Why it happens:** `maybe_single()` returns `data=None` for zero rows (this is handled), but some supabase-py versions raise on `single()`. The codebase already uses `maybe_single()` defensively (`keys.py:79-88` guards `if not row or not row.data`).
**How to avoid:** Mirror `keys.py:status` exactly — `maybe_single()` + `if not row or not row.data: return {default_model: None, theme: "dark"}`.
**Warning signs:** A 406 or AttributeError on first load for a fresh account.

### Pitfall 5: Theme flash on hard reload despite localStorage
**What goes wrong:** A brief dark flash before light renders (or vice-versa) on reload.
**Why it happens:** The class is set in React (`main.tsx` or an effect) which runs only after the JS bundle parses.
**How to avoid:** The class MUST be set by a synchronous inline `<head>` script before the stylesheet/bundle (Pattern 4). `[CITED: tailwindcss.com/docs/dark-mode]`
**Warning signs:** Visible flash on Cmd-R, especially on a throttled connection.

### Pitfall 6: server/localStorage theme divergence
**What goes wrong:** A user toggles light on device A; on device B `localStorage` still says dark, so first paint is dark even though their saved preference is light.
**Why it happens:** localStorage is per-device; the server value is the cross-device truth, but it arrives only after `GET /api/preferences`.
**How to avoid (D-02 intent):** Accept a one-frame reconciliation — paint from localStorage (no FOUC for the common single-device case), then after `GET /api/preferences` resolves, if the server theme differs, update the class + localStorage. This is the documented localStorage-mirror tradeoff, not a bug. Plan should make the reconciliation explicit so it's testable.
**Warning signs:** Theme "snaps" after login on a second device — expected and acceptable per D-02.

## Code Examples

### GET preferences with safe default for a brand-new user
```python
# Source: mirrors backend/routers/keys.py:76-93 (status endpoint guard)
@router.get("/api/preferences", response_model=PreferencesResponse)
async def get_preferences(user_id: str = Depends(get_user_id)):
    row = (get_supabase().table("user_preferences")
           .select("default_model, theme").eq("user_id", user_id)
           .maybe_single().execute())
    if not row or not row.data:
        return {"default_model": None, "theme": "dark"}   # no row yet → app defaults
    return {"default_model": row.data.get("default_model"),
            "theme": row.data.get("theme") or "dark"}
```

### Frontend theme toggle (localStorage = paint truth, server fire-and-forget)
```typescript
// Source: Tailwind v4 class strategy (tailwindcss.com/docs/dark-mode) + apiFetch (lib/api.ts)
function setTheme(theme: 'light' | 'dark') {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  localStorage.theme = theme                                  // source of truth for paint (D-02)
  void apiFetch('/api/preferences', { method: 'PUT', body: JSON.stringify({ theme }) })
    .catch(() => { /* non-blocking; localStorage already applied */ })
}
```

### Hand-rolled selector keyboard a11y skeleton (UI-SPEC listbox contract)
```typescript
// Source: UI-SPEC Components table — role=listbox/option, Enter/Space/Esc/arrows, focus trap.
// No shadcn (deferred to P15). Trigger: aria-haspopup="listbox" aria-expanded={open}.
// Each row min-h-11 (44px), selected row gets a blue-600 check/left-border.
```
(Full implementation is a planner task; the a11y contract — `aria-haspopup`, `aria-expanded`, `role="listbox"`/`"option"`, Esc-closes, arrow-nav, focus-return-on-close, outside-click-close, ≥44px rows — is locked in UI-SPEC § Components.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tailwind.config.js` `darkMode: 'class'` | `@custom-variant dark (&:where(.dark,.dark *))` in CSS | Tailwind v4 (Jan 2025) | No JS config file is loaded by default in v4; `darkMode: 'class'` has NO effect unless you opt into a legacy `@config`. The CSS-first one-liner is the v4 way. `[CITED: tailwindcss.com/docs/dark-mode; WebSearch]` |
| Media-query-only dark mode | Class/selector strategy for manual toggle | Always available, but v4 syntax differs | This app needs manual toggle (PREF-02), so the media-only default must be overridden with the custom-variant. |

**Deprecated/outdated:**
- `darkMode: 'class'` in `tailwind.config.js` — non-functional in Tailwind v4 without a legacy `@config` directive. Do not add a config file for this.
- shadcn Combobox for the selector — NOT this phase (Phase 15). Hand-roll.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `role:"notice"` is an acceptable new message role and the `messages` table `role` column has no CHECK constraint forbidding it | Pattern 5 / Pitfall 3 | If `messages.role` has a CHECK/enum constraint, the notice insert fails. **Planner must verify** `messages` schema (`20240301000002_create_messages.sql`) for a role constraint and, if present, add `"notice"` to it in the new migration. Confirmed `tools_used` exists (migration 024); role constraint NOT yet verified. |
| A2 | The Phase 12 `model_cache` retains rows for currently-valid models such that "absent from cache" reliably means "deprecated" (not "cache mid-refresh / empty") | Pattern 5 (deprecation check) | If a transient empty/partial cache could make a *valid* model look deprecated, users get spurious notices. Phase 12 guards against empty-catalog wipes (`refresh_if_stale` WR-01/serve-stale), so this is low-risk, but the planner should ensure the check tolerates an empty cache (skip the deprecation notice if `model_cache` is empty). |
| A3 | `GET /api/preferences` should be added even though resolution doesn't need it — the FE needs it to hydrate the default-model selector's current value and the theme on login | phase_requirements / GET pattern | If GET is skipped, the default-model selector can't show the current selection and cross-device theme won't reconcile. Low risk; both endpoints are in CONTEXT scope. |
| A4 | The temporary default-model control placement (sidebar footer + mobile drawer) is non-destructive to the existing `ThreadSidebar`/`MobileDrawer` layout | Architecture / UI-SPEC | UI-SPEC locks this placement; risk is purely visual polish, deferred per D-01. |

## Open Questions

1. **Light-mode retrofit strategy: invert bare utilities vs CSS custom-property tokens.**
   - What we know: App uses bare dark utilities everywhere (`bg-gray-900`, no `dark:` prefix anywhere — verified by reading ChatPage/ThreadSidebar/ChatContainer). `@custom-variant dark` only governs `dark:`-prefixed classes. UI-SPEC allows either the class strategy OR CSS custom properties and specifies resolved color values for both themes.
   - What's unclear: Which retrofit is least invasive for the four core surfaces (chat, sidebar, login, composer).
   - Recommendation: **Option A (recommended) — CSS custom-property tokens scoped to core surfaces.** Define palette vars (`--surface-bg`, `--surface-secondary`, `--text-primary`, `--text-muted`, `--border`) under `:root` (light) and `.dark` (dark) in `index.css`, and on the four core-surface components replace the bare `gray-*` utilities with `bg-[var(--surface-bg)]` etc. This touches only ~4 component files, keeps the brand-invariant `blue-600`/`red-600` as literal utilities (UI-SPEC: accent is theme-invariant), and the `@custom-variant dark` line still governs any `dark:` overrides you add for chips/hover. **Option B — invert:** treat existing bare classes as the *light* baseline and add `dark:` overrides for current dark colors on core surfaces; larger diff (every core-surface utility gets a `dark:` sibling) but fully Tailwind-native. The planner should pick Option A for a smaller, more reviewable diff that matches D-01's "core surfaces only" scope. Either satisfies the UI-SPEC contract.

2. **Does the deprecation notice require any change to `_resolve_key_and_model`, or does resolution already fall back correctly?**
   - What we know: `_resolve_key_and_model` resolves `thread.model` BEFORE `user_preferences.default_model` (chat.py:172-177). If `thread.model` is a deprecated string, resolution currently returns that deprecated string (it's a non-null value, so the chain stops there) — it does NOT auto-fall-through to the default.
   - What's unclear: Whether to (a) leave resolution untouched and let the deprecated model be sent to OpenRouter (which 404s → caught by the existing error path), or (b) have the deprecation check OVERRIDE the resolved model to the default before the LLM call.
   - Recommendation: **Option (b)** — the deprecation check (Pattern 5) must run BEFORE `stream_chat_completion` and substitute the default model when the pinned model is absent from cache, so the turn actually succeeds on the fallback model (SC#4 "falls back to default ... not a crash"). This is a small, localized addition in `event_generator` (override `model = default_model` after inserting the notice), NOT a change to `_resolve_key_and_model` itself. The CONTEXT note "minimal/no change to resolution logic" holds — the override lives in the send path, not the resolver. **Flag for the planner:** confirm whether they want the resolver to remain the pure 3-tier function (recommended) with the deprecation override layered in the caller.

3. **`messages.role` column constraint (see A1).**
   - What we know: A new `role:"notice"` value is the cleanest way to keep the notice out of LLM history and render it distinctly.
   - What's unclear: Whether `messages.role` has a DB-level CHECK/enum.
   - Recommendation: Planner reads `20240301000002_create_messages.sql`. If a constraint exists, the `...000032` migration must ALTER it to allow `'notice'`. If `role` is free `TEXT`, no change needed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Supabase project (dev) | Migration apply (`db push`) | ✓ | hosted (.env=dev) | — (MEMORY.md: dual-env; prod deferred to deploy) |
| supabase CLI | `db push` / `migration repair` | Assumed ✓ | — | Apply SQL via Supabase dashboard SQL editor if CLI unavailable |
| Node.js | Frontend build/test | ✓ | per `.nvmrc` present | — |
| npm | Frontend deps (all installed) | ✓ | — | — |
| Python venv | Backend run + pytest | ✓ | `backend/venv/` | — (CLAUDE.md rule) |
| OpenRouter API | `GET /api/models` cache refresh (already working) | ✓ | public catalog endpoint | Serve-stale (Phase 12 D-04) |

**Missing dependencies with no fallback:** None — all stack is in place; Phase 13 adds no new external dependency.

**Missing dependencies with fallback:**
- `supabase` CLI for `db push`: if not installed/authed locally, apply the migration SQL directly in the Supabase dashboard SQL editor against the dev project (MEMORY.md confirms migration history can be finicky; manual apply sidesteps the replay issue entirely).

**Note on migration apply (Pitfall 1):** Per MEMORY.md, `db push` may try to replay the full series; run `supabase migration repair --status applied` on the prior range first, or apply the single new migration via the dashboard.

## Validation Architecture

> nyquist_validation is enabled (config.json `workflow.nyquist_validation: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework (frontend) | vitest 4.1.9 + @testing-library/react 16.3.2 + jsdom 29.1.1 |
| Config file (frontend) | `frontend/vitest.config.ts` (environment jsdom, globals true, setup `./src/test/setup.ts`) |
| Framework (backend) | pytest (in `backend/venv`); shared fixtures in `backend/tests/conftest.py` |
| Config file (backend) | none detected (no pytest.ini/pyproject) — tests run via `python -m pytest` from `backend/` with `conftest.py` path insertion |
| Quick run command (frontend) | `cd frontend && npx vitest run src/components/ModelSelector.test.tsx` |
| Quick run command (backend) | `cd backend && ./venv/Scripts/python -m pytest tests/test_preferences_api.py -x` |
| Full suite command (frontend) | `cd frontend && npm test` (`vitest run`) |
| Full suite command (backend) | `cd backend && ./venv/Scripts/python -m pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MODEL-05 | PUT /api/preferences upserts default_model; GET returns it | integration (backend) | `pytest tests/test_preferences_api.py::test_put_then_get_default_model -x` | ❌ Wave 0 |
| MODEL-05 | brand-new user GET returns `{default_model:null, theme:"dark"}` | integration (backend) | `pytest tests/test_preferences_api.py::test_get_defaults_for_new_user -x` | ❌ Wave 0 |
| MODEL-05 | default-model selector PUTs on select | component (frontend) | `vitest run src/components/DefaultModelSelector.test.tsx` | ❌ Wave 0 |
| MODEL-06 | PATCH /api/threads/{id} sets threads.model; survives reload (GET returns it) | integration (backend) | `pytest tests/test_thread_model_patch.py::test_patch_sets_model -x` | ❌ Wave 0 |
| MODEL-06 | PATCH {model:null} clears the pin back to default | integration (backend) | `pytest tests/test_thread_model_patch.py::test_patch_null_clears -x` | ❌ Wave 0 |
| MODEL-06 | resolution reads real thread.model once column exists (no regression) | unit (backend) | `pytest tests/test_key_model_resolution.py::test_model_fallthrough_absent_p13_schema -x` (existing) + new `test_thread_model_wins_when_set` | ✅ existing / ❌ new |
| MODEL-06 | per-thread selector shows `Default model` sub-state when model is null; PATCHes on select | component (frontend) | `vitest run src/components/ChatContainer.test.tsx` (extend) | ✅ file exists / ❌ cases |
| PREF-02 | PUT /api/preferences persists theme; CHECK rejects invalid theme | integration (backend) | `pytest tests/test_preferences_api.py::test_theme_persist_and_validate -x` | ❌ Wave 0 |
| PREF-02 | toggle flips `<html>` class + writes localStorage + fires PUT | component (frontend) | `vitest run src/components/ThemeToggle.test.tsx` | ❌ Wave 0 |
| PREF-02 | inline-script FOUC: html.dark set from localStorage before mount | unit (frontend, jsdom) | `vitest run src/test/themeBootstrap.test.ts` | ❌ Wave 0 |
| SC#4 (D-06) | pinned model absent from model_cache → notice row inserted, fallback model used, no crash | integration (backend) | `pytest tests/test_deprecated_model_fallback.py::test_inserts_notice_and_falls_back -x` | ❌ Wave 0 |
| SC#4 (D-06) | notice row is NOT sent to the LLM history | unit (backend) | `pytest tests/test_deprecated_model_fallback.py::test_notice_excluded_from_history -x` | ❌ Wave 0 |
| SC#4 (D-06) | DeprecationNotice renders as a system line (not a bubble, not red) | component (frontend) | `vitest run src/components/DeprecationNotice.test.tsx` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the single relevant quick command (e.g. `pytest tests/test_preferences_api.py -x` or `vitest run <file>`).
- **Per wave merge:** `cd backend && ./venv/Scripts/python -m pytest -q` AND `cd frontend && npm test`.
- **Phase gate:** both full suites green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `backend/tests/test_preferences_api.py` — covers MODEL-05, PREF-02 (GET/PUT, defaults, theme CHECK). Mirror `test_models_api.py` patching style (`app.dependency_overrides[get_user_id]`, `patch("routers.preferences.get_supabase")`).
- [ ] `backend/tests/test_thread_model_patch.py` — covers MODEL-06 PATCH set/clear + 404 on non-owned thread.
- [ ] `backend/tests/test_deprecated_model_fallback.py` — covers SC#4: notice insert, fallback override, history exclusion. Reuse `mock_stream_chat_completion` fixture (conftest.py:74) + the `_db_with_key_row` mock pattern from `test_key_model_resolution.py`.
- [ ] `backend/tests/test_key_model_resolution.py` — ADD `test_thread_model_wins_when_set` (real column present, thread.model used over default) — extends existing file.
- [ ] `frontend/src/components/ModelSelector.test.tsx` — a11y contract (listbox roles, keyboard, ≥44px, selected indicator).
- [ ] `frontend/src/components/ThemeToggle.test.tsx` — class toggle + localStorage write + PUT fired.
- [ ] `frontend/src/components/DefaultModelSelector.test.tsx` + `DeprecationNotice.test.tsx`.
- [ ] `frontend/src/test/themeBootstrap.test.ts` — extract the inline-script logic into a tiny importable function so it's unit-testable under jsdom (the inline `<head>` script itself can mirror the function).
- [ ] No framework install needed — vitest + RTL + jsdom (frontend) and pytest + conftest (backend) already present.

## Security Domain

> security_enforcement enabled (absent from config = enabled).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `Depends(get_user_id)` on all three new endpoints (codebase norm); JWT sub binds the row, never a body field. |
| V3 Session Management | no | No new session surface; bearer attached by existing `apiFetch`. |
| V4 Access Control | yes | Per-user RLS on `user_preferences` (own-row, `auth.uid()=user_id`); `threads.model` inherits existing threads RLS; backend ownership re-check on PATCH (`.eq("user_id", user_id)`) defense-in-depth even though service-role bypasses RLS. |
| V5 Input Validation | yes | Pydantic models (`PreferencesUpdate`, `ThreadModelUpdate`); `theme` constrained to `'light'|'dark'` via DB CHECK + Pydantic `Literal`. `default_model`/`model` are free strings (must be — D-06 stores deprecated-but-valid strings) but are never executed/interpolated into SQL (parameterized via supabase-py). |
| V6 Cryptography | no | No secrets handled in P13 (preferences are non-secret; unlike `user_api_keys`, do NOT REVOKE SELECT). |

### Known Threat Patterns for FastAPI + Supabase + React

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR — PATCH another user's thread model | Tampering / EoP | Ownership check `.eq("id",tid).eq("user_id",uid)` before update (threads.py:61-69 pattern) + threads RLS. |
| Cross-user preference read/write | Information Disclosure / EoP | Own-row RLS on `user_preferences`; backend binds `user_id` from JWT, never from the body. |
| Stored XSS via model name / deprecation notice | Tampering | Notice content is server-composed from `default_model`/`thread.model` strings; React escapes by default (notice rendered as text, NOT `dangerouslySetInnerHTML`). Model ids come from the controlled `model_cache`/owner default. |
| Invalid theme value poisoning paint | Tampering | DB CHECK `theme IN ('light','dark')` + Pydantic `Literal['light','dark']`; client also normalizes unknown values to `'dark'`. |
| Notice row injected into LLM context (prompt-confusion) | Tampering | History map filters to `role in (user,assistant)` (Pitfall 3) — `notice` rows never reach the model. |
| Theme PUT used to probe other users | Info Disclosure | Endpoint only ever reads/writes `auth.uid()`'s own row; no path-param user id. |

## Sources

### Primary (HIGH confidence)
- Codebase (read directly, 2026-06-24): `backend/routers/chat.py` (122-207 resolution, 667-846 send path), `backend/routers/threads.py`, `backend/routers/keys.py` (upsert/status pattern), `backend/routers/models.py`, `backend/services/model_catalog_service.py`, `backend/models/schemas.py`, `supabase/migrations/20240301000001_create_threads.sql`, `..._000025_create_user_api_keys.sql`, `..._000030_create_model_cache.sql`, `backend/tests/conftest.py`, `backend/tests/test_key_model_resolution.py`, `backend/tests/test_models_api.py`, `frontend/src/lib/api.ts`, `frontend/src/hooks/useChat.ts`, `frontend/src/pages/ChatPage.tsx`, `frontend/src/components/{ChatContainer,ThreadSidebar}.tsx`, `frontend/src/contexts/AuthContext.tsx`, `frontend/index.html`, `frontend/src/index.css`, `frontend/vitest.config.ts`, `frontend/src/test/utils.tsx`, `frontend/src/pages/ChatPage.test.tsx`, `frontend/package.json`.
- tailwindcss.com/docs/dark-mode — class-strategy `@custom-variant dark (&:where(.dark,.dark *))` + FOUC inline script (verified 2026-06-24 via WebFetch + ctx7 `/tailwindlabs/tailwindcss.com`).
- `npm ls` (2026-06-24): tailwindcss@4.2.2, @tailwindcss/vite@4.2.2, vitest@4.1.9, @testing-library/react@16.3.2, jsdom@29.1.1.

### Secondary (MEDIUM confidence)
- WebSearch (Tailwind v4 dark mode retrofit): confirms `darkMode:'class'` config is non-functional in v4 without `@config`; `:where()` (zero specificity) preferred over `:is()`. Cross-verified with the official docs above.
- `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `.planning/config.json` — phase scope, requirement traceability, validation flag.
- MEMORY.md — Supabase migration history repair caveat; dual dev/prod env discipline.

### Tertiary (LOW confidence)
- Community articles (schoen.world, nerdleveltech, Tailwind discussion #15083) on advanced custom-variant patterns — used only to corroborate the `:where()` specificity point, not as a primary source.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every dependency verified installed via `npm ls`/requirements; no new deps by project rule.
- Architecture (endpoints, migration, resolution wiring): HIGH — integration points read directly from source; resolution helpers + tests confirm the read side is schema-tolerant and unchanged.
- Theming: MEDIUM — Tailwind v4 mechanism is HIGH-confidence (official docs), but the specific *retrofit* of bare-utility dark-only code has two valid strategies (Open Question 1); the planner must choose. The FOUC inline-script pattern is HIGH.
- Deprecation fallback: HIGH on the mechanism (model_cache absence check + notice row), MEDIUM on two details flagged in Assumptions (A1 role constraint, A2 empty-cache tolerance) the planner must verify.
- Pitfalls: HIGH — drawn from verified source (`chat.py:743` history map, bare-utility grep, MEMORY.md migration caveat, `keys.py` maybe_single guard).

**Research date:** 2026-06-24
**Valid until:** 2026-07-24 (stable — internal codebase + Tailwind v4 stable release; re-verify only if Tailwind major version or Supabase client major changes).
