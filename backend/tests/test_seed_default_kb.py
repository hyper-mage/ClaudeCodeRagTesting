"""Tests for the default KB seed script.

Unit-level tests that validate script constants, the ltree sanitizer,
and file existence -- no database connection required.

Run: cd backend && python -m pytest tests/test_seed_default_kb.py -x -v
"""

import sys
import os
import uuid

# Add backend and scripts to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from scripts.seed_default_kb import (
    sanitize_ltree_label,
    GAMES,
    SYSTEM_USER_ID,
    BOARD_GAMES_FOLDER_ID,
    DEFAULT_KB_DIR,
)


def test_sanitize_ltree_label_basic():
    assert sanitize_ltree_label("Catan") == "catan"


def test_sanitize_ltree_label_spaces():
    assert sanitize_ltree_label("Ticket to Ride") == "ticket_to_ride"


def test_sanitize_ltree_label_special_chars():
    assert sanitize_ltree_label("7 Wonders") == "7_wonders"


def test_sanitize_ltree_label_strips_non_alnum():
    assert sanitize_ltree_label("King's Dilemma") == "kings_dilemma"


def test_games_dict_has_10_entries():
    assert len(GAMES) == 10


def test_all_game_files_exist():
    resolved_dir = os.path.normpath(DEFAULT_KB_DIR)
    for filename in GAMES:
        filepath = os.path.join(resolved_dir, filename)
        assert os.path.exists(filepath), f"Missing game file: {filepath}"


def test_system_user_id_is_valid_uuid():
    parsed = uuid.UUID(SYSTEM_USER_ID)
    assert str(parsed) == SYSTEM_USER_ID


def test_board_games_folder_id_is_valid_uuid():
    parsed = uuid.UUID(BOARD_GAMES_FOLDER_ID)
    assert str(parsed) == BOARD_GAMES_FOLDER_ID
    # Must match the value from migration 018
    assert BOARD_GAMES_FOLDER_ID == "a0000000-0000-0000-0000-000000000001"
