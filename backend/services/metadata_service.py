import json
import logging
from config import get_settings
from models.schemas import DocumentMetadata
from services.llm_service import get_llm_client

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a document classifier. Analyze the document text and extract metadata.

Return a JSON object with exactly these fields:

- "document_type": one of "technical_documentation", "meeting_notes", "research_paper", "tutorial", "email", "general"
  - "technical_documentation": API docs, READMEs, specs, architecture docs, changelogs
  - "meeting_notes": meeting minutes, agendas, action items, standup notes
  - "research_paper": academic papers, studies, literature reviews, whitepapers
  - "tutorial": how-to guides, walkthroughs, lessons, courses, educational content, speeches/presentations
  - "email": email threads, newsletters, correspondence
  - "general": anything that doesn't clearly fit the above categories
- "topic": a short phrase (3-6 words) describing the main subject
- "keywords": array of 3-5 specific keywords from the document
- "summary": one sentence summarizing the document
- "language": ISO 639-1 code (e.g. "en", "es", "fr")

Respond with ONLY the JSON object, no markdown fences or extra text."""


def extract_metadata(text: str) -> DocumentMetadata:
    """Call LLM to extract structured metadata from document text."""
    settings = get_settings()
    client = get_llm_client()

    # Truncate to first 4000 chars to keep cost low
    truncated = text[:4000]

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": truncated},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    # Parse and validate through Pydantic
    data = json.loads(content)
    return DocumentMetadata.model_validate(data)


def extract_metadata_safe(text: str) -> DocumentMetadata:
    """Extract metadata with graceful fallback — never blocks ingestion."""
    try:
        result = extract_metadata(text)
        logger.info(f"Metadata extracted: type={result.document_type}, topic={result.topic}")
        return result
    except Exception as e:
        logger.warning(f"Metadata extraction failed, using defaults: {e}")
        return DocumentMetadata()
