#!/usr/bin/env bash
# backend/scripts/_lib/get_test_jwt.sh
# Phase 4 D-14: shared Supabase password-grant helper.
# Sourced by docker_smoke.sh (uses .env) and fly_smoke.sh (uses .env.prod).
#
# Caller MUST source the appropriate env file FIRST so $VITE_SUPABASE_URL
# and $VITE_SUPABASE_ANON_KEY are exported. Function reads them; does not
# load any env file itself.
#
# Usage:
#   set -a; source .env.prod; set +a
#   source backend/scripts/_lib/get_test_jwt.sh
#   get_test_jwt    # exports $JWT (or returns 1 + writes error to stderr)
#   echo "$JWT"

get_test_jwt() {
  : "${VITE_SUPABASE_URL:?get_test_jwt: VITE_SUPABASE_URL not set — source env file first}"
  : "${VITE_SUPABASE_ANON_KEY:?get_test_jwt: VITE_SUPABASE_ANON_KEY not set — source env file first}"
  local AUTH_JSON
  AUTH_JSON=$(curl -sS -X POST "${VITE_SUPABASE_URL}/auth/v1/token?grant_type=password" \
    -H "apikey: ${VITE_SUPABASE_ANON_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_EMAIL:-ragtest1@gmail.com}\",\"password\":\"${TEST_PASSWORD:-testpass123}\"}")
  JWT=$(echo "$AUTH_JSON" | jq -r '.access_token // empty')
  if [ -z "$JWT" ]; then
    echo "[get_test_jwt] auth failed: $AUTH_JSON" >&2
    return 1
  fi
  export JWT
}
