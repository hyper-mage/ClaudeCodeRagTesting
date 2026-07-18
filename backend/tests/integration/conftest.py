"""Fixtures for the real-DB integration suite (quick task 260718-o4c).

CRITICAL: this file NEVER patches or mocks `get_supabase`. That is the entire reason the
suite catches PostgREST-shape bugs — a real service-role round-trip is the only thing that
surfaces the resource-embedding / maybe_single class of regression.

Auth is overridden (mirroring `test_folders_api.py::override_auth`) so the endpoints run as
the system user WITHOUT needing a real JWT; the DB client stays fully real.

Every seed fixture inserts sentinel-prefixed rows owned by the system user and DELETES them
in teardown-AFTER-yield, so a failed assertion still cleans up. All deletes are idempotent
(delete-by-id / delete-by-thread_id) so a test that already removed the row cleans up
without error.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from main import app
from auth import get_user_id
from database import get_supabase

from tests.integration import SENTINEL, SYSTEM_USER_ID


@pytest.fixture(autouse=True)
def override_auth():
    """Run every request as the system user (no real JWT). get_supabase stays REAL."""
    app.dependency_overrides[get_user_id] = lambda: SYSTEM_USER_ID
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    """The REAL service-role client — used by fixtures to seed/tear down rows."""
    return get_supabase()


@pytest.fixture
def seeded_thread(db):
    """Insert a throwaway thread + 2 messages with EXPLICIT, out-of-order created_at.

    The LATER (assistant / "second") message is inserted FIRST so a naive/unsorted return
    would be wrong — the GET test proves `get_thread`'s Python asc-sort against the real
    embedded array.
    """
    tid = str(uuid.uuid4())
    db.table("threads").insert(
        {"id": tid, "user_id": SYSTEM_USER_ID, "title": f"{SENTINEL}{tid}"}
    ).execute()

    # Insert the LATER row first (deliberate) so ordering is not incidentally correct.
    db.table("messages").insert(
        {
            "id": str(uuid.uuid4()),
            "thread_id": tid,
            "user_id": SYSTEM_USER_ID,
            "role": "assistant",
            "content": "second",
            "created_at": "2020-01-01T00:00:01+00:00",
        }
    ).execute()
    db.table("messages").insert(
        {
            "id": str(uuid.uuid4()),
            "thread_id": tid,
            "user_id": SYSTEM_USER_ID,
            "role": "user",
            "content": "first",
            "created_at": "2020-01-01T00:00:00+00:00",
        }
    ).execute()

    yield {"tid": tid, "early_content": "first", "late_content": "second"}

    # Teardown AFTER yield — always runs, even on assertion failure. Idempotent.
    db.table("messages").delete().eq("thread_id", tid).execute()
    db.table("threads").delete().eq("id", tid).execute()


@pytest.fixture
def seeded_folder(db):
    """Insert a throwaway private folder. path label is [a-z0-9_] only; the uuid suffix
    satisfies UNIQUE(user_id, path)."""
    fid = str(uuid.uuid4())
    db.table("folders").insert(
        {
            "id": fid,
            "user_id": SYSTEM_USER_ID,
            "name": f"{SENTINEL}{fid[:8]}",
            "path": f"my_documents.inttest_{fid.replace('-', '')}",
            "visibility": "private",
        }
    ).execute()

    yield fid

    db.table("folders").delete().eq("id", fid).execute()


@pytest.fixture
def seeded_document(db):
    """Insert a throwaway private document row.

    storage_path is a dummy string — NO real Storage object is created because
    `list_documents` only reads the table, never Storage.
    """
    did = str(uuid.uuid4())
    db.table("documents").insert(
        {
            "id": did,
            "user_id": SYSTEM_USER_ID,
            "filename": f"{SENTINEL}{did[:8]}.md",
            "storage_path": f"inttest/{did}/x.md",
            "file_size": 1,
            "mime_type": "text/markdown",
            "status": "completed",
            "visibility": "private",
        }
    ).execute()

    yield did

    db.table("documents").delete().eq("id", did).execute()
