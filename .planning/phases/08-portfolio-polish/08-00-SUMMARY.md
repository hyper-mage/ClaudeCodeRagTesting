---
phase: "08"
plan: "00"
status: partial
date: 2026-05-17
provisional: true
---

# Plan 08-00 — Wave 0 Scaffolding (PARTIAL — Task 1 PENDING)

## Status

- **Task 1 (anon JWT `aud` verification):** ⏸ **PENDING USER ACTION**. Supabase anon sign-ins toggled ON in prod (user confirmed 2026-05-17). User has not yet decoded a minted anon JWT to report empirical `aud` claim value.
- **Task 2 (sample doc + credits):** ✅ Done. Commit: `22463f0`.
- **Task 3 (pytest scaffolding):** ✅ Done. Commit: `c89c4a2`.

## Provisional Decision Used by Downstream Wave 1 Plans

Until Task 1 resume signal lands, downstream plans (08-01 in particular) assume the **no-op path**:

> **Provisional assumption:** anon JWT `aud == "authenticated"` (matches Supabase documented default — see RESEARCH §Common Pitfalls Pitfall 1).
>
> **→ Plan 08-01 keeps `backend/auth.py` line 42 `audience="authenticated"` unchanged.**
>
> **Risk:** if Task 1 resume signal reports `aud == "anon"` or any other value, Plan 08-01 must widen to `audience=["authenticated", "anon"]` per RESEARCH Pitfall 7. One-line patch + re-run of `test_auth_anon.py`.

This is consistent with conftest fixture default: `_ANON_AUD_CLAIM = "authenticated"` in `backend/tests/conftest.py` (Plan 08-00 Task 3 output, commit `c89c4a2`).

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

## When Task 1 Resume Signal Arrives

1. If `aud == "authenticated"`: this SUMMARY upgrades to `status: complete`, `provisional: false`. No code change needed.
2. If `aud != "authenticated"`:
   - Patch `_ANON_AUD_CLAIM = "<reported value>"` in `backend/tests/conftest.py`.
   - Plan 08-01 widens `audience=["authenticated", "<reported value>"]` in `backend/auth.py`.
   - Re-run `pytest tests/test_auth_anon.py -x` to confirm.
   - Update this SUMMARY with the resolved value + remove `provisional: true` marker.

## Files Committed

- `22463f0` feat(08-00): sample D&D 5e quickref + CREDITS attribution (Task 2)
- `c89c4a2` test(08-00): pytest scaffolding — conftest fixtures + 4 stub files (Task 3)
