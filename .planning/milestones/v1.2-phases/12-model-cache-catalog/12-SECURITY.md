---
phase: 12
slug: model-cache-catalog
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-23
---

# Phase 12 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Verified against implementation — every `mitigate` threat traced to a code/migration
> location; every `accept` threat recorded with its plan-authored rationale.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Upstream OpenRouter catalog → `model_cache` write path | Untrusted/partial upstream rows (a model may omit `name`, carry a `-1` price sentinel, or malformed pricing) cross into the service-role batch upsert | Public model metadata (id, name, pricing strings, context_length) — non-secret |
| Authenticated client (incl. Text-to-SQL tool) → `model_cache` table | Any logged-in client can attempt to read or write the catalog table directly via the anon/RLS-enforced path | Global non-secret catalog list (no per-user rows) |
| Frontend → `GET /api/models` | Auth-gated backend read seam; frontend never calls OpenRouter directly (Success Criterion #1) | Render-ready catalog (is_free, per-Mtok hints, popularity, raw pricing) |
| `model_catalog_service.fetch_catalog` → openrouter.ai | Outbound HTTP to a hardcoded public catalog URL; NO Authorization header sent | None outbound (no key); inbound = public catalog JSON |

---

## Threat Register

Threat IDs T-12-V5-01..04 appear in BOTH plan 12-01 and plan 12-04 against **different
components**; they are recorded as distinct register entries keyed by component (the
12-04 entries are the gap-closure / regression-hardening of the 12-01 surface).

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-12-V5-01 (12-01) | Denial of Service | `price_per_mtok` / `tag_is_free` / `build_model_response` (model_catalog_service.py) | mitigate | Defensive parse: `isinstance(per_token, str)` guard + `float()` in try/except + `<0`→None (price_per_mtok L58-77); `.get()` per field + `pricing or {}` (tag_is_free L80-92); `ctx if isinstance(ctx, int) else None` (build_model_response L109-141). Never raises on a hostile/partial row. Tests: test_pricing_parse_guards, test_sentinel_not_free, test_context_length_nullsafe. | closed |
| T-12-V5-02 (12-01) | Tampering (SSRF) | `fetch_catalog` outbound URL | accept | `CATALOG_URL` is a hardcoded module constant (model_catalog_service.py L36); no user input flows into the URL → no SSRF surface. | closed |
| T-12-INFO-01 (12-01) | Information Disclosure | `fetch_catalog` httpx call | mitigate | `httpx.get(CATALOG_URL, timeout=10)` (L50) sends NO `headers=`/Authorization argument (grep: only comment-level mentions of "Authorization"/"Bearer"); response body never logged (failure logs emit `type(exc).__name__` only). Test: test_fetch_catalog_sends_no_auth_header. | closed |
| T-12-V4-01 (12-02) | Tampering | `model_cache` write path (migration 030) | mitigate | Migration 030 (L36-45): `ENABLE ROW LEVEL SECURITY` + exactly ONE `FOR SELECT USING (true)` policy + ZERO INSERT/UPDATE/DELETE policy → RLS denies all client writes by default; only the service-role backend (`get_supabase()`) writes. Client/Text-to-SQL cannot poison the list. | closed |
| T-12-V4-02 (12-02) | Information Disclosure | `model_cache` read path | accept | Permissive `SELECT USING (true)` (migration 030 L39-41) exposes the catalog to any authenticated client. Catalog is a non-secret, globally-identical public list (no per-user rows, no secrets). Contrast user_api_keys which REVOKEs SELECT. | closed |
| T-12-V5-03 (12-03) | Tampering / Input Validation | `free_only` query param | mitigate | Route signature `free_only: bool = False` (routers/models.py L36) → FastAPI coerces/rejects non-bool; no raw string flows into a query. Filter runs server-side (L51-52). Test: test_free_only_filter. | closed |
| T-12-V5-04 (12-03) | Denial of Service | Refresh path serving upstream data through the route | mitigate | `refresh_if_stale` defensive parse + `httpx.get(..., timeout=10)` bound + serve-stale-on-failure (model_catalog_service.py L206-253) → a malformed upstream row never 500s; route returns 200 stale. Test: test_serve_stale_on_fetch_failure (route + service). | closed |
| T-12-V4-03 (12-03) | Information Disclosure | `GET /api/models` exposure | accept | Endpoint auth-gated via `Depends(get_user_id)` (routers/models.py L37); serves only the non-secret public catalog — no per-user or secret data. Frontend reads here only, never OpenRouter directly. | closed |
| T-12-V5-01 (12-04) | Denial of Service | `refresh_if_stale` batch upsert vs `name NOT NULL` | mitigate | `_to_cache_row` coalesces `model.get("name") or str(model.get("id") or "")` (model_catalog_service.py L197) so the served name is never NULL; migration 031 (`ALTER COLUMN name DROP NOT NULL`) removes the schema contradiction. A nameless upstream row degrades gracefully instead of failing the batch and emptying the cache. Tests: test_nameless_model_coalesces_to_model_id (constraint-aware stub), test_empty_catalog_guard_serves_stale, test_empty_and_failed_distinct_warning. | closed |
| T-12-V5-02 (12-04) | Tampering | Corrective migration 031 vs `model_cache` RLS | mitigate | Migration 031 is scoped to a SINGLE `ALTER TABLE model_cache ALTER COLUMN name DROP NOT NULL` (L29). Grep gate confirmed: zero `CREATE POLICY`/`DROP POLICY`/`FOR INSERT|UPDATE|DELETE`/`GRANT`/`REVOKE`. Inverted RLS posture from 030 is untouched; `on_conflict="model_id"` upsert preserved (L240) → no new write surface. | closed |
| T-12-V5-03 (12-04) | Spoofing / Information Disclosure | `fetch_catalog` auth coupling | mitigate | WR-05 regression test test_fetch_catalog_sends_no_auth_header asserts `fetch_catalog` sends NO Authorization header and smuggles no bearer/`sk-or-` in any header value; implementation `httpx.get(CATALOG_URL, timeout=10)` passes no headers (L50). Locks the D-05 "never couple the catalog to an owner key" decision. | closed |
| T-12-V5-04 (12-04) | Denial of Service | `model_cache_ttl_seconds` misconfiguration | mitigate | `model_cache_ttl_seconds: int = Field(default=86400, ge=0)` (config.py L51) → a negative TTL raises pydantic ValidationError at Settings init, failing loudly instead of silently hammering upstream on every read. Test: test_negative_ttl_rejected_loudly. | closed |
| T-12-V5-05 (12-04) | Information Disclosure | `model_cache` read path | accept | Permissive `SELECT USING (true)` exposes the catalog to any authenticated client. Non-secret, globally-identical public list (unchanged from T-12-V4-02). Migration 031 explicitly leaves RLS untouched. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-12-01 | T-12-V5-02 (12-01) | `fetch_catalog` targets a hardcoded constant URL (`https://openrouter.ai/api/v1/models`); no user input reaches the URL, so there is no SSRF surface to mitigate. | gsd-security-auditor (plan-authored disposition) | 2026-06-23 |
| AR-12-02 | T-12-V4-02 (12-02) / T-12-V5-05 (12-04) | `model_cache` uses a permissive `SELECT USING (true)` policy. The catalog is a non-secret, globally-identical public list with no per-user rows and no secrets — read exposure to any authenticated client is the intended design (mirror image of user_api_keys, which REVOKEs SELECT because it holds secrets). | gsd-security-auditor (plan-authored disposition) | 2026-06-23 |
| AR-12-03 | T-12-V4-03 (12-03) | `GET /api/models` serves only the non-secret public catalog. It is auth-gated via `Depends(get_user_id)` per codebase norm (A4), but the data exposed is per-user-agnostic and non-secret, so the read path carries no confidentiality risk. | gsd-security-auditor (plan-authored disposition) | 2026-06-23 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-23 | 13 | 13 | 0 | gsd-security-auditor |

Note: 13 register entries cover 11 unique threat IDs; T-12-V5-01..04 each appear twice
(plan 12-01/03 surface + plan 12-04 gap-closure) against distinct components and are
counted as distinct entries.

---

## Unregistered Flags

None. SUMMARY 12-03 `## Threat Flags` declares "None — no new security surface beyond
the plan's `<threat_model>`". SUMMARYs 12-01, 12-02, 12-04 introduce no `## Threat Flags`
section and no new attack surface (12-04 Threat Mitigations Confirmed re-states the
plan-authored T-12-V5-02 / T-12-V5-03 controls). No new entry points or write surfaces
appeared during implementation that lack a threat mapping.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-23
