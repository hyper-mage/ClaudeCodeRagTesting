import json
import logging
from database import get_supabase
from config import get_settings

logger = logging.getLogger(__name__)

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
