---
phase: "08"
plan: "00"
status: complete
date: 2026-05-18
provisional: false
---

# Plan 08-00 — Wave 0 Scaffolding (COMPLETE)

## Status

- **Task 1 (anon JWT `aud` verification):** ✅ **CONFIRMED 2026-05-18**. Empirical anon JWT minted against prod Supabase project via REST POST `/auth/v1/signup` (apikey=anon). Decoded payload returns `aud="authenticated"`, `role="authenticated"` — matches Supabase documented default (see RESEARCH §Common Pitfalls Pitfall 1) and dashboard text "Anonymous users will use the `authenticated` role when signing in". No code change needed in `backend/auth.py` — provisional no-op path confirmed.
- **Task 2 (sample doc + credits):** ✅ Done. Commit: `22463f0`.
- **Task 3 (pytest scaffolding):** ✅ Done. Commit: `c89c4a2`.

## Confirmed Decision — Wave 1 No-Op Path Locked

Empirical decode 2026-05-18 against prod Supabase project confirms documented default:

> **Confirmed:** anon JWT `aud == "authenticated"`, `role == "authenticated"`.
>
> **→ Plan 08-01 `backend/auth.py:42` `audience="authenticated"` unchanged.**
>
> **Verification method:** REST POST `/auth/v1/signup` with empty body + anon-key apikey against prod project → returned `access_token` decoded at jwt.io → both claims read `authenticated`.

Conftest fixture default `_ANON_AUD_CLAIM = "authenticated"` in `backend/tests/conftest.py` (commit `c89c4a2`) matches empirical value — Wave 1 tests run against the correct claim.

## Artifacts Created (Tasks 2 + 3)

| Path | Size | Notes |
|------|------|-------|
| `data/sample-private-docs/dnd5e-quickref.md` | 311 lines, 13,725 B | CC-BY 4.0 attribution top + footer; required H2 sections present |
| `docs/CREDITS.md` | — | SRD 5.1 (CC-BY 4.0) + lucide-react (MIT); references quickref path |
| `backend/tests/conftest.py` | +67 lines | `anon_jwt`, `permanent_jwt`, `seed_sample_doc_path` fixtures appended |
| `backend/tests/test_demo_bootstrap.py` | new, 38 lines | 1 real test (PASSES) + 3 Wave 1 skip stubs |
| `backend/tests/test_anon_cleanup.py` | new, 21 lines | 3 Wave 1 skip stubs |
| `backend/tests/test_auth_anon.py` | new, 17 lines | 2 Wave 1 skip stubs |
| `backend/tests/test_chat_retry.py` | new, 17 lines | 2 Wave 1 skip stubs |

## Pytest Collection Proof

```
$ cd backend && venv/Scripts/python -m pytest tests/test_demo_bootstrap.py tests/test_anon_cleanup.py tests/test_auth_anon.py tests/test_chat_retry.py --collect-only -q
... (11 tests across 4 files, 0 collection errors)
11 tests collected in 0.10s

$ cd backend && venv/Scripts/python -m pytest tests/test_demo_bootstrap.py::test_sample_doc_file_exists -x
... PASSED
1 passed in 0.34s

$ cd backend && venv/Scripts/python -m pytest --collect-only -q | tail -3
... 138 tests collected in 3.96s  (no regression)
```

## Files Committed

- `22463f0` feat(08-00): sample D&D 5e quickref + CREDITS attribution (Task 2)
- `c89c4a2` test(08-00): pytest scaffolding — conftest fixtures + 4 stub files (Task 3)
- `43be596` docs(08-00): provisional SUMMARY (later upgraded to complete on 2026-05-18)
