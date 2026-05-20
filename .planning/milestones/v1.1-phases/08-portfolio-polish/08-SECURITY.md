---
phase: 8
slug: portfolio-polish
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-20
---

# Phase 8 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Built from artifacts (State B) — no prior SECURITY.md. Threat register aggregated from the `<threat_model>` blocks of all 8 phase PLAN files (08-00 through 08-07). `register_authored_at_plan_time: true` — every plan carried a formal STRIDE register, so this audit verifies mitigations rather than retroactively constructing one.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Client → backend JWT verification | Untrusted JWT bearer tokens arrive at `get_user_id`; verifier must reject forged / wrong-audience / expired tokens. | Supabase JWT (anon + permanent) |
| Anonymous client → /api/demo/bootstrap | Unauthenticated visitors mint anon JWTs freely; endpoint must be rate-limited + bounded-work + idempotent. | Anon JWT, seed writes |
| Service-role admin client → auth.users delete | Cascade delete is service-role privileged; cleanup must filter strictly on is_anonymous + age. | User rows, storage objects |
| Client → /api/threads/{id}/messages?retry=true | Untrusted retry flag from browser; backend must not trust it beyond skipping one DB insert. | Retry flag, message rows |
| Browser → Sentry (caught exception) | `Sentry.captureException` must pass through the PII-scrub `beforeSend` in `lib/sentry.ts`. | Error events |
| Recorded media → public repo | Screenshots + GIF committed to a public repo are world-readable forever; PII in any frame is irretrievable. | PNG / GIF assets |
| README badges → shields.io / UptimeRobot | Browsers fetch badge SVGs at render time; badge hosts are the trust anchor. | Uptime %, last-commit date |
| GitHub repo visibility | Last-commit badge requires a public repo; flipping to public exposes repo content at HEAD. | Repo source |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-08-01 | Spoofing | `backend/auth.py` JWT verifier (anon `aud` claim) | mitigate | Empirical decode confirmed anon `aud="authenticated"` — matches existing `audience="authenticated"`; no widening needed. 4 unit tests in `test_auth_anon.py` (anon-accepted, permanent-accepted, invalid-aud-rejected, missing-sub-rejected). | closed |
| T-08-W0-LIC | Tampering / Compliance | `data/sample-private-docs/dnd5e-quickref.md` | mitigate | Verbatim CC-BY 4.0 attribution block present in the doc and in `docs/CREDITS.md` (grep-confirmed). | closed |
| T-08-01-LEAK | Information Disclosure | JWT verifier error responses | accept | 401 "Invalid token" detail does not leak claim values; behavior unchanged. | closed |
| T-08-02 | Denial of Service / Resource leak | /api/demo/bootstrap + cleanup loop | mitigate | `@limiter.limit("5/minute")` on bootstrap (`demo.py:33`); cleanup bounded to one ≤100-user page (`demo_service.py:159`); idempotency guard skips re-seed (`demo_service.py:72-81`). | closed |
| T-08-02-PERM | Elevation of Privilege | /api/demo/bootstrap called by permanent user | mitigate | `is_anonymous` check via `db.auth.admin.get_user_by_id` returns `{seeded: false}` no-op for permanent users (`demo.py:50`). | closed |
| T-08-02-FK | Tampering / Integrity | auth.users delete without ON DELETE CASCADE | mitigate | `_cascade_delete_user_data` child-first deletes: document_chunks → documents → folders → messages → threads (`demo_service.py:205-209`); storage prefix removed first. | closed |
| T-08-02-LEAK | Information Disclosure | Cleanup logs include user UUIDs | accept | UUIDs stay server-side; Sentry is frontend-only per Phase 7 PII contract. | closed |
| T-08-02-LOOP | Tampering / Integrity | One bad user aborts the purge loop | mitigate | Per-user try/except around cascade-delete + delete_user; logs warning and continues (`demo_service.py:164-169`). | closed |
| T-08-03 | Tampering / Integrity (data layer) | chat.py retry — duplicate assistant row | mitigate | Retry-aware cleanup deletes prior assistant row before re-insert; verified live in UAT item 10 (exactly 1 user + 1 assistant row post-retry). | closed |
| T-08-03-DOS | Denial of Service | Retry storms drain LLM provider | accept | User-driven retry only (no auto-retry, D-07); Phase 6 SEC-04 per-user rate-limit still applies; Retry disabled while streaming. | closed |
| T-08-03-SPOOF | Spoofing | Retry flag manipulated to delete unrelated rows | mitigate | Delete chain scoped by `thread_id` + `user_id` + `role='assistant'` (`chat.py:501-510`) — cannot reach across users or threads. | closed |
| T-08-03-USER | Tampering | User-message duplication on retry | mitigate | `if not retry:` guard around user-message insert (`chat.py:526`); prior user row preserved on retry. | closed |
| T-08-04-PII | Information Disclosure | `Sentry.captureException` in useChat catch block | mitigate | Reuses Phase 7 `lib/sentry.ts` `beforeSend` PII scrub (`sentry.ts:36`); useChat makes zero `Sentry.setUser` calls (grep-confirmed) — no anon UUID leak. | closed |
| T-08-04-XSS | Tampering / Injection | ErrorMessageBubble body copy | accept | Locked static string literal, not user input; no `dangerouslySetInnerHTML`; React auto-escapes. | closed |
| T-08-04-RETRY-DOS | Denial of Service | Retry button | mitigate | `disabled={isStreaming}` on the button; `retryLastUserMessage` early-returns while streaming; Phase 6 SEC-04 rate-limit applies. | closed |
| T-08-04-ANON-LEAK | Information Disclosure | Demo pill exposes anon-mode status visually | accept | Anon status is non-sensitive; visible pill prevents reviewer confusion; tooltip discloses 7-day cleanup. | closed |
| T-08-04-COPY | Information Disclosure | Error messages leak provider names or HTTP codes | mitigate | Error copy audited: "The assistant ran into a problem…" / "The assistant didn't respond…" — no provider names, no HTTP codes (grep-confirmed; only Tailwind shade classes matched the numeric regex). | closed |
| T-08-05-SSRF | Information Disclosure | shields.io badge endpoints fetched at render time | accept | shields.io is the standard portfolio badge host; only documented public endpoints used, no untrusted query params. | closed |
| T-08-05-STALE | Information Disclosure | README documents prod URL + deploy steps | accept | URLs sourced from STATE.md at write time; no secret material in README; README is re-edited per major change. | closed |
| T-08-05-PII | Information Disclosure | Screenshots may include PII | mitigate | All 4 screenshots captured from a fresh anon-demo session; visual no-PII review passed in UAT (no email/UUID/real-user content). | closed |
| T-08-06-PII | Information Disclosure | Screenshots + hero GIF could include real user PII | mitigate | All capture from anon-demo session; visual review confirmed no JWT/email/UUID in any frame. | closed |
| T-08-06-LIC | Tampering / Compliance | Assets could show third-party copyrighted board-game art | mitigate | Public KB content is text-only (own-words summaries); sample doc is CC-BY 4.0; no third-party images/trademarks captured. | closed |
| T-08-06-OVERSIZE | Availability | Oversized assets bloat repo clone + GitHub bandwidth | mitigate | Size caps verified: architecture.png 177 KB (≤500), screenshots 14–136 KB each (≤200), hero.gif 1.1 MB (≤5 MB). | closed |
| T-08-07-SSRF | Information Disclosure | shields.io badge endpoints | accept | Standard badge provider; documented public endpoints only, no user-controlled query params. | closed |
| T-08-07-UR-LEAK | Information Disclosure | UptimeRobot badge reveals uptime % | accept | A single uptime percentage is non-sensitive metadata; narrower surface than a public status page (Phase 7 carve-out preserved). | closed |
| T-08-07-STALE | Tampering / Integrity | Badge SVG cached stale by GitHub Camo proxy | accept | Camo staleness is a few hours at most; acceptable for a portfolio README. | closed |
| T-08-07-VISIBILITY | Information Disclosure | Flipping repo to public for the last-commit badge | mitigate | Developer confirmed visibility before flipping (USER-3, explicit step); owner email redacted at HEAD (`512f181`) before the flip. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-08-01 | T-08-01-LEAK | 401 error detail does not leak claim values; pre-existing behavior. | hyper-mage | 2026-05-20 |
| AR-08-02 | T-08-02-LEAK | Cleanup logs with user UUIDs stay server-side; Sentry is frontend-only. | hyper-mage | 2026-05-20 |
| AR-08-03 | T-08-03-DOS | User-driven retry only; Phase 6 SEC-04 rate-limit caps per-user RPM. | hyper-mage | 2026-05-20 |
| AR-08-04 | T-08-04-XSS | Locked static string; React auto-escapes; no raw HTML injection. | hyper-mage | 2026-05-20 |
| AR-08-05 | T-08-04-ANON-LEAK | Anon-mode status is non-sensitive; pill aids reviewer clarity. | hyper-mage | 2026-05-20 |
| AR-08-06 | T-08-05-SSRF | shields.io is the standard badge host; SSRF is the host's responsibility. | hyper-mage | 2026-05-20 |
| AR-08-07 | T-08-05-STALE | No secrets in README; URLs re-edited per major change. | hyper-mage | 2026-05-20 |
| AR-08-08 | T-08-07-SSRF | shields.io documented public endpoints only; no user-controlled params. | hyper-mage | 2026-05-20 |
| AR-08-09 | T-08-07-UR-LEAK | Single uptime % is non-sensitive; narrower than a public status page. | hyper-mage | 2026-05-20 |
| AR-08-10 | T-08-07-STALE | GitHub Camo badge cache staleness (hours) is acceptable for a portfolio. | hyper-mage | 2026-05-20 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-20 | 27 | 27 | 0 | /gsd:secure-phase (inline audit) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-20
