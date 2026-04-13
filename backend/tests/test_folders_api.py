"""Unit tests for folder CRUD + document rename/move/bulk endpoints.

Uses FastAPI TestClient with mocked Supabase client. The `get_user_id`
dependency is overridden to return a fixed test UUID. The `get_supabase`
dependency is NOT directly DI-injected in the routers (they call
`get_supabase()` as a plain function), so we patch the symbol inside
each router module.

Usage: cd backend && python -m pytest tests/test_folders_api.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from main import app
from auth import get_user_id

TEST_USER_ID = "11111111-1111-1111-1111-111111111111"
BOARD_GAMES_ROOT_ID = "a0000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def override_auth():
    """Bypass JWT auth for all tests."""
    app.dependency_overrides[get_user_id] = lambda: TEST_USER_ID
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _make_query_chain(terminal_result):
    """Return a MagicMock whose .execute() returns `terminal_result` and
    whose builder methods (.select, .eq, .or_, .order, .in_, .like,
    .single, .maybe_single, .update, .insert, .delete) all return self.
    """
    chain = MagicMock()
    for method in (
        "select", "eq", "or_", "order", "in_", "like",
        "single", "maybe_single", "update", "insert", "delete",
    ):
        getattr(chain, method).return_value = chain
    chain.execute.return_value = terminal_result
    return chain


def _result(data):
    r = MagicMock()
    r.data = data
    return r


def _make_folder(
    fid="f-1",
    name="MyFolder",
    path="my_documents.myfolder",
    parent_id=None,
    visibility="private",
    user_id=TEST_USER_ID,
):
    return {
        "id": fid,
        "user_id": user_id,
        "name": name,
        "path": path,
        "parent_id": parent_id,
        "visibility": visibility,
        "created_at": "2026-04-13T00:00:00Z",
        "updated_at": "2026-04-13T00:00:00Z",
    }


def _make_document(
    did="d-1",
    filename="doc.pdf",
    folder_id=None,
    visibility="private",
    user_id=TEST_USER_ID,
    storage_path=None,
):
    return {
        "id": did,
        "user_id": user_id,
        "filename": filename,
        "storage_path": storage_path or f"{user_id}/{did}/{filename}",
        "folder_id": folder_id,
        "visibility": visibility,
        "status": "ready",
        "file_size": 1000,
        "mime_type": "application/pdf",
    }


class MockSupabase:
    """Mock Supabase client. The `tables` dict maps table name -> function
    that receives a list of recorded ops and returns the terminal result.

    For simplicity we use a router attribute: each test sets callable
    handlers for .table(name) and .storage.from_(...).
    """

    def __init__(self):
        self.table_handler = None
        self.storage_remove = MagicMock(return_value=None)
        self.storage_from_mock = MagicMock()
        self.storage_from_mock.remove = self.storage_remove

    def table(self, name):
        return self.table_handler(name)

    @property
    def storage(self):
        obj = MagicMock()
        obj.from_ = lambda bucket: self.storage_from_mock
        return obj


# ---------------------------------------------------------------------------
# Folder API tests
# ---------------------------------------------------------------------------

def test_create_folder(client):
    """POST /api/folders creates a private folder with my_documents.* path."""
    inserted_payload = {}

    class FakeInsertChain:
        def insert(self, payload):
            inserted_payload.update(payload)
            return self
        def execute(self):
            return _result([inserted_payload])

    def table_handler(name):
        assert name == "folders"
        return FakeInsertChain()

    mock_db = MockSupabase()
    mock_db.table_handler = table_handler

    with patch("routers.folders.get_supabase", return_value=mock_db):
        r = client.post("/api/folders", json={"name": "My Folder"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "My Folder"
    assert body["visibility"] == "private"
    assert body["path"] == "my_documents.my_folder"


def test_create_folder_with_parent(client):
    """POST /api/folders with parent_id derives path from parent."""
    parent = _make_folder(fid="parent-1", name="Parent", path="my_documents.parent")
    inserted_payload = {}

    class Chain:
        def __init__(self):
            self.mode = None
        def select(self, *_a, **_kw):
            self.mode = "select"; return self
        def insert(self, payload):
            self.mode = "insert"; inserted_payload.update(payload); return self
        def eq(self, *_a, **_kw): return self
        def maybe_single(self): return self
        def execute(self):
            if self.mode == "select":
                return _result(parent)
            return _result([inserted_payload])

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.folders.get_supabase", return_value=mock_db):
        r = client.post("/api/folders", json={"name": "Sub", "parent_id": "parent-1"})

    assert r.status_code == 200, r.text
    assert r.json()["path"] == "my_documents.parent.sub"


def test_create_folder_in_public_rejected(client):
    """POST /api/folders with parent=public returns 403."""
    public_parent = _make_folder(
        fid=BOARD_GAMES_ROOT_ID,
        name="Board Games",
        path="board_games",
        visibility="public",
        user_id="00000000-0000-0000-0000-000000000000",
    )

    class Chain:
        def select(self, *_a, **_kw): return self
        def eq(self, *_a, **_kw): return self
        def maybe_single(self): return self
        def execute(self): return _result(public_parent)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.folders.get_supabase", return_value=mock_db):
        r = client.post(
            "/api/folders",
            json={"name": "Bad", "parent_id": BOARD_GAMES_ROOT_ID},
        )
    assert r.status_code == 403


def test_rename_folder(client):
    """PATCH /api/folders/{id} renames private folder."""
    folder = _make_folder(fid="f-rename", name="Old", path="my_documents.old")
    updated = {**folder, "name": "New Name", "path": "my_documents.new_name"}

    state = {"count": 0}

    class Chain:
        def __init__(self): self.mode = None
        def select(self, *_a, **_kw): self.mode = "select"; return self
        def update(self, payload): self.mode = "update"; self.payload = payload; return self
        def eq(self, *_a, **_kw): return self
        def like(self, *_a, **_kw): self.mode = "descendants"; return self
        def maybe_single(self): return self
        def single(self): self.mode = "select_single"; return self
        def execute(self):
            state["count"] += 1
            if self.mode == "select" and state["count"] == 1:
                return _result(folder)
            if self.mode == "descendants":
                return _result([])
            if self.mode == "select_single":
                return _result(updated)
            return _result(None)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.folders.get_supabase", return_value=mock_db):
        r = client.patch("/api/folders/f-rename", json={"name": "New Name"})

    assert r.status_code == 200, r.text
    assert r.json()["name"] == "New Name"
    assert r.json()["path"] == "my_documents.new_name"


def test_rename_public_folder_rejected(client):
    public = _make_folder(
        fid="pub-1", path="board_games", visibility="public",
        user_id="00000000-0000-0000-0000-000000000000",
    )

    class Chain:
        def select(self, *_a, **_kw): return self
        def eq(self, *_a, **_kw): return self
        def maybe_single(self): return self
        def execute(self): return _result(public)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.folders.get_supabase", return_value=mock_db):
        r = client.patch("/api/folders/pub-1", json={"name": "Bad"})
    assert r.status_code == 403


def test_delete_folder_cascade(client):
    """DELETE /api/folders/{id} removes storage files + cascades DB."""
    folder = _make_folder(fid="del-1", path="my_documents.del_1")
    docs = [_make_document(did="doc-a"), _make_document(did="doc-b")]

    state = {"stage": 0}

    class Chain:
        def __init__(self, table):
            self.table = table
            self.mode = None
        def select(self, *_a, **_kw): self.mode = "select"; return self
        def delete(self): self.mode = "delete"; return self
        def eq(self, *_a, **_kw): return self
        def like(self, *_a, **_kw): self.mode = "like"; return self
        def in_(self, *_a, **_kw): self.mode = "in"; return self
        def maybe_single(self): self.mode = "maybe"; return self
        def execute(self):
            state["stage"] += 1
            if self.table == "folders":
                if self.mode == "maybe":
                    return _result(folder)
                if self.mode == "like":
                    return _result([])  # no descendants
                if self.mode == "delete":
                    return _result(None)
            if self.table == "documents":
                if self.mode == "in":
                    return _result(docs)
            return _result(None)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain(name)

    with patch("routers.folders.get_supabase", return_value=mock_db):
        r = client.delete("/api/folders/del-1")

    assert r.status_code == 204
    # storage.remove should have been called with storage paths of the docs
    mock_db.storage_remove.assert_called()
    called_paths = mock_db.storage_remove.call_args[0][0]
    assert any("doc-a" in p for p in called_paths)
    assert any("doc-b" in p for p in called_paths)


def test_delete_public_folder_rejected(client):
    public = _make_folder(
        fid="pub-del", path="board_games", visibility="public",
        user_id="00000000-0000-0000-0000-000000000000",
    )

    class Chain:
        def select(self, *_a, **_kw): return self
        def eq(self, *_a, **_kw): return self
        def maybe_single(self): return self
        def execute(self): return _result(public)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.folders.get_supabase", return_value=mock_db):
        r = client.delete("/api/folders/pub-del")
    assert r.status_code == 403


def test_move_folder(client):
    """PATCH /api/folders/{id}/move updates path + descendants."""
    src = _make_folder(fid="mv-src", name="Src", path="my_documents.src")
    target = _make_folder(fid="mv-tgt", name="Tgt", path="my_documents.tgt")
    updated = {**src, "parent_id": "mv-tgt", "path": "my_documents.tgt.src"}

    lookups = [src, target]  # Order: source first, then target

    class Chain:
        def __init__(self): self.mode = None
        def select(self, *_a, **_kw): self.mode = "select"; return self
        def update(self, payload): self.mode = "update"; self.payload = payload; return self
        def eq(self, *_a, **_kw): return self
        def like(self, *_a, **_kw): self.mode = "like"; return self
        def maybe_single(self): self.mode = "maybe"; return self
        def single(self): self.mode = "single"; return self
        def execute(self):
            if self.mode == "maybe":
                return _result(lookups.pop(0))
            if self.mode == "like":
                return _result([])
            if self.mode == "single":
                return _result(updated)
            return _result(None)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.folders.get_supabase", return_value=mock_db):
        r = client.patch("/api/folders/mv-src/move", json={"new_parent_id": "mv-tgt"})

    assert r.status_code == 200, r.text
    assert r.json()["path"] == "my_documents.tgt.src"


def test_move_to_public_rejected(client):
    src = _make_folder(fid="mv-src", name="Src", path="my_documents.src")
    public_target = _make_folder(
        fid=BOARD_GAMES_ROOT_ID, path="board_games", visibility="public",
        user_id="00000000-0000-0000-0000-000000000000",
    )
    lookups = [src, public_target]

    class Chain:
        def __init__(self): self.mode = None
        def select(self, *_a, **_kw): self.mode = "select"; return self
        def eq(self, *_a, **_kw): return self
        def maybe_single(self): return self
        def execute(self): return _result(lookups.pop(0))

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.folders.get_supabase", return_value=mock_db):
        r = client.patch(
            "/api/folders/mv-src/move",
            json={"new_parent_id": BOARD_GAMES_ROOT_ID},
        )
    assert r.status_code == 403


def test_list_folders(client):
    private_f = _make_folder(fid="p-1", path="my_documents.private")
    public_f = _make_folder(
        fid="pub-1", path="board_games", visibility="public",
        user_id="00000000-0000-0000-0000-000000000000",
    )

    class Chain:
        def select(self, *_a, **_kw): return self
        def or_(self, *_a, **_kw): return self
        def order(self, *_a, **_kw): return self
        def execute(self): return _result([public_f, private_f])

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.folders.get_supabase", return_value=mock_db):
        r = client.get("/api/folders")

    assert r.status_code == 200
    ids = {f["id"] for f in r.json()}
    assert "p-1" in ids and "pub-1" in ids


def test_get_folder_contents(client):
    """GET /api/folders/{id}/contents returns folder + subfolders + documents."""
    folder = _make_folder(fid="fc-1", path="my_documents.fc_1")
    sub = _make_folder(fid="sub-1", path="my_documents.fc_1.sub", parent_id="fc-1")
    doc = _make_document(did="doc-fc", folder_id="fc-1")

    call_state = {"i": 0}

    class Chain:
        def __init__(self, table):
            self.table = table
            self.mode = None
        def select(self, *_a, **_kw): return self
        def eq(self, *_a, **_kw): return self
        def or_(self, *_a, **_kw): return self
        def order(self, *_a, **_kw): return self
        def maybe_single(self): self.mode = "maybe"; return self
        def execute(self):
            call_state["i"] += 1
            if self.table == "folders":
                if self.mode == "maybe":
                    return _result(folder)
                return _result([sub])
            if self.table == "documents":
                return _result([doc])
            return _result(None)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain(name)

    with patch("routers.folders.get_supabase", return_value=mock_db):
        r = client.get("/api/folders/fc-1/contents")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["folder"]["id"] == "fc-1"
    assert body["subfolders"][0]["id"] == "sub-1"
    assert body["documents"][0]["id"] == "doc-fc"


# ---------------------------------------------------------------------------
# Document API tests (rename, move, bulk-delete, bulk-move)
# ---------------------------------------------------------------------------

def test_rename_document(client):
    doc = _make_document(did="d-rename", filename="old.pdf")
    updated = {**doc, "filename": "renamed.pdf"}

    state = {"i": 0}

    class Chain:
        def __init__(self): self.mode = None
        def select(self, *_a, **_kw): self.mode = "select"; return self
        def update(self, _p): self.mode = "update"; return self
        def eq(self, *_a, **_kw): return self
        def maybe_single(self): self.mode = "maybe"; return self
        def single(self): self.mode = "single"; return self
        def execute(self):
            state["i"] += 1
            if self.mode == "maybe":
                return _result(doc)
            if self.mode == "single":
                return _result(updated)
            return _result(None)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.documents.get_supabase", return_value=mock_db):
        r = client.patch("/api/documents/d-rename", json={"filename": "renamed.pdf"})

    assert r.status_code == 200, r.text
    assert r.json()["filename"] == "renamed.pdf"


def test_rename_public_document_rejected(client):
    pub_doc = _make_document(
        did="pub-doc", visibility="public",
        user_id="00000000-0000-0000-0000-000000000000",
    )

    class Chain:
        def select(self, *_a, **_kw): return self
        def eq(self, *_a, **_kw): return self
        def maybe_single(self): return self
        def execute(self): return _result(pub_doc)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.documents.get_supabase", return_value=mock_db):
        r = client.patch("/api/documents/pub-doc", json={"filename": "bad.pdf"})
    assert r.status_code == 403


def test_move_document(client):
    doc = _make_document(did="d-move")
    target = _make_folder(fid="tgt-1", path="my_documents.tgt_1")
    updated = {**doc, "folder_id": "tgt-1"}

    lookups = [doc, target]

    class Chain:
        def __init__(self, table):
            self.table = table; self.mode = None
        def select(self, *_a, **_kw): self.mode = "select"; return self
        def update(self, _p): self.mode = "update"; return self
        def eq(self, *_a, **_kw): return self
        def maybe_single(self): self.mode = "maybe"; return self
        def single(self): self.mode = "single"; return self
        def execute(self):
            if self.mode == "maybe":
                return _result(lookups.pop(0))
            if self.mode == "single":
                return _result(updated)
            return _result(None)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain(name)

    with patch("routers.documents.get_supabase", return_value=mock_db):
        r = client.patch("/api/documents/d-move/move", json={"folder_id": "tgt-1"})

    assert r.status_code == 200, r.text
    assert r.json()["folder_id"] == "tgt-1"


def test_move_document_to_public_rejected(client):
    doc = _make_document(did="d-move-pub")
    public_target = _make_folder(
        fid=BOARD_GAMES_ROOT_ID, path="board_games", visibility="public",
        user_id="00000000-0000-0000-0000-000000000000",
    )
    lookups = [doc, public_target]

    class Chain:
        def __init__(self, table): self.table = table
        def select(self, *_a, **_kw): return self
        def eq(self, *_a, **_kw): return self
        def maybe_single(self): return self
        def execute(self): return _result(lookups.pop(0))

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain(name)

    with patch("routers.documents.get_supabase", return_value=mock_db):
        r = client.patch(
            "/api/documents/d-move-pub/move",
            json={"folder_id": BOARD_GAMES_ROOT_ID},
        )
    assert r.status_code == 403


def test_move_document_to_root(client):
    """folder_id=null moves doc to root (no folder target validation)."""
    doc = _make_document(did="d-to-root", folder_id="some-folder")
    updated = {**doc, "folder_id": None}

    class Chain:
        def __init__(self): self.mode = None
        def select(self, *_a, **_kw): self.mode = "select"; return self
        def update(self, _p): self.mode = "update"; return self
        def eq(self, *_a, **_kw): return self
        def maybe_single(self): self.mode = "maybe"; return self
        def single(self): self.mode = "single"; return self
        def execute(self):
            if self.mode == "maybe":
                return _result(doc)
            if self.mode == "single":
                return _result(updated)
            return _result(None)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.documents.get_supabase", return_value=mock_db):
        r = client.patch("/api/documents/d-to-root/move", json={"folder_id": None})

    assert r.status_code == 200, r.text
    assert r.json()["folder_id"] is None


def test_bulk_delete_documents(client):
    doc1 = _make_document(did="b-1", filename="a.pdf")
    doc2 = _make_document(did="b-2", filename="b.pdf")
    lookups = [doc1, doc2]

    class Chain:
        def __init__(self): self.mode = None
        def select(self, *_a, **_kw): self.mode = "select"; return self
        def delete(self): self.mode = "delete"; return self
        def eq(self, *_a, **_kw): return self
        def in_(self, *_a, **_kw): self.mode = "in"; return self
        def maybe_single(self): self.mode = "maybe"; return self
        def execute(self):
            if self.mode == "maybe":
                return _result(lookups.pop(0))
            return _result(None)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.documents.get_supabase", return_value=mock_db):
        r = client.post("/api/documents/bulk-delete", json={"ids": ["b-1", "b-2"]})

    assert r.status_code == 200, r.text
    assert r.json()["deleted"] == 2
    mock_db.storage_remove.assert_called()


def test_bulk_delete_with_public_rejected(client):
    doc1 = _make_document(did="b-ok")
    doc_public = _make_document(
        did="b-pub", visibility="public",
        user_id="00000000-0000-0000-0000-000000000000",
    )
    lookups = [doc1, doc_public]

    class Chain:
        def __init__(self): self.mode = None
        def select(self, *_a, **_kw): self.mode = "select"; return self
        def eq(self, *_a, **_kw): return self
        def maybe_single(self): return self
        def execute(self): return _result(lookups.pop(0))

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.documents.get_supabase", return_value=mock_db):
        r = client.post("/api/documents/bulk-delete", json={"ids": ["b-ok", "b-pub"]})

    assert r.status_code == 403
    # Storage.remove should NOT have been called since validation failed
    mock_db.storage_remove.assert_not_called()


def test_bulk_move_documents(client):
    target = _make_folder(fid="bm-tgt", path="my_documents.bm_tgt")
    doc1 = _make_document(did="bm-1")
    doc2 = _make_document(did="bm-2")
    lookups = [target, doc1, doc2]

    class Chain:
        def __init__(self): self.mode = None
        def select(self, *_a, **_kw): self.mode = "select"; return self
        def update(self, _p): self.mode = "update"; return self
        def eq(self, *_a, **_kw): return self
        def in_(self, *_a, **_kw): self.mode = "in"; return self
        def maybe_single(self): return self
        def execute(self):
            if lookups:
                return _result(lookups.pop(0))
            return _result(None)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.documents.get_supabase", return_value=mock_db):
        r = client.post(
            "/api/documents/bulk-move",
            json={"ids": ["bm-1", "bm-2"], "folder_id": "bm-tgt"},
        )

    assert r.status_code == 200, r.text
    assert r.json()["moved"] == 2


def test_bulk_move_to_public_rejected(client):
    public_target = _make_folder(
        fid=BOARD_GAMES_ROOT_ID, path="board_games", visibility="public",
        user_id="00000000-0000-0000-0000-000000000000",
    )

    class Chain:
        def select(self, *_a, **_kw): return self
        def eq(self, *_a, **_kw): return self
        def maybe_single(self): return self
        def execute(self): return _result(public_target)

    mock_db = MockSupabase()
    mock_db.table_handler = lambda name: Chain()

    with patch("routers.documents.get_supabase", return_value=mock_db):
        r = client.post(
            "/api/documents/bulk-move",
            json={"ids": ["x-1"], "folder_id": BOARD_GAMES_ROOT_ID},
        )
    assert r.status_code == 403
