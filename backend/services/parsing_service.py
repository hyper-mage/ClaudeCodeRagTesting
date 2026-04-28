import os
import logging
import tempfile
from pathlib import Path

# Windows symlink workaround: force HuggingFace Hub to use file copies
# instead of symlinks (avoids WinError 1314 without Developer Mode)
if os.name == "nt":
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    import huggingface_hub.file_download as _hf_fd
    _hf_fd._are_symlinks_supported_in_dir.update(
        {str(Path.home() / ".cache" / "huggingface" / "hub"): False}
    )

logger = logging.getLogger(__name__)

# Local models directory (avoids Windows symlink issues with HF cache)
_MODELS_DIR = Path(__file__).parent.parent / ".models"

# Lazy-initialized converter (heavy to construct)
_converter = None


def _get_converter():
    global _converter
    if _converter is None:
        from docling.document_converter import (
            DocumentConverter, PdfFormatOption, ImageFormatOption, ExcelFormatOption
        )
        from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions
        from docling.datamodel.base_models import InputFormat

        pdf_options = PdfPipelineOptions()
        # Pin OCR engine to Tesseract. Docling 2.82's default RapidOCR (3.8.1)
        # ships an arch_config.yaml that no longer recognizes the PP-OCRv4 model
        # layout `docling-tools models download` fetches, producing
        # "architecture ch_PP-OCRv4_det_infer is not in arch_config.yaml" at parse time.
        # Tesseract uses OS-managed apt tessdata (no Docling model cache), so it is
        # immune to docling/rapidocr version drift. See docs/ocr-decision.md.
        pdf_options.ocr_options = TesseractCliOcrOptions()
        if _MODELS_DIR.exists():
            pdf_options.artifacts_path = _MODELS_DIR

        _converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF, InputFormat.DOCX, InputFormat.HTML,
                InputFormat.MD, InputFormat.IMAGE, InputFormat.XLSX,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
                InputFormat.IMAGE: ImageFormatOption(),
                InputFormat.XLSX: ExcelFormatOption(),
            }
        )
    return _converter


# MIME types that need a temp file on disk (binary formats)
_FILE_BASED = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
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
