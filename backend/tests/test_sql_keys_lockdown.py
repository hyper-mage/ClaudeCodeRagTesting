"""SEC-02 exfiltration probe — the SQL-tool keys-table lockdown gate.

Asserts the ALLOWLIST LOGIC at a deterministic, pure-Python seam rather than a
mocked DB return. Per RESEARCH Pitfall 5, a purely-mocked probe (one that mocks
execute_readonly_query and never asserts the SQL string was rejected) is a false
PASS — it tests the mock, not the protection. Here we assert against
`is_query_allowlisted` / `ALLOWED_SQL_TABLES`, the single Python source of truth
that mirrors the SQL allowlist in migration 027 (the hardened replacement of 026).

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


def test_comma_cross_join_blocked():
    """CR-01: a comma cross-join (implicit FROM-list member) that smuggles a
    non-allowlisted table must be rejected. The pre-fix parser only inspected
    the token after FROM/JOIN and let the comma member through (false PASS).

    Red-then-green: these assertions FAIL against the old FROM/JOIN-only regex
    and PASS against the migration-027-aligned FROM-clause parser."""
    assert is_query_allowlisted("select * from threads, user_api_keys") is False
    assert is_query_allowlisted("select * from documents d, user_api_keys k") is False
    # auth.users via a comma cross-join (NOT behind the Gate-1 REVOKE) must
    # also be rejected — the broader purpose of Gate 2.
    assert (
        is_query_allowlisted(
            "select t.id from threads t, auth.users u where u.id = t.user_id"
        )
        is False
    )


def test_schema_qualified_keys_blocked():
    """CR-02: schema-qualified references must validate the TABLE part against
    the allowlist and reject any non-public schema. The pre-fix parser captured
    the SCHEMA segment (e.g. `messages` from `messages.user_api_keys`), which
    happened to be allowlisted, so the keys table slipped through (false PASS)."""
    # public.user_api_keys: schema allowed, but table is NOT allowlisted.
    assert is_query_allowlisted("select * from public.user_api_keys") is False
    # messages.user_api_keys: old parser captured `messages` (allowlisted) and
    # passed; the hardened parser sees table=user_api_keys and rejects.
    assert is_query_allowlisted("select * from messages.user_api_keys") is False
    # auth.users: non-public schema is rejected outright.
    assert is_query_allowlisted("select * from auth.users") is False
    # arbitrary schema qualifier is rejected.
    assert is_query_allowlisted("select * from x.user_api_keys") is False


def test_subquery_exfil_blocked():
    """CR-01/CR-02 defense-in-depth: a non-allowlisted table smuggled inside a
    subquery FROM clause is inspected and rejected."""
    assert (
        is_query_allowlisted("select * from (select * from user_api_keys) sub")
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
    # Multi-table comma cross-join, all sources allowlisted — must PASS
    # (WR-02 regression guard: legitimate comma joins are not falsely rejected).
    assert (
        is_query_allowlisted(
            "select * from documents d, document_chunks c "
            "where c.document_id = d.id"
        )
        is True
    )
    # JOIN over two allowlisted tables with a SELECT-list comma — the SELECT
    # comma must NOT be mistaken for a FROM-list member.
    assert (
        is_query_allowlisted(
            "select m.content, t.title from messages m "
            "join threads t on m.thread_id = t.id"
        )
        is True
    )
    # public-qualified allowlisted table passes.
    assert is_query_allowlisted("select * from public.threads") is True


def test_user_api_keys_not_in_allowlist():
    """The keys table (and folders) are NOT members of the allowlist set."""
    assert "user_api_keys" not in ALLOWED_SQL_TABLES
    assert "folders" not in ALLOWED_SQL_TABLES
    # The allowlist is exactly the four advertised QUERYABLE_SCHEMA tables.
    assert ALLOWED_SQL_TABLES == {"threads", "messages", "documents", "document_chunks"}
