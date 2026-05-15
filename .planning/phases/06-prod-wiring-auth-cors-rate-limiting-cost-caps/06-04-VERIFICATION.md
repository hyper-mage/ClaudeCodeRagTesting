# 06-04 VERIFICATION — Supabase Auth URLs + OpenRouter cost guardrail

**Plan:** `06-04-PLAN.md` — Wave 3, manual dashboard work.
**Outcome:** ✅ Part A (Auth URLs) complete. ⚠️ Part B (cost guardrail trip) **partial** — externalized to backlog script (see Carry-forward).

---

## Part A — Supabase Auth URLs (D-12 / D-13) ✅

### Configuration applied (Supabase dashboard)

- **Site URL:** `https://boardgame-rag-prod.pages.dev`
- **Redirect URL allowlist:**
  - `https://boardgame-rag-prod.pages.dev/**`
  - `http://localhost:5173/**` (local dev preserved)

### Verification

| Check | Method | Result |
|---|---|---|
| Throwaway-email signup from prod URL | Incognito on `https://boardgame-rag-prod.pages.dev` | ✅ |
| Email confirmation link redirect target | Click link from inbox | ✅ Lands on `boardgame-rag-prod.pages.dev` (NOT `localhost`) |
| Chat works after fresh signup | Send "hi" → assistant streams response | ✅ Screenshot captured |
| Local dev signup still works | `http://localhost:5173/**` retained in allowlist | ✅ (not regressed — same Supabase project) |

Screenshot evidence kept locally by user (private-browsing window showing `boardgame-rag-prod.pages.dev/#` URL + working chat).

---

## Part B — OpenRouter cost guardrail (D-19 / D-20) ⚠️ Partial

### Observations vs plan

Plan assumed **OpenRouter "Usage Alerts"** with `$0.01` email threshold. As of 2026-05-14 the feature was renamed/replaced:

| Plan expectation | Reality (2026-05-14) | Impact |
|---|---|---|
| Usage Alerts | **Guardrails** (separate UX) | Naming-only; same intent |
| `$0.01` minimum threshold | **`$0.10` minimum** | Lower bound is 10× the plan target |
| Email-alert toggle | **Not present in UI** | Whether guardrail trip emails is unverified |
| `$1` top-up | **`$5` minimum** | Min top-up raised |

### What was done

1. **Top-up:** $5 (min). Stripe-charged.
2. **Guardrail set:** $0.10 / `mlynn808138@gmail.com` (account email).
3. **Fly secret swap to paid model:** `flyctl secrets set LLM_MODEL="openai/gpt-4o-mini" -a boardgame-rag-prod` — rolling update succeeded, machine `80e35ef6015d48` restarted.
4. **Burn attempt:** self + invited friends via throwaway accounts on `https://boardgame-rag-prod.pages.dev`. Total spend reached **$0.0105** (≈10.5% of guardrail).
5. **Decision:** bench remaining ~$0.0895 burn — externalize to a deterministic backlog script (see Carry-forward) rather than continue manual chatting.
6. **Fly secret reverted to `:free`:** `LLM_MODEL=openai/gpt-oss-120b:free`. Digest back to `870b2184e3cd2f97` (matches 06-03 baseline). Confirmed via `flyctl secrets list`.

### What was NOT verified (deferred)

- ❌ Guardrail trip behavior at threshold (does it block further calls? warn-only?)
- ❌ Email-on-trip delivery (whether OpenRouter emits any notification to account email)
- ❌ Time-to-email after trip

### Cost reference captured (≈)

- `openai/gpt-4o-mini` short-prompt chat ≈ `$0.005` / message
- $0.10 trip threshold ≈ 20 short-prompt chats from same key
- Per-IP / per-throwaway-account scaling did not measurably accelerate burn (LLM call cost is per token, not per account)

---

## Decisions / deviations from plan

1. **`LLM_MODEL` reverted to `:free` after partial burn.** No reason to keep paying while guardrail trip remains unverified. Defer remainder to scripted test.
2. **Guardrail trip externalized to backlog.** Cleanest deterministic test is a script: mint N throwaway JWTs (or reuse one), burn N×$0.006 against `gpt-4o-mini` via repeated chat calls, observe credits page + inbox. Plan/execute under v1.2.
3. **Email-alert acceptance criterion relaxed.** Plan D-19/D-20 assumed verifiable email at trip. Until guardrail script runs, treat the cost-cap surface as "configured + visible in OpenRouter dashboard" not "verified to email on trip". Document in milestone audit as known partial gate.
4. **Mobile UX bug discovered during friend-testing.** Out of scope for 06-04; routed to a new urgent phase (06-05 mobile-responsive-chat-layout). See Carry-forward.

---

## Verification matrix

| Gate | Status | Notes |
|---|---|---|
| Supabase Site URL = prod CF URL | ✅ | Throwaway signup confirmed |
| Supabase redirect allowlist includes prod + localhost | ✅ | Local dev preserved |
| Prod email confirm lands on prod (not localhost) | ✅ | Incognito throwaway test |
| OpenRouter $5 balance loaded | ✅ | Stripe top-up |
| OpenRouter cost guardrail configured at min threshold | ✅ | $0.10 (min available; was $0.01 in plan) |
| Fly secret swap to paid model + verify digest change | ✅ | gpt-4o-mini active during test, reverted to `:free` after |
| Guardrail TRIP behavior verified | ⚠️ deferred | Only $0.0105 of $0.10 burned manually; deferred to script |
| Guardrail email delivery verified | ⚠️ deferred | Threshold not reached; deferred to script |
| Fly secret restored to `:free` after test | ✅ | `LLM_MODEL` digest `870b2184e3cd2f97` |

---

## Files touched this plan

Configuration-only — no code commits required for Part A or Part B:

- Supabase dashboard: Site URL + Redirect URLs (no repo file)
- OpenRouter dashboard: $5 top-up + $0.10 guardrail (no repo file)
- Fly secrets: `LLM_MODEL` swap → revert (no repo file)

(Memory file added to user's auto-memory store for future reference: `reference_openrouter_guardrails.md` — captures the Guardrails-replaces-Alerts + $0.10-minimum + $5-top-up changes for v1.2 BYO-key planning.)

---

## Carry-forward

### Backlog

- **Guardrail trip verification script** (`backend/scripts/cost_guardrail_burn.sh` or similar): programmatically reach the configured OpenRouter guardrail by issuing N parallel chat requests against the paid model, watch credits page for delta + inbox for delivery email. Default `N` computed from current `gpt-4o-mini` cost reference (~20 short prompts ≈ $0.10). Will be planned + executed in v1.2.

### To v1.2

- **Multi-model picker** (already noted in 06-03-SUMMARY).
- **BYO-key foundation** (already noted in 06-03-SUMMARY).
- **Re-verify OpenRouter guardrail behavior** (email vs block) once script lands and trip is reproducible. Update memory `reference_openrouter_guardrails.md` accordingly.

### To 06-05 (new urgent phase)

- **Mobile-responsive chat layout.** Discovered during 06-04 friend-testing: `ThreadSidebar` is `w-64` always-visible, eats most of mobile viewport (~256px of 375px), chat unusable on mobile. Fix scope: hide sidebar below `md:` breakpoint, add hamburger toggle + drawer pattern. Files touched: `frontend/src/components/ThreadSidebar.tsx`, `frontend/src/pages/ChatPage.tsx`, possibly `frontend/src/components/ChatContainer.tsx`.
