import json
import logging
import re
from database import get_supabase
from config import get_settings

logger = logging.getLogger(__name__)

# SEC-02 / D-01: single Python source of truth for the FROM-table allowlist.
# This set mirrors the SQL allowlist enforced inside execute_readonly_query
# (migration 027 — the hardened replacement of 026) and MUST match
# QUERYABLE_SCHEMA below exactly. It deliberately EXCLUDES user_api_keys (the
# BYOK key store) and folders (navigated via the KB tree/grep/glob tools, not
# Text-to-SQL). It exists so the allowlist set is unit-testable at a
# deterministic seam (RESEARCH Open Question 2 / Pitfall 5); it is NOT wired
# into execute_sql's runtime path — the DB RPC remains the enforcing gate.
ALLOWED_SQL_TABLES = frozenset({"threads", "messages", "documents", "document_chunks"})

# A regex cannot truly parse SQL; the DB RPC (migration 027) is the enforcing
# gate. This Python mirror is a fail-closed approximation kept faithful to that
# gate so the allowlist is unit-testable at a deterministic seam.
#
# Step 1: isolate each FROM-clause REGION — the text after a `from` keyword up
# to the next clause-terminating keyword (where/group/order/having/limit/...),
# a closing paren, semicolon, or end-of-string. DOTALL so multi-line queries are
# handled. Nested subqueries each contain their own `from`, so an exfil attempt
# like `from (select * from user_api_keys) sub` yields a region containing the
# inner `from user_api_keys` which is then inspected (CR-01/CR-02 defense in
# depth against subquery smuggling).
_FROM_CLAUSE_RE = re.compile(
    r'\bfrom\b(.*?)'
    r'(?=\bwhere\b|\bgroup\b|\border\b|\bhaving\b|\blimit\b|\boffset\b'
    r'|\bunion\b|\bintersect\b|\bexcept\b|\bwindow\b|\bfetch\b|\bfor\b'
    r'|\)|;|$)',
    re.IGNORECASE | re.DOTALL,
)

# Step 2: within a FROM region, a table SOURCE is the token at the region start,
# after a `join` keyword, or after a comma (implicit cross-join — CR-01). Each
# source may be schema-qualified (CR-02): group 1 is the first identifier, group
# 2 the optional `.table` segment after a dot. When group 2 is present the source
# was `schema.table` (group 1 = schema, group 2 = table); otherwise group 1 is
# the bare table. Optional opening double-quote, standard identifier chars.
_SOURCE_RE = re.compile(
    r'(?:^|\bjoin\b|,)\s*"?([a-z_][a-z0-9_]*)"?(?:\s*\.\s*"?([a-z_][a-z0-9_]*)"?)?',
    re.IGNORECASE,
)

# Only the `public` schema may be referenced with a schema-qualified name; any
# other schema (auth, storage, pg_catalog, ...) is rejected outright (CR-02).
_ALLOWED_SQL_SCHEMA = "public"


def is_query_allowlisted(query: str) -> bool:
    """Return True only if EVERY table referenced in a FROM-list position
    (after FROM, JOIN, or a comma cross-join, in any subquery) is a member of
    ALLOWED_SQL_TABLES.

    Pure-Python mirror of migration 027's positive default-deny allowlist.
    Fail-closed semantics:

    - Comma cross-joins (`from a, b`) are parsed — every comma-separated source
      in the FROM clause is validated, not just the token after FROM/JOIN
      (CR-01). Commas in the SELECT list are NOT mistaken for FROM-list members
      because only the isolated FROM-clause region is scanned for sources.
    - Schema-qualified names (`schema.table`) are normalized: only the `public`
      schema is permitted, and the TABLE part is checked against the allowlist;
      any other schema (e.g. `auth.users`, `messages.user_api_keys`) is rejected
      (CR-02).
    - Subquery FROM clauses are inspected too (each `from` opens its own region),
      so `from (select * from user_api_keys) sub` is rejected.
    - If no FROM clause is found, or a FROM region yields no parseable source,
      the query is NOT allowlisted (defensive default-deny — a query the
      extractor cannot reason about is not trusted).
    """
    regions = _FROM_CLAUSE_RE.findall(query)
    if not regions:
        return False
    found_any_source = False
    for region in regions:
        for first, second in _SOURCE_RE.findall(region):
            if not first:
                continue
            found_any_source = True
            if second:
                # Schema-qualified: `first.second` -> schema=first, table=second.
                # Only the public schema is allowed; the table must be allowlisted.
                if first.lower() != _ALLOWED_SQL_SCHEMA:
                    return False
                table = second.lower()
            else:
                # Bare identifier -> table name with implicit (public) schema.
                table = first.lower()
            if table not in ALLOWED_SQL_TABLES:
                return False
    return found_any_source

QUERYABLE_SCHEMA = """
Available tables (all filtered to the current user's data automatically):

threads:
  - id (UUID, primary key)
  - title (TEXT, nullable — conversation title)
  - created_at (TIMESTAMPTZ)
  - updated_at (TIMESTAMPTZ)

messages:
  - id (UUID, primary key)
  - thread_id (UUID, references threads.id)
  - role (TEXT — 'user' or 'assistant')
  - content (TEXT — message text)
  - created_at (TIMESTAMPTZ)

documents:
  - id (UUID, primary key)
  - filename (TEXT)
  - file_size (INTEGER, bytes)
  - mime_type (TEXT)
  - status (TEXT — 'pending', 'processing', 'completed', 'failed')
  - chunk_count (INTEGER)
  - metadata (JSONB — contains document_type, topic, keywords, summary, language)
  - created_at (TIMESTAMPTZ)
  - updated_at (TIMESTAMPTZ)

document_chunks:
  - id (UUID, primary key)
  - document_id (UUID, references documents.id)
  - content (TEXT — chunk text)
  - chunk_index (INTEGER)
  - metadata (JSONB)
""".strip()


def get_queryable_schema() -> str:
    return QUERYABLE_SCHEMA


def execute_sql(user_id: str, query: str) -> dict:
    """Execute a read-only SQL query via the safe RPC function."""
    settings = get_settings()
    db = get_supabase()
    try:
        result = db.rpc("execute_readonly_query", {
            "query_text": query,
            "max_rows": settings.sql_max_rows,
            "calling_user_id": user_id,
        }).execute()
        rows = result.data if result.data else []
        return {
            "success": True,
            "rows": rows,
            "row_count": len(rows) if isinstance(rows, list) else 0,
            "truncated": isinstance(rows, list) and len(rows) >= settings.sql_max_rows,
        }
    except Exception as e:
        logger.error(f"SQL execution failed: {e}", exc_info=True)
        return {"success": False, "error": str(e), "rows": [], "row_count": 0}
