"""Tests for source conversion modules."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from woograph.convert.account import convert_account
from woograph.convert.pdf import convert_pdf
from woograph.convert.web import convert_url


class TestAccountConverter:
    """Tests for the account (markdown passthrough) converter."""

    def test_copies_markdown_to_output(self, tmp_output: Path) -> None:
        """Account converter copies the markdown file to content.md."""
        source_md = tmp_output.parent / "account.md"
        source_md.write_text("# My Story\n\nThis is my account.\n")

        result = convert_account(source_md, tmp_output)

        assert result == tmp_output / "content.md"
        assert result.exists()
        assert result.read_text() == "# My Story\n\nThis is my account.\n"

    def test_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        """Account converter creates the output directory."""
        source_md = tmp_path / "account.md"
        source_md.write_text("# Story\n")
        output_dir = tmp_path / "nested" / "output"

        result = convert_account(source_md, output_dir)

        assert result.exists()
        assert output_dir.exists()

    def test_raises_on_missing_source(self, tmp_output: Path) -> None:
        """Account converter raises FileNotFoundError for missing file."""
        missing = tmp_output / "nonexistent.md"

        with pytest.raises(FileNotFoundError):
            convert_account(missing, tmp_output)

    def test_preserves_content(self, tmp_output: Path) -> None:
        """Account converter preserves the exact content of the source."""
        content = "# Title\n\nParagraph with unicode: cafe\n\n## Section 2\n"
        source_md = tmp_output.parent / "narrative.md"
        source_md.write_text(content)

        result = convert_account(source_md, tmp_output)
        assert result.read_text() == content


class TestPdfConverter:
    """Tests for the PDF converter."""

    def test_raises_on_missing_pdf(self, tmp_output: Path) -> None:
        """PDF converter raises FileNotFoundError for missing file."""
        missing = tmp_output / "nonexistent.pdf"

        with pytest.raises(FileNotFoundError):
            convert_pdf(missing, tmp_output)

    @patch("woograph.convert.pdf.pymupdf4llm")
    def test_converts_pdf_to_markdown(
        self, mock_pymupdf: MagicMock, tmp_path: Path
    ) -> None:
        """PDF converter calls pymupdf4llm and writes content.md."""
        # Create a fake PDF file (just needs to exist)
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        output_dir = tmp_path / "output"

        mock_pymupdf.to_markdown.return_value = "# Extracted Content\n\nSome text.\n"

        result = convert_pdf(pdf_file, output_dir)

        assert result == output_dir / "content.md"
        assert result.exists()
        assert "Extracted Content" in result.read_text()
        mock_pymupdf.to_markdown.assert_called_once()

    @patch("woograph.convert.pdf.pymupdf4llm")
    def test_creates_images_directory(
        self, mock_pymupdf: MagicMock, tmp_path: Path
    ) -> None:
        """PDF converter creates an images/ subdirectory."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        output_dir = tmp_path / "output"

        mock_pymupdf.to_markdown.return_value = "# Content\n"

        convert_pdf(pdf_file, output_dir)

        assert (output_dir / "images").is_dir()

    @patch("woograph.convert.pdf.pymupdf4llm")
    def test_handles_conversion_error(
        self, mock_pymupdf: MagicMock, tmp_path: Path
    ) -> None:
        """PDF converter wraps pymupdf4llm errors in RuntimeError."""
        pdf_file = tmp_path / "corrupt.pdf"
        pdf_file.write_bytes(b"not a pdf")
        output_dir = tmp_path / "output"

        mock_pymupdf.to_markdown.side_effect = Exception("Corrupt PDF")

        with pytest.raises(RuntimeError, match="Failed to convert PDF"):
            convert_pdf(pdf_file, output_dir)


class TestWebConverter:
    """Tests for the URL/web converter."""

    def test_raises_on_empty_url(self, tmp_output: Path) -> None:
        """Web converter raises ValueError for empty URL."""
        with pytest.raises(ValueError, match="URL must not be empty"):
            convert_url("", tmp_output)

    @patch("woograph.convert.web.trafilatura")
    def test_converts_url_to_markdown(
        self, mock_traf: MagicMock, tmp_output: Path
    ) -> None:
        """Web converter fetches URL and writes content.md."""
        mock_traf.fetch_url.return_value = "<html><body>Hello</body></html>"
        mock_traf.extract.return_value = "Hello world content"

        result = convert_url("https://example.com/article", tmp_output)

        assert result == tmp_output / "content.md"
        assert result.exists()
        content = result.read_text()
        assert "Hello world content" in content
        assert "example.com" in content
        mock_traf.fetch_url.assert_called_once_with("https://example.com/article")

    @patch("woograph.convert.web.trafilatura")
    def test_raises_on_fetch_failure(
        self, mock_traf: MagicMock, tmp_output: Path
    ) -> None:
        """Web converter raises RuntimeError when fetch fails."""
        mock_traf.fetch_url.return_value = None

        with pytest.raises(RuntimeError, match="Failed to fetch"):
            convert_url("https://example.com/broken", tmp_output)

    @patch("woograph.convert.web.trafilatura")
    def test_raises_on_extraction_failure(
        self, mock_traf: MagicMock, tmp_output: Path
    ) -> None:
        """Web converter raises RuntimeError when extraction returns None."""
        mock_traf.fetch_url.return_value = "<html></html>"
        mock_traf.extract.return_value = None

        with pytest.raises(RuntimeError, match="Failed to extract"):
            convert_url("https://example.com/empty", tmp_output)
