import json
import logging
import re
from database import get_supabase
from config import get_settings

logger = logging.getLogger(__name__)

# SEC-02 / D-01: single Python source of truth for the FROM-table allowlist.
# This set mirrors the SQL allowlist enforced inside execute_readonly_query
# (migration 026) and MUST match QUERYABLE_SCHEMA below exactly. It deliberately
# EXCLUDES user_api_keys (the BYOK key store) and folders (navigated via the
# KB tree/grep/glob tools, not Text-to-SQL). It exists so the allowlist set is
# unit-testable at a deterministic seam (RESEARCH Open Question 2 / Pitfall 5);
# it is NOT wired into execute_sql's runtime path — the DB RPC remains the
# enforcing gate.
ALLOWED_SQL_TABLES = frozenset({"threads", "messages", "documents", "document_chunks"})

# Identifier following a FROM or JOIN keyword (case-insensitive, optional
# double-quote, standard identifier chars). Mirrors the regex shape used in
# migration 026's allowlist loop.
_FROM_JOIN_TABLE_RE = re.compile(r'(?:from|join)\s+"?([a-z_][a-z0-9_]*)', re.IGNORECASE)


def is_query_allowlisted(query: str) -> bool:
    """Return True only if EVERY table referenced after a FROM/JOIN keyword in
    `query` is a member of ALLOWED_SQL_TABLES.

    Pure-Python mirror of migration 026's positive default-deny allowlist. An
    empty match (no FROM/JOIN found) returns False (defensive — a query the
    extractor cannot reason about is not allowlisted).
    """
    tables = [m.lower() for m in _FROM_JOIN_TABLE_RE.findall(query)]
    if not tables:
        return False
    return all(table in ALLOWED_SQL_TABLES for table in tables)

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
