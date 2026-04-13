"""Folder CRUD router.

Endpoints:
- GET    /api/folders              - list all visible folders (user-private + public)
- POST   /api/folders               - create a private folder
- GET    /api/folders/{id}/contents - list subfolders + documents of a folder
- PATCH  /api/folders/{id}          - rename folder (private only)
- PATCH  /api/folders/{id}/move     - move folder (private only)
- DELETE /api/folders/{id}          - delete folder with cascade (private only)

Public/Board Games folders are read-only. Mutation attempts return 403.
Path scheme (per RESEARCH.md Pattern 3): root-level private folders use
`my_documents.{sanitized_name}`; nested folders append `.{sanitized_name}`
to the parent path. User isolation is enforced by `UNIQUE(user_id, path)`
plus user_id scoping on all queries.
"""
import re
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException

from auth import get_user_id
from database import get_supabase
from models.folder_models import (
    FolderCreate,
    FolderRename,
    FolderMove,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/folders", tags=["folders"])


def _sanitize_label(name: str) -> str:
    """Convert a folder name into a valid ltree label.

    ltree labels must be alphanumeric + underscore. Lowercase, replace
    anything non-alphanumeric with underscore, collapse consecutive
    underscores, strip leading/trailing underscores.
    """
    label = name.lower()
    label = re.sub(r"[^a-z0-9]+", "_", label)
    label = re.sub(r"_+", "_", label)
    label = label.strip("_")
    if not label:
        label = "folder"
    return label


def _get_folder_or_404(db, folder_id: str):
    result = (
        db.table("folders")
        .select("*")
        .eq("id", folder_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Folder not found")
    return result.data


def _ensure_owned_private(folder: dict, user_id: str) -> None:
    if folder.get("visibility") == "public":
        raise HTTPException(
            status_code=403,
            detail="Cannot modify read-only (public) folders",
        )
    if folder.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")


@router.get("")
async def list_folders(user_id: str = Depends(get_user_id)):
    """List user-private folders + all public folders (flat list)."""
    db = get_supabase()
    result = (
        db.table("folders")
        .select("*")
        .or_(f"user_id.eq.{user_id},visibility.eq.public")
        .order("path")
        .execute()
    )
    return result.data or []


@router.post("")
async def create_folder(
    body: FolderCreate,
    user_id: str = Depends(get_user_id),
):
    """Create a new private folder.

    Root-level path scheme: `my_documents.{label}`
    Nested path scheme:     `{parent.path}.{label}`
    """
    db = get_supabase()
    folder_id = str(uuid.uuid4())
    label = _sanitize_label(body.name)

    if body.parent_id:
        parent = _get_folder_or_404(db, body.parent_id)
        if parent.get("visibility") == "public":
            raise HTTPException(
                status_code=403,
                detail="Cannot create folders in read-only areas",
            )
        if parent.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Not allowed")
        path = f"{parent['path']}.{label}"
    else:
        path = f"my_documents.{label}"

    insert = (
        db.table("folders")
        .insert(
            {
                "id": folder_id,
                "user_id": user_id,
                "name": body.name,
                "path": path,
                "parent_id": body.parent_id,
                "visibility": "private",
            }
        )
        .execute()
    )
    data = insert.data
    if isinstance(data, list):
        return data[0] if data else {"id": folder_id, "path": path, "name": body.name}
    return data


@router.get("/{folder_id}/contents")
async def get_folder_contents(
    folder_id: str,
    user_id: str = Depends(get_user_id),
):
    """Return the folder itself plus its immediate subfolders and documents."""
    db = get_supabase()
    folder = _get_folder_or_404(db, folder_id)
    # Visibility check: user must own OR folder must be public
    if folder.get("visibility") != "public" and folder.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Folder not found")

    subfolders = (
        db.table("folders")
        .select("*")
        .eq("parent_id", folder_id)
        .or_(f"user_id.eq.{user_id},visibility.eq.public")
        .order("name")
        .execute()
    )
    documents = (
        db.table("documents")
        .select("*")
        .eq("folder_id", folder_id)
        .or_(f"user_id.eq.{user_id},visibility.eq.public")
        .order("filename")
        .execute()
    )

    return {
        "folder": folder,
        "subfolders": subfolders.data or [],
        "documents": documents.data or [],
    }


def _replace_path_prefix(old_path: str, new_prefix_old: str, new_prefix_new: str) -> str:
    """Replace leading `new_prefix_old` in `old_path` with `new_prefix_new`."""
    return new_prefix_new + old_path[len(new_prefix_old):]


@router.patch("/{folder_id}")
async def rename_folder(
    folder_id: str,
    body: FolderRename,
    user_id: str = Depends(get_user_id),
):
    """Rename a private folder. Updates the folder's ltree label and cascades
    the path change to all descendants."""
    db = get_supabase()
    folder = _get_folder_or_404(db, folder_id)
    _ensure_owned_private(folder, user_id)

    old_path = folder["path"]
    new_label = _sanitize_label(body.name)
    # Replace only last segment of path
    if "." in old_path:
        prefix, _last = old_path.rsplit(".", 1)
        new_path = f"{prefix}.{new_label}"
    else:
        new_path = new_label

    # Update self
    db.table("folders").update(
        {"name": body.name, "path": new_path}
    ).eq("id", folder_id).execute()

    # Update descendants
    if new_path != old_path:
        descendants = (
            db.table("folders")
            .select("id, path")
            .eq("user_id", user_id)
            .like("path", f"{old_path}.%")
            .execute()
        )
        for desc in descendants.data or []:
            updated_path = _replace_path_prefix(desc["path"], old_path, new_path)
            db.table("folders").update({"path": updated_path}).eq(
                "id", desc["id"]
            ).execute()

    updated = (
        db.table("folders")
        .select("*")
        .eq("id", folder_id)
        .single()
        .execute()
    )
    return updated.data


@router.patch("/{folder_id}/move")
async def move_folder(
    folder_id: str,
    body: FolderMove,
    user_id: str = Depends(get_user_id),
):
    """Move a private folder to a new parent (or to user root).

    Updates the folder's path AND all descendant paths.
    Storage paths are not affected (D-15).
    """
    db = get_supabase()
    folder = _get_folder_or_404(db, folder_id)
    _ensure_owned_private(folder, user_id)

    old_path = folder["path"]
    # Extract current label (last segment) so we preserve the folder's own name
    label = old_path.rsplit(".", 1)[-1] if "." in old_path else old_path

    if body.new_parent_id:
        new_parent = _get_folder_or_404(db, body.new_parent_id)
        _ensure_owned_private(new_parent, user_id)
        new_path = f"{new_parent['path']}.{label}"
        new_parent_id = body.new_parent_id
    else:
        new_path = f"my_documents.{label}"
        new_parent_id = None

    # Update self
    db.table("folders").update(
        {"parent_id": new_parent_id, "path": new_path}
    ).eq("id", folder_id).execute()

    # Update descendants
    if new_path != old_path:
        descendants = (
            db.table("folders")
            .select("id, path")
            .eq("user_id", user_id)
            .like("path", f"{old_path}.%")
            .execute()
        )
        for desc in descendants.data or []:
            updated_path = _replace_path_prefix(desc["path"], old_path, new_path)
            db.table("folders").update({"path": updated_path}).eq(
                "id", desc["id"]
            ).execute()

    updated = (
        db.table("folders")
        .select("*")
        .eq("id", folder_id)
        .single()
        .execute()
    )
    return updated.data


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: str,
    user_id: str = Depends(get_user_id),
):
    """Cascade-delete a private folder: remove storage files for all
    contained documents (including those in descendant folders), then
    delete the folder. Child folders + document rows + chunks cascade
    via FK constraints."""
    db = get_supabase()
    folder = _get_folder_or_404(db, folder_id)
    _ensure_owned_private(folder, user_id)

    folder_path = folder["path"]

    # Collect descendant folder IDs
    descendants = (
        db.table("folders")
        .select("id")
        .eq("user_id", user_id)
        .like("path", f"{folder_path}.%")
        .execute()
    )
    all_folder_ids = [folder_id] + [d["id"] for d in (descendants.data or [])]

    # Collect all documents inside this folder tree
    docs = (
        db.table("documents")
        .select("id, storage_path")
        .in_("folder_id", all_folder_ids)
        .execute()
    )
    storage_paths = [d["storage_path"] for d in (docs.data or []) if d.get("storage_path")]

    # Remove storage objects first
    if storage_paths:
        try:
            db.storage.from_("documents").remove(storage_paths)
        except Exception as e:
            logger.warning(f"Storage cleanup partial failure: {e}")

    # Delete the folder (child folders, documents, and chunks cascade via FK)
    db.table("folders").delete().eq("id", folder_id).execute()
    return None
