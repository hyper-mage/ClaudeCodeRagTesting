---
phase: 3
slug: prod-supabase-project
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-28
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend, existing) + bash verify scripts (ops) |
| **Config file** | backend/pytest.ini or pyproject.toml (existing) |
| **Quick run command** | `bash scripts/verify_prod_supabase.sh` |
| **Full suite command** | `cd backend && pytest tests/ -q` |
| **Estimated runtime** | ~30s verify script, ~60s pytest |

---

## Sampling Rate

- **After every task commit:** Run `bash scripts/verify_prod_supabase.sh` (where applicable to ops tasks)
- **After every plan wave:** Run full verify script + any seed-touching pytest
- **Before `/gsd:verify-work`:** Verify script must pass against prod, seed count ≥10
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | DEPLOY-03 | ops verify | `bash scripts/verify_prod_supabase.sh` | ❌ W0 | ⬜ pending |

*Filled by planner. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/verify_prod_supabase.sh` — checks pgvector enabled, migration count match, `documents` bucket exists, public seed count ≥10
- [ ] `.gitignore` patch — `.env*` pattern before any `.env.prod` is created

*All other behaviors verified via manual CLI run + the verify script.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Prod Supabase project creation | DEPLOY-03 SC-1 | Browser action on supabase.com dashboard, no CLI primitive | Create project, enable pgvector via SQL editor, capture URL + anon + service-role keys |
| Secrets captured in password manager | DEPLOY-03 SC-5 | Out-of-band — secrets never on disk in repo | Confirm 1Password (or equivalent) entry exists with prod URL + both keys; `.env.prod` exists locally only and is gitignored |
| `supabase db push` against linked prod project | DEPLOY-03 SC-2 | Interactive auth + project link, one-time | Run `supabase login`, `supabase link --project-ref <ref>`, `supabase db push`; capture output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers verify script + .gitignore patch
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
