# Phase 10: OAuth PKCE — Backend Exchange + Frontend Connect - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 10-oauth-pkce-backend-exchange-frontend-connect
**Areas discussed:** Connect surface scope, Status indicator, Callback + return UX, Disconnect / reconnect UX

---

## Connect surface scope

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal /settings stub | Real /settings route now, key connect/status/disconnect only; P14 grows it. No throwaway, no scope creep. | ✓ |
| Temporary nav button | Connect button + badge in existing nav, no dedicated page. Fastest, throwaway. | |
| Build full Settings page now | Complete SettingsPage shell — pulls P14 scope forward. | |

**User's choice:** Minimal /settings stub
**Notes:** Real testable route that Phase 14 extends, rather than throwaway UI or pulling later scope forward.

### Entry point (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Gear in IconSidebar | Settings/gear entry → /settings; status on that page only. | |
| Gear + chat-header dot | Settings gear PLUS persistent connected/not dot in chat header. | ✓ |
| You decide | Planner picks following nav conventions. | |

**User's choice:** Gear + chat-header dot
**Notes:** Folds the easy half of Pitfall 13's always-visible key-state signal into P10; full state machine stays in P14.

---

## Status indicator

| Option | Description | Selected |
|--------|-------------|----------|
| Masked key tail + date | Backend captures masked hint at exchange (e.g. sk-or-v1-…wXyZ, last 4) + connected-since date; small non-secret label column. | ✓ |
| Generic 'Connected' + date | 'OpenRouter connected ✓' + date, no key-derived chars. | |
| OpenRouter label if returned | Use OpenRouter's assigned key label if exchange returns one, else generic. | |

**User's choice:** Masked key tail + date
**Notes:** Lets users confirm which key without exposing the secret. Researcher/planner to confirm whether the Phase 9 user_api_keys table has a masked-label + connected_at column or needs one added.

---

## Callback + return UX

| Option | Description | Selected |
|--------|-------------|----------|
| Spinner → auto-return | 'Connecting…' spinner during exchange → auto-redirect to /settings (Connected) + success toast. | ✓ |
| Success screen + Continue | Dedicated 'Connected!' screen with manual Continue button. | |
| You decide | Planner picks rendering + landing. | |

**User's choice:** Spinner → auto-return (happy path)
**Notes:** Fast, no extra click.

### Failure path (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Inline error + retry | Callback page shows 'Couldn't connect — try again' + Retry/Back button; sk-or scrubbed before log/Sentry. | ✓ |
| Redirect + error toast | Auto-redirect to /settings with error toast. | |
| You decide | Planner picks, keeping sk-or scrub. | |

**User's choice:** Inline error + retry
**Notes:** Recoverable, stays on the route. Hard-refresh (verifier still in sessionStorage) is the SUCCESS path, not a failure.

---

## Disconnect / reconnect UX

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm dialog | 'Disconnect OpenRouter? You'll need to reconnect to chat with your own key.' → DELETE → not-connected + Connect button. | ✓ |
| Immediate + undo toast | One-click disconnect with Undo toast (undo is misleading — can't restore deleted key). | |
| You decide | Planner picks following confirm/toast conventions. | |

**User's choice:** Confirm dialog
**Notes:** Guards an action that stops chat (demo-fallback OFF by default). Reconnect = re-run Connect; exchange upserts and overwrites the row (one key per user).

---

## Claude's Discretion

- Exact endpoint/handler signatures, `openrouter_service.exchange_code` shape.
- Masked-label / `connected_at` column names + migration filename (if a follow-on migration is needed).
- `lib/pkce.ts` helper API, callback route guard (public vs protected), spinner/toast/confirm-dialog component choices.

## Deferred Ideas

- Full "Demo vs Your key (balance) vs No key" always-visible state machine + mid-chat 401/402/403 recovery (Pitfall 13 full scope) — Phase 14.
- `GET /api/keys/balance` OpenRouter balance proxy — Phase 14 (COST-02).
- Key-gated model selection launching OAuth inline + resume-on-return — Phase 15 (KEY-05).
- Backend `sk-or` log/SSE scrub + LangSmith `wrap_openai` gate — Phase 11 (backend half of SEC-01).
