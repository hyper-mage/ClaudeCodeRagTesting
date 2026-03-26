import os
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Local models directory (avoids Windows symlink issues with HF cache)
_MODELS_DIR = Path(__file__).parent.parent / ".models"

# Lazy-initialized converter (heavy to construct)
_converter = None


def _get_converter():
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat

        pdf_options = PdfPipelineOptions()
        if _MODELS_DIR.exists():
            pdf_options.artifacts_path = _MODELS_DIR

        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
            }
        )
    return _converter


# MIME types that need a temp file on disk (binary formats)
_FILE_BASED = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}

# MIME types that can be converted from a string
_STRING_BASED = {
    "text/markdown": None,  # mapped to InputFormat below
    "text/html": None,
}


def extract_text(file_bytes: bytes, mime_type: str, filename: str) -> str:
    """Convert file bytes to text using docling (or plain decode for .txt).

    Returns extracted text as a string.
    Raises ValueError on unsupported type or empty result.
    """
    # Plain text: skip docling entirely
    if mime_type == "text/plain":
        return file_bytes.decode("utf-8")

    from docling.datamodel.base_models import InputFormat

    converter = _get_converter()

    # String-based formats (HTML, Markdown)
    if mime_type in _STRING_BASED:
        decoded = file_bytes.decode("utf-8")
        fmt = {
            "text/markdown": InputFormat.MD,
            "text/html": InputFormat.HTML,
        }[mime_type]
        result = converter.convert_string(decoded, format=fmt)
        text = result.document.export_to_markdown()

    # File-based formats (PDF, DOCX)
    elif mime_type in _FILE_BASED:
        suffix = _FILE_BASED[mime_type]
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        try:
            tmp.write(file_bytes)
            tmp.close()
            result = converter.convert(tmp.name)
            text = result.document.export_to_markdown()
        finally:
            os.unlink(tmp.name)

    else:
        raise ValueError(f"Unsupported MIME type for parsing: {mime_type}")

    if not text or not text.strip():
        raise ValueError(f"No text extracted from {filename}")

    logger.info(f"Extracted {len(text)} chars from '{filename}' ({mime_type})")
    return text
