#!/usr/bin/env bash
# scripts/verify_prod_supabase.sh
# Reusable Supabase prod schema + seed verification harness.
# Sources: .planning/phases/03-prod-supabase-project/03-CONTEXT.md (D-06..D-14, D-07 two-layer)
# Usage:
#   ENV_FILE=.env.prod bash scripts/verify_prod_supabase.sh
#   bash scripts/verify_prod_supabase.sh --include-seed   # also assert seed counts
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.prod}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "FAIL: $ENV_FILE not found"; exit 1
fi
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

: "${DATABASE_URL:?DATABASE_URL must be set in $ENV_FILE (postgres://...) }"

INCLUDE_SEED=0
[[ "${1:-}" == "--include-seed" ]] && INCLUDE_SEED=1

fails=0
check() {
  local label="$1" sql="$2" expected="$3"
  local actual
  actual=$(psql "$DATABASE_URL" -At -c "$sql" 2>/dev/null || echo "ERR")
  if [[ "$actual" == "$expected" ]]; then
    echo "PASS  $label  ($actual)"
  else
    echo "FAIL  $label  expected=$expected actual=$actual"
    fails=$((fails+1))
  fi
}

# D-06: extensions (vector + ltree)
check "ext.vector" "SELECT count(*) FROM pg_extension WHERE extname='vector'"  "1"
check "ext.ltree"  "SELECT count(*) FROM pg_extension WHERE extname='ltree'"   "1"

# D-07 layer 1: migration row count = 24
check "migrations.count" \
  "SELECT count(*) FROM supabase_migrations.schema_migrations" "24"

# D-07 layer 2: tables
check "tables.core" \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('documents','document_chunks','folders','messages','threads')" "5"

# D-07 layer 2: RPCs
check "rpcs.kb" \
  "SELECT count(*) FROM pg_proc WHERE proname IN ('match_document_chunks','keyword_search_chunks','kb_grep_regex','kb_glob','execute_readonly_query')" "5"

# D-09: storage bucket
check "storage.bucket.documents" \
  "SELECT count(*) FROM storage.buckets WHERE id='documents'" "1"

# D-09: 3 RLS policies on storage.objects
check "storage.policies" \
  "SELECT count(*) FROM pg_policies WHERE schemaname='storage' AND tablename='objects' AND policyname IN ('Users can upload documents','Users can read own documents','Users can delete own documents')" "3"

if [[ "$INCLUDE_SEED" == "1" ]]; then
  # D-14: seed counts
  seed_docs=$(psql "$DATABASE_URL" -At -c "SELECT count(*) FROM documents WHERE visibility='public'")
  seed_folders=$(psql "$DATABASE_URL" -At -c "SELECT count(*) FROM folders WHERE visibility='public'")
  seed_chunks=$(psql "$DATABASE_URL" -At -c "SELECT count(*) FROM document_chunks WHERE document_id IN (SELECT id FROM documents WHERE visibility='public')")
  [[ "$seed_docs"    -ge 10 ]] && echo "PASS  seed.documents>=10  ($seed_docs)"   || { echo "FAIL  seed.documents>=10 actual=$seed_docs"; fails=$((fails+1)); }
  [[ "$seed_folders" -ge 11 ]] && echo "PASS  seed.folders>=11   ($seed_folders)" || { echo "FAIL  seed.folders>=11 actual=$seed_folders"; fails=$((fails+1)); }
  [[ "$seed_chunks"  -gt 0  ]] && echo "PASS  seed.chunks>0      ($seed_chunks)"  || { echo "FAIL  seed.chunks>0 actual=$seed_chunks"; fails=$((fails+1)); }
fi

if [[ "$fails" -gt 0 ]]; then
  echo "VERIFY FAILED: $fails check(s) failed"; exit 1
fi
echo "VERIFY OK"
