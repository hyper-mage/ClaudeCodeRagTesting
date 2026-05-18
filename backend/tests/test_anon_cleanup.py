"""Tests for purge_stale_anon_users (PORT-01 cleanup half).

Test plan:
- test_purge_filters_correctly       — Plan 08-02 Wave 1: only anon users older than threshold are deleted
- test_cascade_order                 — Plan 08-02 Wave 1: chunks → documents → storage → auth user order respected
- test_purge_swallows_per_user_errors — Plan 08-02 Wave 1: a single failed user does not abort the whole sweep
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


def _make_user(*, user_id: str, is_anonymous: bool, age_days: float) -> MagicMock:
    """Build a MagicMock that mimics the gotrue User model for purge filtering."""
    u = MagicMock()
    u.id = user_id
    u.is_anonymous = is_anonymous
    u.created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    return u


def test_purge_filters_correctly() -> None:
    """Only anon users older than retention_days are deleted (permanent + recent skipped)."""
    from services.demo_service import purge_stale_anon_users

    old_anon = _make_user(user_id="old-anon", is_anonymous=True, age_days=8)
    new_anon = _make_user(user_id="new-anon", is_anonymous=True, age_days=1)
    permanent = _make_user(user_id="perm-uuid", is_anonymous=False, age_days=30)

    mock_db = MagicMock()
    mock_db.auth.admin.list_users.return_value = [old_anon, new_anon, permanent]
    mock_db.storage.from_.return_value.list.return_value = []

    with patch("services.demo_service.get_supabase", return_value=mock_db):
        deleted = purge_stale_anon_users(retention_days=7)

    assert deleted == 1, f"expected 1 deleted, got {deleted}"
    mock_db.auth.admin.delete_user.assert_called_once_with("old-anon")


def test_cascade_order() -> None:
    """Cascade-delete table order is exactly document_chunks → documents → folders → messages → threads."""
    from services.demo_service import purge_stale_anon_users

    old_anon = _make_user(user_id="old-anon", is_anonymous=True, age_days=8)

    mock_db = MagicMock()
    mock_db.auth.admin.list_users.return_value = [old_anon]
    mock_db.storage.from_.return_value.list.return_value = []

    with patch("services.demo_service.get_supabase", return_value=mock_db):
        purge_stale_anon_users(retention_days=7)

    # Extract every db.table(<name>) call name in order. The cascade is the
    # only thing calling db.table in this test (no other code path runs).
    table_names = [
        call.args[0]
        for call in mock_db.table.call_args_list
    ]
    assert table_names == [
        "document_chunks",
        "documents",
        "folders",
        "messages",
        "threads",
    ], f"unexpected cascade order: {table_names!r}"


def test_purge_swallows_per_user_errors() -> None:
    """A single failed user does not abort the loop; logged + skipped + count reflects survivors."""
    from services.demo_service import purge_stale_anon_users

    old_anon_a = _make_user(user_id="old-anon-a", is_anonymous=True, age_days=8)
    old_anon_b = _make_user(user_id="old-anon-b", is_anonymous=True, age_days=10)

    mock_db = MagicMock()
    mock_db.auth.admin.list_users.return_value = [old_anon_a, old_anon_b]
    mock_db.storage.from_.return_value.list.return_value = []
    # First delete_user call raises, second succeeds; loop must continue.
    mock_db.auth.admin.delete_user.side_effect = [Exception("boom"), None]

    with patch("services.demo_service.get_supabase", return_value=mock_db):
        deleted = purge_stale_anon_users(retention_days=7)

    assert deleted == 1, f"expected 1 successful delete after one error, got {deleted}"
    assert mock_db.auth.admin.delete_user.call_count == 2, (
        f"expected delete_user to be attempted twice, got {mock_db.auth.admin.delete_user.call_count}"
    )
