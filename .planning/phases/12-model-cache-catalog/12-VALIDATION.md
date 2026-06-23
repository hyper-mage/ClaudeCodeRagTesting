---
phase: 12
slug: model-cache-catalog
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-23
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `12-RESEARCH.md` § Validation Architecture (verified against live OpenRouter API 2026-06-22).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 + pytest-asyncio 0.23.8 (`asyncio_mode=auto`) |
| **Config file** | `backend/pytest.ini` (`testpaths=tests`, `--strict-markers`, `integration` marker) |
| **Quick run command** | `cd backend && python -m pytest tests/test_model_catalog.py tests/test_models_api.py -x` |
| **Full suite command** | `cd backend && python -m pytest` |
| **Estimated runtime** | ~10–20 seconds (offline; outbound fetch monkeypatched) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_model_catalog.py tests/test_models_api.py -x`
- **After every plan wave:** Run `cd backend && python -m pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~20 seconds

---

## Per-Task Verification Map

> Task IDs assigned at planning (`12-NN-MM`). Rows below are requirement-level; the planner binds each to a concrete task.

| Req | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-----------------|-----------|-------------------|-------------|--------|
| MODEL-02 | `:free` suffix tagged free | — | N/A | unit | `pytest tests/test_model_catalog.py::test_free_by_suffix -x` | ❌ W0 | ⬜ pending |
| MODEL-02 | `prompt==0 AND completion==0` tagged free | — | N/A | unit | `pytest tests/test_model_catalog.py::test_free_by_zero_price -x` | ❌ W0 | ⬜ pending |
| MODEL-02 | `-1` sentinel NOT free, NOT mis-priced | T-12-V5 | malformed upstream data never crashes endpoint | unit | `pytest tests/test_model_catalog.py::test_sentinel_not_free -x` | ❌ W0 | ⬜ pending |
| MODEL-02 | malformed/missing pricing doesn't crash (defensive) | T-12-V5 | guarded parse, never blind `float()` | unit | `pytest tests/test_model_catalog.py::test_pricing_parse_guards -x` | ❌ W0 | ⬜ pending |
| MODEL-07 | per-Mtok math (`gpt-4o-mini` → 0.15/0.60) | — | N/A | unit | `pytest tests/test_model_catalog.py::test_price_per_mtok -x` | ❌ W0 | ⬜ pending |
| MODEL-07 | context_length surfaced; null-safe | — | N/A | unit | `pytest tests/test_model_catalog.py::test_context_length_nullsafe -x` | ❌ W0 | ⬜ pending |
| MODEL-03 | popularity rank from `POPULAR_MODELS`; absent → null | — | N/A | unit | `pytest tests/test_model_catalog.py::test_popularity_tagging -x` | ❌ W0 | ⬜ pending |
| MODEL-04 | stale (TTL lapsed/empty) triggers refresh; fresh model appears | — | N/A | unit (injected TTL=0 + monkeypatched fetch) | `pytest tests/test_model_catalog.py::test_refresh_when_stale -x` | ❌ W0 | ⬜ pending |
| MODEL-04 | within-TTL serves cache without fetch | — | N/A | unit | `pytest tests/test_model_catalog.py::test_serve_cached_within_ttl -x` | ❌ W0 | ⬜ pending |
| MODEL-04 | fetch failure during refresh serves stale (D-04) | T-12-V5 | availability preserved on upstream failure | unit | `pytest tests/test_model_catalog.py::test_serve_stale_on_fetch_failure -x` | ❌ W0 | ⬜ pending |
| MODEL-01 | `?free_only=true` filters server-side (D-02) | — | typed bool coercion | unit (route) | `pytest tests/test_models_api.py::test_free_only_filter -x` | ❌ W0 | ⬜ pending |
| MODEL-01 | empty cache populates on first read; never empty (D-05) | — | N/A | unit (route) | `pytest tests/test_models_api.py::test_first_request_populate -x` | ❌ W0 | ⬜ pending |
| config | `model_cache_ttl_seconds` default 86400 + env override | — | N/A | unit | `pytest tests/test_config.py::test_model_cache_ttl_default -x` | ❌ W0 (extend existing) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_model_catalog.py` — pure-function tests (tagging, Mtok math, popularity, refresh-if-stale with injected TTL + monkeypatched fetch). Covers MODEL-02/03/04/07.
- [ ] `backend/tests/test_models_api.py` — route-level tests (`?free_only`, first-request populate, serve-stale-on-failure). Covers MODEL-01/04 + D-02/D-04/D-05.
- [ ] Extend `backend/tests/test_config.py` — `model_cache_ttl_seconds` default + env override (existing file pattern).
- [ ] `backend/tests/fixtures/openrouter_models_sample.json` — small real-shape fixture (`gpt-4o-mini`, a `:free` model, an `openrouter/auto` `-1`-pricing model, one missing-pricing edge) so tests run offline without the live API.
- Framework install: none — pytest already present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Deploy seed runs against prod `.env.prod` and catalog is non-empty post-deploy | MODEL-01 / D-05 | Requires real Fly deploy + prod Supabase; first-request populate is the automated correctness guarantee | After deploy, `curl https://<prod>/api/models` returns >0 models; confirm `model_cache` row count > 0 in prod Supabase |
| Real new OpenRouter model appears after 24h TTL in prod | MODEL-04 | Real wall-clock TTL + live upstream change; the injected-TTL unit test is the automated proxy | Note a model absent today; after >24h, confirm it appears via `/api/models` (or force by setting `model_cache_ttl_seconds` low) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (catalog tests, api tests, config extension, fixture)
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
