"""PDF to markdown conversion using pymupdf4llm."""

import logging
from pathlib import Path

import pymupdf4llm

logger = logging.getLogger(__name__)


def convert_pdf(pdf_path: Path, output_dir: Path) -> Path:
    """Convert a PDF file to markdown using pymupdf4llm.

    Extracts text content and images from the PDF. The markdown is saved
    to output_dir/content.md and images are saved to output_dir/images/.

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
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)

    logger.info("Converting PDF: %s", pdf_path.name)

    try:
        md_text = pymupdf4llm.to_markdown(
            str(pdf_path),
            write_images=True,
            image_path=str(images_dir),
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to convert PDF '{pdf_path.name}': {exc}"
        ) from exc

    content_path = output_dir / "content.md"
    if isinstance(md_text, list):
        md_text = "\n\n".join(str(chunk) for chunk in md_text)
    content_path.write_text(md_text)

    logger.info(
        "PDF converted: %d chars, images in %s", len(md_text), images_dir
    )
    return content_path
