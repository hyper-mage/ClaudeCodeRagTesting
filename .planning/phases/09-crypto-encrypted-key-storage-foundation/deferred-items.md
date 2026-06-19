# Deferred Items — Phase 09

Out-of-scope discoveries logged during execution (NOT fixed here per executor SCOPE BOUNDARY).

## D-09-A: `SET LOCAL role` rejected inside SECURITY DEFINER on dev Postgres (PRE-EXISTING)

- **Found during:** Plan 09-03 Task 2 (live SEC-02 probe against dev).
- **Symptom:** A legitimate `select id from threads limit 1` driven through `execute_sql` against the dev Supabase project fails with Postgres `42501: cannot set parameter "role" within security-definer function`.
- **Root cause:** `execute_readonly_query` sets `SET LOCAL role = 'authenticated'` (migration 015 line 32) to establish the RLS context. This dev Postgres instance/version forbids `SET LOCAL role` inside a `SECURITY DEFINER` function. The line is **identical** in migration 015 and migration 026 — migration 026 (Phase 9) copied it verbatim (confirms RESEARCH Assumption A3: no drift introduced).
- **Why deferred (not a Phase 9 regression):**
  - The error originates at a line untouched by Phase 9 — it pre-dates this milestone (RPC built in v1.0 migration 015) and is documented in `.planning/codebase/CONCERNS.md` as the RLS-enforcement mechanism.
  - It is NOT the SEC-02 allowlist gate. The allowlist (migration 026) correctly **allowed** `threads` through — the query passed Gate 2 (no `non-allowlisted table` exception) and only failed deeper at the role switch. So migration 026 did not regress the legitimate query path at the layer it touches.
  - Fixing it would change the RPC's RLS-context strategy (e.g. `SET LOCAL ROLE` vs `SET ROLE`, or relying on `request.jwt.claim.sub` + GUC alone) — an architectural decision (Rule 4) about how RLS is enforced inside the SECURITY DEFINER body, out of scope for this dev-apply/verify plan.
- **Impact / next step:** This affects whether ANY Text-to-SQL query returns rows on this dev Postgres, independent of BYOK. Should be triaged separately (likely Phase 11 chat-loop seam, or a dedicated RPC-fix plan). Recommend: verify the same probe against prod at deploy (D-05) and decide whether to switch the RLS-context approach. Until then the Text-to-SQL tool's *execution* path may be non-functional on this dev instance — but the SEC-02 lockdown (the goal of Phase 9) is unaffected and proven.
