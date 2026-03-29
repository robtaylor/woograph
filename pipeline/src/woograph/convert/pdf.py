"""PDF to markdown conversion with auto-detection of digital vs scanned PDFs.

Strategy:
- Try pymupdf4llm first (fast, works on digital/text PDFs)
- If the extracted text is too short relative to page count, the PDF is likely
  scanned - fall back to Marker (Surya OCR) for high-quality OCR
- Override with WOOGRAPH_PDF_BACKEND=pymupdf|marker to force a specific backend
"""

import logging
import os
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

# Minimum chars per page to consider a PDF as having usable digital text
_MIN_CHARS_PER_PAGE = 200

# Cache Marker models at module level (expensive to load)
_marker_converter = None
_marker_failed = False


def _get_marker_converter():
    """Lazy-load Marker converter with model dict."""
    global _marker_converter, _marker_failed  # noqa: PLW0603
    if _marker_converter is not None:
        return _marker_converter
    if _marker_failed:
        return None
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict

        logger.info("Loading Marker OCR models (first use may download ~2GB)...")
        artifact_dict = create_model_dict()
        _marker_converter = PdfConverter(artifact_dict=artifact_dict)
        logger.info("Marker OCR models loaded")
        return _marker_converter
    except Exception as exc:
        logger.warning("Failed to load Marker, will use pymupdf4llm: %s", exc)
        _marker_failed = True
        return None


def _is_digital_pdf(pdf_path: Path) -> bool:
    """Check if a PDF has extractable digital text.

    Opens the PDF with pymupdf and checks if the average text per page
    exceeds a threshold. Scanned PDFs will have little or no extractable text.
    """
    try:
        doc = pymupdf.open(str(pdf_path))
        total_chars = sum(len(page.get_text()) for page in doc)
        page_count = max(len(doc), 1)
        doc.close()
        chars_per_page = total_chars / page_count
        logger.debug(
            "%s: %d chars across %d pages (%.0f chars/page)",
            pdf_path.name, total_chars, page_count, chars_per_page,
        )
        return chars_per_page >= _MIN_CHARS_PER_PAGE
    except Exception:
        return False


def _convert_with_marker(pdf_path: Path, output_dir: Path) -> str:
    """Convert PDF using Marker (Surya OCR). Returns markdown text."""
    converter = _get_marker_converter()
    assert converter is not None
    result = converter(str(pdf_path))
    # Save any images from Marker output
    images_dir = output_dir / "images"
    if hasattr(result, "images") and result.images:
        images_dir.mkdir(exist_ok=True)
        for name, img in result.images.items():
            img.save(images_dir / name)
    return result.markdown


def _convert_with_pymupdf(pdf_path: Path, output_dir: Path) -> str:
    """Convert PDF using pymupdf4llm (fast, works on digital PDFs). Returns markdown text."""
    import pymupdf4llm

    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)
    md_text = pymupdf4llm.to_markdown(
        str(pdf_path),
        write_images=True,
        image_path=str(images_dir),
    )
    if isinstance(md_text, list):
        md_text = "\n\n".join(str(chunk) for chunk in md_text)
    return md_text


def convert_pdf(pdf_path: Path, output_dir: Path) -> Path:
    """Convert a PDF file to markdown, auto-detecting the best approach.

    Auto mode (default):
    - Checks if PDF has digital text (pymupdf text extraction)
    - Digital PDFs: uses pymupdf4llm (fast)
    - Scanned PDFs: uses Marker/Surya OCR (accurate)

    Override with WOOGRAPH_PDF_BACKEND=pymupdf|marker to force a backend.

    Args:
        pdf_path: Path to the input PDF file.
        output_dir: Directory to write the output files.

    Returns:
        Path to the generated content.md file.

    Raises:
        FileNotFoundError: If the PDF file does not exist.
        RuntimeError: If the PDF cannot be processed.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    backend = os.environ.get("WOOGRAPH_PDF_BACKEND", "auto").lower()

    if backend == "auto":
        if _is_digital_pdf(pdf_path):
            backend = "pymupdf"
            logger.info("Converting PDF: %s (auto → pymupdf, digital text detected)", pdf_path.name)
        elif _get_marker_converter() is not None:
            backend = "marker"
            logger.info("Converting PDF: %s (auto → marker, scanned/image PDF)", pdf_path.name)
        else:
            backend = "pymupdf"
            logger.info("Converting PDF: %s (auto → pymupdf, marker unavailable)", pdf_path.name)
    else:
        logger.info("Converting PDF: %s (backend=%s)", pdf_path.name, backend)

    try:
        if backend == "marker":
            if _get_marker_converter() is not None:
                md_text = _convert_with_marker(pdf_path, output_dir)
            else:
                logger.warning("Marker unavailable, falling back to pymupdf4llm")
                md_text = _convert_with_pymupdf(pdf_path, output_dir)
        else:
            md_text = _convert_with_pymupdf(pdf_path, output_dir)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to convert PDF '{pdf_path.name}': {exc}"
        ) from exc

    content_path = output_dir / "content.md"
    content_path.write_text(md_text)

    logger.info("PDF converted: %d chars", len(md_text))
    return content_path
