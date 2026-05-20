# Phase 4: Deploy Backend to Fly.io - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 04-deploy-backend-to-fly-io
**Areas discussed:** Secrets loading flow, CORS placeholder strategy, Docling model cache volume, Smoke test + app/region lock-in

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Secrets loading flow | Manual `flyctl secrets set` per key vs `flyctl secrets import < .env.prod` bulk vs prompted script | ✓ |
| CORS placeholder strategy | Phase 5 not deployed — what goes in CORS_ALLOWED_ORIGINS now? | ✓ |
| Docling model cache volume | Mount Fly volume on `/home/appuser/.cache/docling` vs rely on baked-in image cache only | ✓ |
| Smoke test + app/region lock-in | Reuse `docker_smoke.sh` vs new `fly_smoke.sh` vs curl-by-hand; confirm app name + region | ✓ |

**User's choice:** All four selected.

---

## Secrets loading flow

| Option | Description | Selected |
|--------|-------------|----------|
| Bulk import .env.prod | `flyctl secrets import < .env.prod` — single command, atomic, reuses Phase 3 .env.prod | ✓ |
| Per-key flyctl set | `flyctl secrets set KEY=value` for each — more typing, individual audit trail, machine restart per key | |
| Shell wrapper script | Commit `backend/scripts/fly_secrets_set.sh` reading from 1Password CLI / .env.prod | |

**User's choice:** Bulk import .env.prod
**Notes:** Captured as D-04. Triggers single machine restart vs N. Still need filter to strip VITE_* keys before import (D-05).

---

## CORS placeholder strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Localhost-only placeholder | `CORS_ALLOWED_ORIGINS=http://localhost:5173` — backend boots, SSE testable from local browser | ✓ |
| Empty string | Empty value falls back to Settings default `["http://localhost:5173"]` (Phase 1 D-02) | |
| Guessed pages.dev URL | Pre-set `https://boardgame-rag.pages.dev` based on expected CF Pages name | |

**User's choice:** Localhost-only placeholder
**Notes:** Captured as D-07. Explicit value preferred over relying on default fallback so `flyctl secrets list` is unambiguous. Phase 5 will overwrite (D-08).

---

## Docling model cache volume

| Option | Description | Selected |
|--------|-------------|----------|
| No volume | Models baked into image (Phase 2 D-06); suspend preserves process memory | ✓ |
| Mount 1GB volume on /home/appuser/.cache/docling | Persists across full machine restart; free tier includes 3GB volumes | |

**User's choice:** No volume
**Notes:** Captured as D-09. Re-evaluation deferred to v1.2+ per REQUIREMENTS.md Future Requirements item.

---

## Post-deploy smoke test approach

| Option | Description | Selected |
|--------|-------------|----------|
| New fly_smoke.sh against Fly URL | Commit `backend/scripts/fly_smoke.sh` taking `$FLY_URL`; polls health, runs SSE chat, asserts streamed chunks | ✓ |
| Reuse docker_smoke.sh w/ URL flag | Generalize Phase 2 script to accept target URL | |
| Curl-by-hand checklist | Document curl commands in PLAN/SUMMARY, run interactively | |

**User's choice:** New fly_smoke.sh against Fly URL
**Notes:** Captured as D-13. Avoids the docker_smoke ingestion step polluting prod Storage.

---

## Fly app name + region final lock-in

| Option | Description | Selected |
|--------|-------------|----------|
| Match Phase 3 exactly | App `boardgame-rag-prod`, region `iad` | ✓ |
| Different app name | Pick alternate name | |
| Different region | Override `iad` | |

**User's choice:** Match Phase 3 exactly
**Notes:** Captured as D-01/D-02. `bgkb-rag-prod` documented as fallback if global Fly name collision (D-01).

---

## fly.toml location

| Option | Description | Selected |
|--------|-------------|----------|
| Repo root | Same dir as Dockerfile (Phase 2 D-10) | ✓ |
| backend/ subdir | Requires `--config` + `--dockerfile` flags | |

**User's choice:** Repo root
**Notes:** Captured as D-03.

---

## Where document keep-warm toggle

| Option | Description | Selected |
|--------|-------------|----------|
| Comment in fly.toml only | Single commented line under `[http_service]` above active `min_machines_running = 0` | ✓ |
| fly.toml comment + README mention | Both — README §Deployment notes the toggle | |

**User's choice:** Comment in fly.toml only
**Notes:** Captured as D-12. README pass owned by Phase 8.

---

## fly_smoke.sh auth — JWT for SSE chat

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse docker_smoke.sh helper | Extract JWT-fetch into sourceable helper, both smokes consume it | ✓ |
| Inline in fly_smoke.sh | Duplicate JWT login block | |
| Manual: paste JWT as arg | User pastes token, runs `fly_smoke.sh <jwt>` | |

**User's choice:** Reuse docker_smoke.sh helper
**Notes:** Captured as D-14. DRY across both smokes; modifies docker_smoke.sh too (function extraction only, no behavior change).

---

## Claude's Discretion

- Exact `fly.toml` formatting (TOML key order, comment density, optional sections like `[deploy]`).
- Filter mechanism for stripping VITE_* keys from `.env.prod` before `flyctl secrets import`.
- `fly_smoke.sh` health-poll cadence (2s / 5s / exponential).
- Shared-helper file location (`backend/scripts/_lib/get_test_jwt.sh` vs `backend/scripts/_get_test_jwt.sh`).
- Whether to pre-create the Fly app via `flyctl apps create` discrete task vs single `flyctl launch --no-deploy --copy-config` invocation.

## Deferred Ideas

- Fly volume for Docling cache (v1.2+).
- CI-driven `fly deploy` (Phase 8 or later).
- README + deploy badge (Phase 8).
- OBS-04 Supabase reachability in `/api/health` (Phase 7).
- Rate limit / max-iter / spend cap (Phase 6).
- Real prod CORS origin (Phase 5 overwrites).
- `min_machines_running=1` keep-warm enablement (toggle off until justified).
