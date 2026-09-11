# Model Catalog Operations

How the model picker stays current — what updates itself, what needs a human, and the command for each.

The catalog is **not** seeded like the public KB. It pulls from the live OpenRouter API on a lazy 24h cycle. There is one hand-maintained piece (the fallback ranking list) and everything else takes care of itself.

---

## How it works

| Piece | Location | Role |
|---|---|---|
| Catalog rows | `model_cache` table (migration 030) | Every model the picker can show. Holds the full upstream object in `raw`. |
| Refresh trigger | `refresh_if_stale` — `backend/services/model_catalog_service.py:311` | Lazy, read-triggered, 24h TTL. No scheduler. |
| TTL knob | `model_cache_ttl_seconds` — `backend/config.py:51` | Default 86400. Env override `MODEL_CACHE_TTL_SECONDS`. |
| AA ranking | `aa_ranking` — `backend/services/model_catalog_service.py:142` | **Primary** popularity source. Reads `benchmarks.artificial_analysis.intelligence_index`. |
| Rank cap | `AA_RANK_LIMIT` — `backend/services/model_catalog_service.py:49` | Bounds how many models land in Popular. Default 12. |
| Fallback list | `POPULAR_MODELS` — `backend/config.py:78` | **Hand-maintained.** Covers models with no AA score. |
| Warm-up seed | `backend/scripts/seed_model_cache.py` | Optional. Force-refresh / post-deploy warm. |

The short version: **ranking updates itself, the fallback list does not.**

---

## What updates itself

A new model ships on OpenRouter → the next `GET /api/models` read after the 24h TTL expires fetches the live catalog → the model's AA intelligence score rides along in the `raw` column → it ranks itself.

No deploy. No command. Nothing to remember.

Three properties worth knowing, all deliberate:

- **No scheduler, by design.** Fly suspends the machine and suspension kills timers, so the read path *is* the trigger. A cron job here would be unreliable theatre.
- **A fetch failure serves stale rows rather than raising.** Availability beats freshness — the picker never goes blank because OpenRouter had a bad minute.
- **An empty cache populates synchronously** on the first read, so a fresh deploy is never serving an empty list even if the seed below never runs.

---

## Force a refresh now

Skips the 24h wait. Also the right thing to run right after a deploy, so the first real user request isn't paying the cold fetch.

```bash
cd backend && python -m scripts.seed_model_cache                      # dev
cd backend && ENV_FILE=.env.prod python -m scripts.seed_model_cache   # prod
```

Fetches the live catalog and upserts keyed on `model_id`, restamping `fetched_at`. Idempotent — re-running is safe. It never delete-alls the table, so a bad upstream response cannot empty your picker.

Exits non-zero on failure with a logged error rather than a bare traceback, so it is safe to wire into a deploy step if you ever want to.

---

## Inspect what's ranked (read-only)

Runs the shipped ranking code against the live catalog. Touches no database.

```bash
cd backend && venv/Scripts/python.exe -c "
import json, urllib.request
from services.model_catalog_service import aa_ranking, build_model_response
rows = json.load(urllib.request.urlopen('https://openrouter.ai/api/v1/models'))['data']
aa = aa_ranking(rows)
pop = sorted([m for m in (build_model_response(r, aa_ranks=aa) for r in rows)
              if m['popularity_rank'] is not None], key=lambda m: m['popularity_rank'])
for m in pop: print(f\"{m['popularity_rank']:>3}  {m['popularity_source']:<18} {m['id']}\")
"
```

Output looks like:

```
  0  artificialanalysis anthropic/claude-fable-5.1
  2  artificialanalysis anthropic/claude-opus-5
 11  artificialanalysis google/gemini-3.8-flash      <- AA_RANK_LIMIT cutoff
 13  curated            anthropic/claude-sonnet-5
 17  curated            anthropic/claude-haiku-4.5
```

`artificialanalysis` rows ranked themselves. `curated` rows came from `POPULAR_MODELS` — they scored below the cutoff or carry no AA score at all, and the fallback list is their only route into Popular.

---

## Refresh the fallback list

The one job that still needs a human. Only matters for models with **no** AA rank — today that includes real workhorses like `claude-sonnet-5` and `claude-haiku-4.5`, so the list is load-bearing, not vestigial.

### 1. Check whether it needs attention

```bash
cd backend && venv/Scripts/python.exe -c "
import json, urllib.request
from config import get_settings
ids = {m['id'] for m in json.load(urllib.request.urlopen('https://openrouter.ai/api/v1/models'))['data']}
dead = [s for s in get_settings().POPULAR_MODELS if s not in ids]
print('dead slugs:', dead or 'none')
"
```

`none` → nothing to do. A dead slug means that model silently lost its Popular slot (it degrades to `popularity_rank: None` — never a crash), so it is worth replacing.

### 2. Edit and deploy

Update `POPULAR_MODELS` in `backend/config.py:78`, then deploy. It is a code constant, not a DB or env value — there is no admin UI and no runtime override.

### 3. Verify any slug with a membership test

```bash
cd backend && venv/Scripts/python.exe -c "
import json, urllib.request
ids = {m['id'] for m in json.load(urllib.request.urlopen('https://openrouter.ai/api/v1/models'))['data']}
print('anthropic/claude-sonnet-5' in ids)
"
```

**Never verify a slug by eyeballing a filtered or truncated listing.** Slicing the `anthropic/` prefix to the first 25 entries cuts off immediately after `claude-sonnet-4.6:batch` and hides `claude-sonnet-5` — that exact mistake produced a confident, wrong "this model does not exist" claim during the 260910-lcm task. Membership test, always.

---

## Notes & gotchas

- **`:batch` twins are excluded from the ranking.** Every top model ships an identical-score `:batch` duplicate upstream. Unfiltered, a top-12 would be six distinct models and six duplicates.
- **Gaps in the rank sequence are normal.** Curated ranks are offset by `len(aa_ranks)` so AA and curated form one continuous ordering. A model pinned in `POPULAR_MODELS` that *also* wins an AA rank takes the AA rank and leaves its curated slot empty. `anthropic/claude-opus-5` does this today — the redundant pin is deliberate insurance so it keeps a Popular slot if OpenRouter ever drops its AA score. Do not "clean it up".
- **Widening the Popular section is a one-constant change.** Raise or remove `AA_RANK_LIMIT`. The frontend contract is `popularity_rank != null` → Popular (`frontend/src/components/ModelSelector.tsx:198`) with no cap of its own, which is exactly why the bound lives server-side. No frontend edit needed either way.
- **Only about a third of the catalog carries an AA score.** Roughly 130 of 437 at time of writing, and only ~90 of those are non-`:batch`. Removing the cap entirely would make Popular a near-duplicate of "All models".
- **Ties are broken deterministically** by `(-score, model_id)`. Real ties exist upstream; without the tiebreak the Popular section would reshuffle between page loads.
- **Prod is a separate run.** `ENV_FILE=.env.prod` targets the prod Supabase project. Refreshing dev does nothing for prod.
- **`demo_fallback_model` is NOT covered by the dead-slug check above.** It lives at `backend/config.py:42` and currently pins `meta-llama/llama-3.3-70b-instruct:free`, which is gone from the live catalog (the non-`:free` variant survives). Harmless while `demo_fallback_enabled` is `False`; breaks the moment demo mode is switched on.

---

## Quick reference

```bash
# force refresh (dev / prod)
cd backend && python -m scripts.seed_model_cache
cd backend && ENV_FILE=.env.prod python -m scripts.seed_model_cache

# what's in Popular right now (read-only)
#   -> see "Inspect what's ranked" above

# does the fallback list have dead slugs?
#   -> see "Refresh the fallback list" step 1

# knobs
backend/services/model_catalog_service.py:49   AA_RANK_LIMIT            # Popular section size
backend/config.py:51                           model_cache_ttl_seconds  # refresh cadence
backend/config.py:78                           POPULAR_MODELS           # fallback ranking list
```
