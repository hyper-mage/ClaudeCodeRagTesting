"""Tests for extended parsing format support (IMAGE OCR, XLSX).

Validates that the parsing service correctly registers IMAGE and XLSX
formats in the Docling converter and _FILE_BASED dict, and that
unsupported MIME types raise ValueError.
"""
import pytest


def test_image_png_in_file_based():
    """image/png must be registered in _FILE_BASED dict."""
    from services.parsing_service import _FILE_BASED

    assert "image/png" in _FILE_BASED, "image/png not in _FILE_BASED"
    assert _FILE_BASED["image/png"] == ".png"


def test_image_jpeg_in_file_based():
    """image/jpeg must be registered in _FILE_BASED dict."""
    from services.parsing_service import _FILE_BASED

    assert "image/jpeg" in _FILE_BASED, "image/jpeg not in _FILE_BASED"
    assert _FILE_BASED["image/jpeg"] == ".jpg"


def test_xlsx_in_file_based():
    """XLSX MIME type must be registered in _FILE_BASED dict."""
    from services.parsing_service import _FILE_BASED

    xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert xlsx_mime in _FILE_BASED, f"{xlsx_mime} not in _FILE_BASED"
    assert _FILE_BASED[xlsx_mime] == ".xlsx"


def test_unsupported_mime_raises():
    """Unsupported MIME type should raise ValueError."""
    from services.parsing_service import extract_text

    with pytest.raises(ValueError, match="Unsupported MIME type"):
        extract_text(b"data", "application/zip", "test.zip")


def test_mime_map_includes_image_and_xlsx():
    """Upload router mime_map must include image and XLSX extensions."""
    from routers.documents import mime_map

    assert ".jpg" in mime_map, ".jpg not in mime_map"
    assert mime_map[".jpg"] == "image/jpeg"
    assert ".jpeg" in mime_map, ".jpeg not in mime_map"
    assert mime_map[".jpeg"] == "image/jpeg"
    assert ".png" in mime_map, ".png not in mime_map"
    assert mime_map[".png"] == "image/png"
    assert ".xlsx" in mime_map, ".xlsx not in mime_map"
    assert mime_map[".xlsx"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
