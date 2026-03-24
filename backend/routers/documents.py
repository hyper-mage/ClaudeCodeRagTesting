import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from auth import get_user_id
from database import get_supabase
from services.ingestion_service import process_document

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id),
):
    db = get_supabase()
    doc_id = str(uuid.uuid4())

    # Determine mime type
    mime_map = {
        ".txt": "text/plain",
        ".md": "text/markdown",
    }
    filename = file.filename or "unnamed"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_type = mime_map.get(ext)

    if not mime_type:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: .txt, .md"
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Upload to Supabase Storage
    storage_path = f"{user_id}/{doc_id}/{filename}"
    db.storage.from_("documents").upload(
        path=storage_path,
        file=content,
        file_options={"content-type": mime_type},
    )

    # Create document record
    doc = db.table("documents").insert({
        "id": doc_id,
        "user_id": user_id,
        "filename": filename,
        "storage_path": storage_path,
        "file_size": file_size,
        "mime_type": mime_type,
        "status": "pending",
    }).execute()

    # Process document (synchronous for now)
    try:
        process_document(doc_id, user_id)
    except Exception:
        pass  # Status already set to 'failed' inside process_document

    # Return updated document
    result = db.table("documents").select("*").eq("id", doc_id).single().execute()
    return result.data


@router.get("")
async def list_documents(user_id: str = Depends(get_user_id)):
    db = get_supabase()
    result = (
        db.table("documents")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/{doc_id}")
async def get_document(doc_id: str, user_id: str = Depends(get_user_id)):
    db = get_supabase()
    result = (
        db.table("documents")
        .select("*")
        .eq("id", doc_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    return result.data


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str, user_id: str = Depends(get_user_id)):
    db = get_supabase()

    # Get document
    doc = (
        db.table("documents")
        .select("*")
        .eq("id", doc_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not doc.data:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from storage
    try:
        db.storage.from_("documents").remove([doc.data["storage_path"]])
    except Exception:
        pass  # Storage file may already be gone

    # Delete document (chunks cascade-deleted)
    db.table("documents").delete().eq("id", doc_id).execute()
