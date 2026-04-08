"""Seed the default knowledge base with 10 popular board game markdown files.

Reads markdown files from data/default-kb/, creates per-game subfolders under
the Board Games root folder, and processes each through the ingestion pipeline.
Idempotent: skips games whose content has already been ingested.
"""

import sys
import os
import re
import uuid
import logging

# Add backend directory to sys.path so imports work when run as a module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import get_supabase
from services.record_manager import hash_content, check_duplicate
from services.ingestion_service import process_document

logger = logging.getLogger(__name__)

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"
BOARD_GAMES_FOLDER_ID = "a0000000-0000-0000-0000-000000000001"
DEFAULT_KB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "default-kb")

GAMES = {
    "catan.md": "Catan",
    "ticket-to-ride.md": "Ticket to Ride",
    "pandemic.md": "Pandemic",
    "carcassonne.md": "Carcassonne",
    "7-wonders.md": "7 Wonders",
    "codenames.md": "Codenames",
    "azul.md": "Azul",
    "splendor.md": "Splendor",
    "dominion.md": "Dominion",
    "wingspan.md": "Wingspan",
}


def sanitize_ltree_label(name: str) -> str:
    """Convert a display name to a valid ltree label (lowercase, alnum + underscore only)."""
    label = name.lower().replace(" ", "_")
    label = re.sub(r"[^a-z0-9_]", "", label)
    label = re.sub(r"_+", "_", label).strip("_")
    return label


def get_or_create_game_folder(db, game_name: str) -> str:
    """Get existing game subfolder or create one under Board Games root.
    Returns the folder UUID string."""
    # Check for existing folder
    result = (
        db.table("folders")
        .select("id")
        .eq("parent_id", BOARD_GAMES_FOLDER_ID)
        .eq("name", game_name)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["id"]

    # Generate deterministic UUID from game name
    folder_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"boardgame.{sanitize_ltree_label(game_name)}"))

    # Get parent folder's ltree path
    parent = (
        db.table("folders")
        .select("path")
        .eq("id", BOARD_GAMES_FOLDER_ID)
        .single()
        .execute()
    )
    parent_path = parent.data["path"]
    child_path = f"{parent_path}.{sanitize_ltree_label(game_name)}"

    # Insert new game subfolder
    db.table("folders").insert({
        "id": folder_id,
        "name": game_name,
        "parent_id": BOARD_GAMES_FOLDER_ID,
        "user_id": SYSTEM_USER_ID,
        "path": child_path,
        "visibility": "public",
    }).execute()

    return folder_id


def seed_game(db, filename: str, game_name: str) -> bool:
    """Seed a single game into the default KB.
    Returns True if seeded, False if skipped (already exists)."""
    file_path = os.path.join(DEFAULT_KB_DIR, filename)
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    # Check for duplicate content
    content_hash = hash_content(file_bytes)
    existing = check_duplicate(SYSTEM_USER_ID, content_hash)
    if existing:
        print(f"  Skipping {game_name} (already seeded)")
        return False

    # Get or create game subfolder
    folder_id = get_or_create_game_folder(db, game_name)

    # Generate document ID and upload to storage
    doc_id = str(uuid.uuid4())
    storage_path = f"{SYSTEM_USER_ID}/{doc_id}/{filename}"
    db.storage.from_("documents").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "text/markdown"},
    )

    # Insert document record
    db.table("documents").insert({
        "id": doc_id,
        "user_id": SYSTEM_USER_ID,
        "filename": filename,
        "storage_path": storage_path,
        "file_size": len(file_bytes),
        "mime_type": "text/markdown",
        "status": "pending",
        "content_hash": content_hash,
        "folder_id": folder_id,
        "visibility": "public",
    }).execute()

    # Process through ingestion pipeline (chunk + embed)
    process_document(doc_id, SYSTEM_USER_ID)
    print(f"  Seeded {game_name}")
    return True


def main() -> None:
    """Seed all 10 default board games into the knowledge base."""
    db = get_supabase()
    print("Seeding default knowledge base...")

    seeded = 0
    skipped = 0
    for filename, game_name in GAMES.items():
        if seed_game(db, filename, game_name):
            seeded += 1
        else:
            skipped += 1

    print(f"Seeded {seeded} games, skipped {skipped} (already exist)")


if __name__ == "__main__":
    main()
