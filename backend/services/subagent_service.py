import logging
import openai
from database import get_supabase
from services.llm_service import get_llm_client
from config import get_settings

try:
    from langsmith import traceable
except ImportError:
    def traceable(func=None, **kwargs):
        if func:
            return func
        return lambda f: f

logger = logging.getLogger(__name__)


def resolve_document(user_id: str, document_name: str) -> dict | None:
    """Find a document by name (case-insensitive) for the given user."""
    db = get_supabase()
    result = (
        db.table("documents")
        .select("id, filename, status")
        .eq("user_id", user_id)
        .eq("status", "completed")
        .ilike("filename", f"%{document_name}%")
        .execute()
    )
    if not result.data:
        return None
    if len(result.data) == 1:
        return result.data[0]
    # Multiple matches — return list for disambiguation
    return {"multiple": True, "matches": [r["filename"] for r in result.data]}


def get_full_document_text(user_id: str, document_id: str) -> str:
    """Reassemble full document text from chunks, ordered by chunk_index."""
    db = get_supabase()
    result = (
        db.table("document_chunks")
        .select("content")
        .eq("document_id", document_id)
        .eq("user_id", user_id)
        .order("chunk_index")
        .execute()
    )
    return "\n\n".join(chunk["content"] for chunk in result.data)


@traceable(name="subagent_document_analysis")
def run_document_analysis(user_id: str, document_name: str, analysis_query: str) -> dict:
    """Spawn an isolated sub-agent to analyze a full document."""
    settings = get_settings()

    # Resolve document
    doc = resolve_document(user_id, document_name)
    if doc is None:
        return {"error": f"Document not found: {document_name}"}
    if isinstance(doc, dict) and doc.get("multiple"):
        return {
            "error": f"Multiple documents match '{document_name}'. Please be more specific.",
            "matches": doc["matches"],
        }

    # Get full text
    full_text = get_full_document_text(user_id, doc["id"])
    chunk_count = len(full_text.split("\n\n"))

    if len(full_text) > settings.subagent_max_context_chars:
        full_text = full_text[: settings.subagent_max_context_chars]
        full_text += "\n\n[Document truncated due to size limit]"

    # Build sub-agent messages
    messages = [
        {"role": "system", "content": settings.subagent_system_prompt},
        {
            "role": "user",
            "content": (
                f"Document: {doc['filename']}\n\n"
                f"---\n{full_text}\n---\n\n"
                f"Task: {analysis_query}"
            ),
        },
    ]

    # Non-streaming completion with timeout
    client = get_llm_client()
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            max_tokens=settings.subagent_max_tokens,
            timeout=settings.subagent_timeout,
        )
    except openai.APITimeoutError:
        logger.warning(f"Document analysis timed out for '{doc['filename']}'")
        return {"error": "Document analysis timed out. The document may be too large for analysis."}

    analysis = response.choices[0].message.content
    return {
        "document": doc["filename"],
        "chunk_count": chunk_count,
        "analysis": analysis,
    }
