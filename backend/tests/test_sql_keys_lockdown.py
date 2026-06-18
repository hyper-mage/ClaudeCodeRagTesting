"""SEC-02 exfiltration probe — the SQL-tool keys-table lockdown gate.

Asserts the ALLOWLIST LOGIC at a deterministic, pure-Python seam rather than a
mocked DB return. Per RESEARCH Pitfall 5, a purely-mocked probe (one that mocks
execute_readonly_query and never asserts the SQL string was rejected) is a false
PASS — it tests the mock, not the protection. Here we assert against
`is_query_allowlisted` / `ALLOWED_SQL_TABLES`, the single Python source of truth
that mirrors the SQL allowlist in migration 026.

Usage: cd backend && venv/Scripts/python.exe -m pytest tests/test_sql_keys_lockdown.py -x
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.sql_service import is_query_allowlisted, ALLOWED_SQL_TABLES


def test_keys_table_query_blocked():
    """A model-authored 'select * from user_api_keys' is rejected by the
    allowlist (the core SEC-02 exfiltration attempt)."""
    assert is_query_allowlisted("select * from user_api_keys") is False
    # Case/whitespace variants and a JOIN smuggle must also be rejected.
    assert is_query_allowlisted("SELECT encrypted_key FROM user_api_keys") is False
    assert (
        is_query_allowlisted(
            "select t.id from threads t join user_api_keys k on k.user_id = t.user_id"
        )
        is False
    )


def test_allowlisted_queries_pass():
    """Legitimate queries against the four advertised tables still pass
    (regression guard so legitimate Text-to-SQL keeps working)."""
    assert is_query_allowlisted("select count(*) from threads") is True
    assert is_query_allowlisted("select * from messages") is True
    assert is_query_allowlisted("select id from documents") is True
    # documents JOIN document_chunks — both tables are allowlisted.
    assert (
        is_query_allowlisted(
            "select d.filename, c.content from documents d "
            "join document_chunks c on c.document_id = d.id"
        )
        is True
    )


def test_user_api_keys_not_in_allowlist():
    """The keys table (and folders) are NOT members of the allowlist set."""
    assert "user_api_keys" not in ALLOWED_SQL_TABLES
    assert "folders" not in ALLOWED_SQL_TABLES
    # The allowlist is exactly the four advertised QUERYABLE_SCHEMA tables.
    assert ALLOWED_SQL_TABLES == {"threads", "messages", "documents", "document_chunks"}
