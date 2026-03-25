from config import get_settings
from database import get_supabase
from services.embedding_service import get_embeddings
from services.metadata_service import extract_metadata_safe
from services.record_manager import hash_chunk, get_existing_chunk_hashes, diff_chunks
import uuid


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Recursive character splitting: split on paragraph breaks, then newlines, then sentences, then chars."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    separators = ["\n\n", "\n", ". ", " ", ""]
    chunks = []

    for sep in separators:
        if sep == "":
            # Last resort: hard split by character count
            for i in range(0, len(text), chunk_size - chunk_overlap):
                chunk = text[i:i + chunk_size]
                if chunk.strip():
                    chunks.append(chunk.strip())
            return chunks

        parts = text.split(sep)
        if len(parts) == 1:
            continue

        # Merge parts into chunks of chunk_size
        current = ""
        for part in parts:
            candidate = current + sep + part if current else part
            if len(candidate) > chunk_size and current:
                chunks.append(current.strip())
                # Overlap: take end of current chunk
                if chunk_overlap > 0 and len(current) > chunk_overlap:
                    current = current[-chunk_overlap:] + sep + part
                else:
                    current = part
            else:
                current = candidate
        if current.strip():
            chunks.append(current.strip())

        if chunks:
            return chunks

    return [text] if text.strip() else []


def process_document(doc_id: str, user_id: str) -> None:
    """Process a document: chunk text, generate embeddings, store chunks.
    Self-contained — can be called inline or from a background task."""
    db = get_supabase()
    settings = get_settings()

    try:
        # Update status to processing
        db.table("documents").update({"status": "processing"}).eq("id", doc_id).execute()

        # Get document record
        doc = db.table("documents").select("*").eq("id", doc_id).single().execute()
        storage_path = doc.data["storage_path"]
        mime_type = doc.data["mime_type"]

        # Validate file type
        supported_types = ["text/plain", "text/markdown"]
        if mime_type not in supported_types:
            raise ValueError(f"Unsupported file type: {mime_type}. Supported: .txt, .md")

        # Download file from storage
        file_bytes = db.storage.from_("documents").download(storage_path)
        text = file_bytes.decode("utf-8")

        if not text.strip():
            raise ValueError("Document is empty")

        # Extract metadata via LLM
        metadata = extract_metadata_safe(text)
        metadata_dict = metadata.model_dump()

        # Store metadata on document record
        db.table("documents").update({"metadata": metadata_dict}).eq("id", doc_id).execute()

        # Chunk the text
        chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ValueError("No chunks generated from document")

        # Generate embeddings in batches
        batch_size = 100
        all_embeddings = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            embeddings = get_embeddings(batch)
            all_embeddings.extend(embeddings)

        # Insert chunks with embeddings
        chunk_rows = []
        for i, (chunk_text_content, embedding) in enumerate(zip(chunks, all_embeddings)):
            chunk_rows.append({
                "document_id": doc_id,
                "user_id": user_id,
                "content": chunk_text_content,
                "chunk_index": i,
                "embedding": embedding,
                "content_hash": hash_chunk(chunk_text_content),
                "metadata": {"filename": doc.data["filename"], "chunk_index": i, **metadata_dict},
            })

        # Insert in batches
        for i in range(0, len(chunk_rows), 100):
            batch = chunk_rows[i:i + 100]
            db.table("document_chunks").insert(batch).execute()

        # Update document status
        db.table("documents").update({
            "status": "completed",
            "chunk_count": len(chunks),
        }).eq("id", doc_id).execute()

    except Exception as e:
        db.table("documents").update({
            "status": "failed",
            "error_message": str(e),
        }).eq("id", doc_id).execute()
        raise


def process_document_incremental(new_doc_id: str, user_id: str, old_doc_id: str) -> None:
    """Incremental processing: diff chunks, embed only new ones, reuse unchanged."""
    db = get_supabase()
    settings = get_settings()

    try:
        # Update status to processing
        db.table("documents").update({"status": "processing"}).eq("id", new_doc_id).execute()

        # Get new document record
        doc = db.table("documents").select("*").eq("id", new_doc_id).single().execute()
        storage_path = doc.data["storage_path"]

        # Download + chunk new file
        file_bytes = db.storage.from_("documents").download(storage_path)
        text = file_bytes.decode("utf-8")

        if not text.strip():
            raise ValueError("Document is empty")

        # Extract metadata via LLM
        metadata = extract_metadata_safe(text)
        metadata_dict = metadata.model_dump()

        # Store metadata on document record
        db.table("documents").update({"metadata": metadata_dict}).eq("id", new_doc_id).execute()

        chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ValueError("No chunks generated from document")

        # Hash each new chunk
        new_chunk_hashes = [hash_chunk(c) for c in chunks]

        # Get old chunk hashes
        old_hashes = get_existing_chunk_hashes(old_doc_id)

        # Diff
        new_indices, stale_ids = diff_chunks(old_hashes, new_chunk_hashes)

        # Delete stale chunks from old document
        if stale_ids:
            for stale_id in stale_ids:
                db.table("document_chunks").delete().eq("id", stale_id).execute()

        # Re-parent surviving chunks (update document_id + chunk_index to new doc)
        surviving_hashes = {h: cid for h, cid in old_hashes.items() if h in set(new_chunk_hashes)}
        for i, ch in enumerate(new_chunk_hashes):
            if ch in surviving_hashes:
                db.table("document_chunks").update({
                    "document_id": new_doc_id,
                    "chunk_index": i,
                }).eq("id", surviving_hashes[ch]).execute()

        # Embed + insert only new chunks
        if new_indices:
            new_texts = [chunks[i] for i in new_indices]
            batch_size = 100
            all_embeddings = []
            for i in range(0, len(new_texts), batch_size):
                batch = new_texts[i:i + batch_size]
                embeddings = get_embeddings(batch)
                all_embeddings.extend(embeddings)

            chunk_rows = []
            for idx_in_new, embed_idx in enumerate(new_indices):
                chunk_rows.append({
                    "document_id": new_doc_id,
                    "user_id": user_id,
                    "content": chunks[embed_idx],
                    "chunk_index": embed_idx,
                    "embedding": all_embeddings[idx_in_new],
                    "content_hash": new_chunk_hashes[embed_idx],
                    "metadata": {"filename": doc.data["filename"], "chunk_index": embed_idx, **metadata_dict},
                })

            for i in range(0, len(chunk_rows), 100):
                batch = chunk_rows[i:i + 100]
                db.table("document_chunks").insert(batch).execute()

        # Delete old document record + storage file
        old_doc = db.table("documents").select("storage_path").eq("id", old_doc_id).single().execute()
        try:
            db.storage.from_("documents").remove([old_doc.data["storage_path"]])
        except Exception:
            pass  # Storage file may already be gone
        db.table("documents").delete().eq("id", old_doc_id).execute()

        # Update new document status to completed
        db.table("documents").update({
            "status": "completed",
            "chunk_count": len(chunks),
        }).eq("id", new_doc_id).execute()

    except Exception as e:
        db.table("documents").update({
            "status": "failed",
            "error_message": str(e),
        }).eq("id", new_doc_id).execute()
        raise
