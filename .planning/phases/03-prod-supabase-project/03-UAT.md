---
status: complete
phase: 03-prod-supabase-project
source:
  - 03-01-SUMMARY.md
  - 03-02-SUMMARY.md
started: 2026-05-03T00:00:00Z
updated: 2026-05-03T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test (backend against prod)
expected: Stop any running backend. From a fresh shell, start backend pointing at prod via `ENV_FILE=.env.prod`. Server boots without errors and a basic API call returns live data from prod Supabase.
result: pass
note: server booted clean against prod; /api/threads returned 401 (auth gate) confirming server alive + auth middleware engaged

### 2. Verify Harness Against Prod
expected: Run `& "C:\Program Files\Git\bin\bash.exe" -c "ENV_FILE=.env.prod bash scripts/verify_prod_supabase.sh --include-seed"`. Output shows 10/10 PASS and ends with `VERIFY OK`.
result: pass
note: 10/10 PASS — VERIFY OK. All schema + seed checks green.

### 3. Default KB Visible in App Against Prod
expected: Start full stack (frontend + backend) with backend pointing at prod via `ENV_FILE=.env.prod`. Log in, navigate to chat, ask "what board games are available?" or browse the documents page. App returns/lists the 10 seeded board games (Catan, Ticket to Ride, Pandemic, Carcassonne, 7 Wonders, Codenames, Azul, Splendor, Dominion, Wingspan).
result: pass
note: KBs visible, chat returns correct output. Prereqs found: (1) backend `$env:ENV_FILE=".env.prod"` (not `../.env.prod` — config.py prepends backend/..); (2) frontend `npm run dev -- --mode prod` so Vite loads VITE_ vars from `.env.prod`; (3) prod auth.users empty — created test user via Supabase dashboard. Backlog 999.1 logged: chat empty-state UX silent no-op when no threads.

### 4. Supabase CLI Unlinked
expected: Run `supabase status` (or check that `supabase/.temp/project-ref` does not exist). CLI reports no project linked. Day-to-day CLI commands cannot accidentally hit prod.
result: pass
note: `supabase/.temp/project-ref` absent. CLI not linked.

### 5. 1Password Entry Holds 6 Fields
expected: Open password manager → entry `Supabase — boardgame-rag-prod`. Confirm 6 fields present and match prod values: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, DB_PASSWORD, PROJECT_REF, DATABASE_URL.
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
