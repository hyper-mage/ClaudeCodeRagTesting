# Feature Research

**Domain:** BYOK (bring-your-own-key) + model-selection UX for an LLM chat app (OpenRouter-backed)
**Researched:** 2026-06-18
**Confidence:** MEDIUM-HIGH (OpenRouter API behaviors verified against official docs = HIGH; UX conventions drawn from T3 Chat / LibreChat / Open WebUI / OpenRouter's own UI + general BYOK practice = MEDIUM)

> Scope note: This is a SUBSEQUENT milestone (v1.2) layered on a shipped board-game RAG app.
> Existing auth (email/password + anonymous Try-demo), thread management, SSE streaming chat,
> and the agentic tool-use loop are NOT re-scoped here. Every feature below is evaluated for
> how it attaches to those existing systems. Downstream consumer is requirements definition —
> categories, complexity, and dependencies are called out explicitly per feature.

## Key Verified Facts (drive the whole design)

These OpenRouter behaviors are confirmed and shape what is and isn't feasible:

1. **OAuth PKCE returns a real user-controlled inference key.** App redirects to `openrouter.ai/auth?callback_url=...&code_challenge=...&code_challenge_method=S256`, user authorizes, OpenRouter redirects back with `?code=`, backend POSTs to `https://openrouter.ai/api/v1/auth/keys` with the code + `code_verifier` and gets back an API key. (HIGH — official OAuth docs)
2. **Per-request cost is returned inline, automatically.** Every chat completion response now includes `usage.cost` (USD) plus `usage.cost_details`, in the trailing SSE chunk for streams. The old `usage.include` / `stream_options.include_usage` flags are deprecated and no longer needed. This means **per-message cost display requires zero extra API calls.** (HIGH — Usage Accounting docs)
3. **A normal inference key can read its own balance.** `GET /api/v1/key` (Bearer = the user's key) returns `usage`, `limit`, `limit_remaining`, `is_free_tier`, plus daily/weekly/monthly spend. So an OAuth-provisioned per-user key can show its own remaining balance. **No management key required for this.** `GET /api/v1/credits` is a separate, account-level endpoint that DOES require a management key — do not use it for per-user balance. (HIGH — limits docs)
4. **`/models` distinguishes free vs paid cleanly.** Each model has `pricing.prompt` / `pricing.completion` as string USD-per-token; `"0"` on both = free. Models also carry `id`, `name`, `description`, `context_length`, `created` (Unix ts → detect new models), `architecture` (modalities), `top_provider`, `supported_parameters`. Free models also surface as a `:free` id suffix in OpenRouter's catalog convention. (HIGH — get-models docs)
5. **Popularity is a sort, not a per-model score.** OpenRouter's catalog supports `most-popular` / `top-weekly` sorting and `benchmarks` (ELO/intelligence indices) but individual model objects do NOT carry a stable popularity number. "Trending/popular" tagging must be derived (curated allowlist, or scrape the ranked sort) — not read off a field. (HIGH — get-models docs)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Missing these makes the BYOK feature feel broken or untrustworthy.

| Feature | Why Expected | Complexity | Notes / Dependencies |
|---------|--------------|------------|----------------------|
| **OAuth "Connect OpenRouter" button (PKCE)** | Manual key paste is friction + error-prone; one-click is the modern norm | HIGH | Backend generates `code_verifier`/`code_challenge`, stores verifier against session/state, redirects; callback route exchanges code → key. Depends on existing **auth** (must know which user owns the returned key). Needs a dedicated callback route in the SPA + a backend exchange endpoint. |
| **OAuth callback success / failure / cancel states** | Users abandon if the return lands on a blank or broken screen | MEDIUM | Three explicit UI states: success ("Connected as <label>"), failure (exchange error, expired code, challenge mismatch), user-cancelled (returned with no/`error` param). Show a retry affordance, never a dead end. |
| **Encrypted server-side key storage, RLS-scoped** | Storing a raw key in plaintext or in the browser is a security non-starter | HIGH | Encrypt at rest in backend (the project already has `cryptography` 46.x). Key column on a per-user table, RLS so only owner row is reachable; decrypt only in backend at call time, never return the key to the frontend. Depends on **auth** (`user_id`) and existing RLS conventions. |
| **"Connection status" indicator** | Users need to know whether they're on their own key or not | LOW | Boolean "connected / not connected" + the key label/last4 + connected date. Frontend reads a status endpoint, never the key itself. |
| **Disconnect / reconnect** | If you can connect, you must be able to disconnect (trust + key rotation) | LOW-MEDIUM | "Disconnect" deletes the stored key row (and ideally calls OpenRouter to revoke if supported); reconnect re-runs OAuth. Disconnect should warn if it will drop the user back to demo/disabled state. |
| **Model picker (list from `/models`)** | A BYOK app whose whole point is "choose your model" must let you choose | MEDIUM | Fetch + cache `/models`, render a searchable list. Depends on key-gating for paid models and on **per-thread/global selection** to persist the choice. |
| **Free vs paid visual distinction** | Users must not accidentally burn credits; free-tier users need to see what's free | LOW | Tag/badge each model "Free" vs price hint, derived from `pricing.prompt`/`completion === "0"` (and/or `:free` suffix). |
| **Search / filter in the picker** | OpenRouter has 400+ models; an unfiltered list is unusable | MEDIUM | Text search over name/id; at minimum a "Free only" filter. This is table stakes at OpenRouter's catalog size, not a differentiator. |
| **A sensible default model** | New users shouldn't have to choose before they can chat | LOW | Pick a known-good default (free model for demo users, the owner's configured model as the global default). Depends on **demo fallback** + **global default** settings. |
| **Per-message cost display** | BYOK users are spending real money; hiding cost feels predatory | LOW | Read `usage.cost` from the completion response (already inline, no extra call). Render unobtrusively under each assistant message. Depends on **chat loop** surfacing the trailing usage chunk to the frontend. |
| **Account balance display** | "How much do I have left?" is the first question of any prepaid system | LOW-MEDIUM | `GET /api/v1/key` with the user's key → `limit_remaining` / `usage`. Cache briefly; refresh after sends. |
| **Key-gated model selection (trigger OAuth)** | Selecting a paid model with no key must do *something* helpful, not silently fail | MEDIUM | If user picks a model requiring a key they lack → intercept and launch the connect flow (or block + explain). Depends on **OAuth flow** + **model picker** + **key status**. |
| **Owner-key demo fallback (global flag, default off)** | The public portfolio demo must keep working for anonymous Try-demo users | MEDIUM | A single global config flag; when on, users with no key fall back to the owner key + a restricted (free/cheap) model. Default OFF so it's an explicit operator choice. Depends on existing **anonymous auth** and **config** pattern. |
| **Obvious "you're on demo keys" state** | Users (and the owner) must never confuse "owner is paying" with "I'm paying" | LOW-MEDIUM | Persistent, non-dismissible-while-active banner/badge: "Demo mode — using shared keys, limited models. Connect your own key for full access." Drives BYOK conversion AND protects the owner's spend. |
| **Settings / account page** | Every consumer chat app has a settings home for key, model, theme, profile | MEDIUM | New route. Sections: Connection (key status, connect/disconnect, balance), Default model, Appearance (theme), Profile/account (email, sign out). Depends on **auth**, **key storage**, **model picker**, **theme**. |
| **Light / dark theme toggle, persisted** | Baseline expectation for any 2026 web app; many users assume system-match | LOW | Three-state is the modern norm: Light / Dark / System. Persist per user (DB or localStorage). Tailwind 4 `dark:` variant already in stack. |

### Differentiators (Competitive Advantage)

Not strictly required, but they make the BYOK experience feel polished and trustworthy.

| Feature | Value Proposition | Complexity | Notes / Dependencies |
|---------|-------------------|------------|----------------------|
| **Per-thread model selection (persisted)** | Power users want a cheap model for casual threads and a strong one for hard board-game rules reasoning; locking model globally is limiting | MEDIUM | Store `model` on the thread row; the picker in the composer sets it; chat loop reads thread.model. Depends on existing **threads** schema (add a column) + **chat loop** (use per-thread model instead of global config). This is the highest-leverage differentiator for a multi-model app. |
| **Popularity / "trending" marking in picker** | Cuts choice paralysis across 400+ models; signals "safe defaults" | MEDIUM | No per-model popularity field exists — derive it: curate a short allowlist of recommended models, or fetch OpenRouter's `most-popular`/`top-weekly` ranked order and tag the top N. Keep curation in config so it's cheap to update. |
| **Context-length + pricing hints inline** | Helps users pick the right tool (long board-game manuals need big context) and avoid surprise cost | LOW | Show `context_length` (e.g. "128K ctx") and a per-Mtok price hint from `pricing`. Data already in the cached `/models` payload — near-free once the picker exists. |
| **Scheduled model-list refresh (auto pick up new models)** | Catalog churns constantly; a stale list looks abandoned and hides new releases | MEDIUM | Periodic refresh of cached `/models` (cron-style, or refresh-on-read with TTL). `created` timestamp lets you flag "New" models. No background-worker infra exists today, so prefer **TTL-cached refresh-on-read** over a true scheduler to fit the synchronous-backend architecture. |
| **Low-balance warning** | Prevents the jarring "request failed, out of credits" mid-conversation | LOW-MEDIUM | When `limit_remaining` drops below a threshold (or a send fails for insufficient credits), show a warning with a "top up on OpenRouter" link. Depends on **balance display**. |
| **Cumulative / per-thread cost rollup** | "What has this conversation cost me?" is a natural follow-on to per-message cost | LOW | Sum `usage.cost` across a thread's messages; show in thread header or settings. Pure derived data once per-message cost is stored. |
| **Favorites / pinned models** | At 400+ models, even a great picker benefits from a personal shortlist (T3 Chat ships this) | MEDIUM | Per-user favorites list; pinned models float to top of picker. Nice-to-have; defer unless picker UX testing shows it's needed. |
| **"New" badge on recently-added models** | Rewards model enthusiasts, signals the catalog is fresh | LOW | Derived from `/models` `created` ts vs now. Cheap rider on the refresh feature. |

### Anti-Features (Commonly Requested, Often Problematic)

Document these so they don't sneak into scope.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Manual API key paste field** | Seems simpler than OAuth; "just let me paste my key" | Encourages key mishandling, supports a second auth path you must secure/test, and OAuth PKCE is the whole point of near-zero-friction onboarding. Two paths = double the failure surface. | OAuth-only. If a fallback is ever needed, gate it behind a hidden/advanced toggle — not a primary affordance. |
| **Storing keys in the browser (localStorage/cookies)** | Easier than building encrypted server storage | XSS-exfiltratable, can't be RLS-scoped, breaks the "decrypt only in backend" rule, and undermines the security posture this milestone exists to establish | Encrypted server-side storage, key never returned to frontend. |
| **Showing the full key back to the user** | "Let me copy/verify my key" | Re-exposes a secret you worked to protect; invites leaking into screenshots/support chats | Show label + last-4 only. To rotate, disconnect + reconnect. |
| **Per-message model switching mid-thread by default** | "I want to swap models on every message" | Confuses cost attribution and conversation coherence; the agentic tool loop assumes a stable model per turn-chain | Per-thread model is the granularity; allow changing a thread's model going forward, not retroactively per message. |
| **Multi-provider BYOK (OpenAI + Anthropic + ... keys)** | "Why only OpenRouter?" | OpenRouter already aggregates 400+ models behind one key — adding native provider keys multiplies auth flows, key storage shapes, and model-catalog logic for near-zero added coverage | OpenRouter-only BYOK. Its catalog is the multi-provider answer. |
| **Admin UI for the model allowlist / demo config** | "Let me toggle demo mode and curate models in the app" | Project rule is explicitly *no admin UI*; config is env/flag-driven | Global flag via existing `Settings`/env config; curated model list in config or a seed, edited by redeploy. |
| **Real-time balance polling / live cost ticker** | "Show my balance updating live" | Hammers `GET /api/v1/key`, risks rate limits, adds little over refresh-after-send | Refresh balance on settings open and after each send; show per-message cost inline (already free from `usage.cost`). |
| **Billing / top-up flow inside the app** | "Let me add credits without leaving" | Re-implementing OpenRouter's payment surface is out of scope and a compliance burden | Deep-link to OpenRouter's credits page for top-ups. |
| **Building a true background scheduler for model refresh** | "Refresh the catalog on a cron" | No worker/queue infra exists (backend is synchronous/inline by architecture); adds ops surface | TTL-cached refresh-on-read (e.g. revalidate if cache older than N hours on next request). |
| **Per-model rate-limit enforcement in-app** | "Stop users hitting free-model limits" | OpenRouter already enforces free-tier limits (≈20 rpm / 200 per day) and returns errors | Surface OpenRouter's rate-limit error gracefully; don't re-implement its limiter. |

---

## Feature Dependencies

```
Existing: [Auth (email/pw + anon Try-demo)]   [Threads]   [Chat tool-use loop]   [Config/Settings]
                  │                                │              │                      │
                  ▼                                │              │                      │
[OAuth PKCE connect flow] ──provisions──► [Encrypted key storage (RLS)]                  │
        │                                          │                                     │
        │                                          ├──reads──► [Key status indicator]    │
        │                                          │               │                     │
        ▼                                          │               ▼                     │
[OAuth success/fail/cancel states]                 │       [Disconnect / reconnect]      │
                                                   │                                     │
[Model picker] ◄──lists── [/models cache] ◄──refresh-on-read TTL──┐                      │
   │   │   │                                                       └──[Scheduled/auto refresh]
   │   │   └──derives──► [Free/paid tags] [ctx+price hints] [popularity/"new" marking]
   │   │
   │   └──selects──► [Per-thread model] ──column on──► [Threads]
   │   └──selects──► [Global default model] ──stored in──► [Settings page]
   │
   └──when paid model + no key──► [Key-gated trigger] ──launches──► [OAuth PKCE connect flow]

[Owner-key demo fallback (global flag)] ◄──needs──► [Config/Settings]
        │                                              ▲
        └──when no user key & flag ON──► uses owner key + restricted model
        └──surfaces──► [Obvious "demo mode" banner/badge]

[Chat loop] ──emits usage.cost inline──► [Per-message cost] ──sums──► [Per-thread cost rollup]
[User key] ──GET /api/v1/key──► [Balance display] ──threshold──► [Low-balance warning]

[Settings page] ──hosts──► [Key status/connect/disconnect] [Default model] [Theme toggle] [Profile]
[Theme toggle] ──persists──► per-user (DB or localStorage), Tailwind dark: variant
```

### Dependency Notes

- **OAuth flow → Encrypted key storage:** the only point of OAuth here is to obtain a key you then persist securely; storage must exist before connect is useful. Both attach to existing **auth** (the returned key must be bound to a `user_id`).
- **Model picker → /models cache → refresh:** the picker is only as good as its data; caching is required (400+ models, rate limits) and refresh keeps it current. Refresh should be TTL/refresh-on-read, not a new background worker (architecture is synchronous).
- **Key-gated trigger requires picker + OAuth + key status:** it sits at the intersection — it must know (a) the selected model needs a key, (b) the user has none, and (c) how to launch connect.
- **Per-thread model requires a Threads schema change** (add `model` column) and a **chat-loop change** (read thread.model instead of the single env-configured model). This is the main code-touch into existing systems.
- **Demo fallback requires the existing anonymous Try-demo auth + Config pattern;** the global flag belongs in the existing `pydantic-settings` `Settings`. The "demo mode" banner depends on the app knowing the request is running on the owner key.
- **Per-message cost depends on the chat loop forwarding the trailing `usage` SSE chunk** to the frontend — it's data already present, but the SSE event stream must expose it.
- **Balance/low-balance depends on the user's own key** (`GET /api/v1/key`); it is meaningless / shows owner data in demo mode, so gate it to connected users.
- **Conflicts:** Manual-key-paste conflicts with OAuth-only posture; browser key storage conflicts with encrypted-server-side storage; per-message model switching conflicts with per-thread model granularity and stable-model tool loops.

---

## MVP Definition

### Launch With (v1.2 core)

The minimum that delivers "users run their own models with near-zero-friction onboarding, demo still works."

- [ ] **OAuth PKCE connect flow + callback states** — the headline feature; without it BYOK doesn't exist.
- [ ] **Encrypted server-side key storage (RLS-scoped)** — required to hold what OAuth returns; security foundation of the milestone.
- [ ] **Key status indicator + disconnect/reconnect** — trust + rotation; cheap once storage exists.
- [ ] **Model picker with free/paid tags + search/filter** — the "options" half of "User Options & BYOK."
- [ ] **Sensible default model** — so chat works before any choice is made.
- [ ] **Key-gated model selection (triggers OAuth)** — ties picker + keys together; the moment of conversion.
- [ ] **Owner-key demo fallback (global flag, default off) + obvious demo banner** — keeps the public portfolio demo alive; protects owner spend.
- [ ] **Per-message cost display** — essentially free (`usage.cost` inline); core trust feature for spenders.
- [ ] **Balance display (connected users)** — `GET /api/v1/key`; answers "how much is left."
- [ ] **Settings/account page** — the home for key status, default model, theme, profile.
- [ ] **Theme toggle (Light/Dark/System), persisted** — baseline 2026 expectation, low cost.
- [ ] **Per-thread model selection (persisted)** — promoted into core: it's the practical payoff of multi-model and the natural place the picker lives; the schema/loop change is best done once, with the rest of the model work.

### Add After Validation (v1.2.x)

- [ ] **Scheduled/auto model-list refresh + "New" badge** — trigger: catalog staleness complaints or visibly missing recent models. TTL refresh-on-read first.
- [ ] **Popularity / "trending" marking + favorites** — trigger: picker testing shows choice paralysis at full catalog size.
- [ ] **Low-balance warning + per-thread cost rollup** — trigger: first "ran out mid-chat" report; both are cheap riders on existing balance/cost data.
- [ ] **Context-length + pricing hints inline** — trigger: users ask "which model fits a long manual?" Can ship with picker if budget allows (data is already loaded).

### Future Consideration (v2+)

- [ ] **Favorites/pinned reordering, keyboard nav in picker** — only at heavy multi-model usage.
- [ ] **Org/shared-key or team billing** — out of scope for a portfolio app; large surface.
- [ ] **Multi-provider native BYOK** — deliberately deferred; OpenRouter covers it.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| OAuth PKCE connect + callback states | HIGH | HIGH | P1 |
| Encrypted key storage (RLS) | HIGH (trust) | HIGH | P1 |
| Key status + disconnect/reconnect | MEDIUM | LOW | P1 |
| Model picker (free/paid + search) | HIGH | MEDIUM | P1 |
| Default model | MEDIUM | LOW | P1 |
| Key-gated selection (OAuth trigger) | HIGH | MEDIUM | P1 |
| Owner-key demo fallback + demo banner | HIGH (demo + cost safety) | MEDIUM | P1 |
| Per-message cost display | HIGH | LOW | P1 |
| Balance display | MEDIUM | LOW-MEDIUM | P1 |
| Settings/account page | MEDIUM | MEDIUM | P1 |
| Theme toggle (Light/Dark/System) | MEDIUM | LOW | P1 |
| Per-thread model (persisted) | HIGH | MEDIUM | P1 |
| Scheduled/auto model refresh + "New" | MEDIUM | MEDIUM | P2 |
| Popularity/trending marking | MEDIUM | MEDIUM | P2 |
| Low-balance warning | MEDIUM | LOW-MEDIUM | P2 |
| Context-length + price hints in picker | MEDIUM | LOW | P2 |
| Per-thread cost rollup | LOW-MEDIUM | LOW | P2 |
| Favorites / pinned models | LOW-MEDIUM | MEDIUM | P3 |

**Priority key:** P1 = must have for the milestone · P2 = should have, add when possible · P3 = nice to have / future.

---

## Competitor / Reference Feature Analysis

| Feature | T3 Chat | LibreChat / Open WebUI | OpenRouter's own UI | Our Approach |
|---------|---------|------------------------|---------------------|--------------|
| BYOK onboarding | BYOK per provider, key paste | Paste key per provider/endpoint | N/A (you're already in OpenRouter) | **OAuth PKCE only** — no paste; lowest friction, single provider |
| Model picker | Searchable, favorites, keyboard nav, pinned | Grouped by endpoint/provider, specs | Full catalog with rich filters/sort | Searchable + free/paid tags + (P2) trending/curated shortlist |
| Free vs paid | Free tier with select models | Whatever the keys allow | Pricing shown per model | Tag from `pricing == "0"` / `:free`; "Free only" filter |
| Cost surfacing | Usage limits by tier | Token counts, some cost | Per-request cost + balance | **Per-message `usage.cost` inline** (free) + balance via `/key` |
| Per-thread model | Per-conversation model selection | Per-conversation / preset | N/A | **Per-thread `model` column**, persisted |
| Demo / shared key | Free tier on shared infra | N/A (self-host) | N/A | **Owner-key fallback behind global flag**, prominent demo banner |
| Theme | Light/dark + custom themes | Light/dark/system | Light/dark | Light/Dark/System, persisted per user |

---

## Sources

- OpenRouter OAuth PKCE guide — https://openrouter.ai/docs/guides/overview/auth/oauth (HIGH)
- OpenRouter exchange auth code for key — https://openrouter.ai/docs/api/api-reference/o-auth/exchange-auth-code-for-api-key (HIGH)
- OpenRouter list models / fields — https://openrouter.ai/docs/api/api-reference/models/get-models (HIGH)
- OpenRouter get remaining credits (`/credits`, management key) — https://openrouter.ai/docs/api/api-reference/credits/get-credits (HIGH)
- OpenRouter API limits / `GET /api/v1/key` (per-key usage/limit/is_free_tier) — https://openrouter.ai/docs/api/reference/limits (HIGH)
- OpenRouter Usage Accounting (`usage.cost` inline, deprecated include flags) — https://openrouter.ai/docs/cookbook/administration/usage-accounting (HIGH)
- OpenRouter models overview (free models, `:free`, rate limits) — https://openrouter.ai/docs/guides/overview/models (HIGH)
- T3 Chat model picker / favorites / BYOK (UX conventions) — https://feedback.t3.chat/p/better-model-picker , https://t3.chat/ (MEDIUM)
- LibreChat model specs / selector grouping — https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/model_specs (MEDIUM)
- Open WebUI vs LibreChat (multi-provider BYOK landscape) — https://docs.openwebui.com/alternatives/librechat/ (MEDIUM)
- Freemium conversion / shared-key demo UX (general) — https://userpilot.com/blog/freemium-strategy/ (LOW)

---
*Feature research for: BYOK + model selection in an OpenRouter-backed LLM chat app*
*Researched: 2026-06-18*
