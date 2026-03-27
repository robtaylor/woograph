"""Tests for submission YAML validation."""

from pathlib import Path

import yaml

from woograph.utils.validate import validate_submission


class TestValidateSubmission:
    """Tests for validate_submission function."""

    def test_valid_pdf_submission(
        self, sample_submission: Path, schema_path: Path
    ) -> None:
        """Valid PDF submission passes schema validation.

        The semantic check for the actual PDF file will fail since the
        fixture PDF doesn't exist, but schema-level validation should pass.
        """
        errors = validate_submission(sample_submission, schema_path)
        # Only semantic "not found" errors expected, not schema errors
        schema_errors = [e for e in errors if "not found" not in e]
        assert schema_errors == []

    def test_valid_url_submission(
        self, sample_url_submission: Path, schema_path: Path
    ) -> None:
        """Valid URL submission passes validation."""
        errors = validate_submission(sample_url_submission, schema_path)
        assert errors == []

    def test_valid_account_submission(
        self, sample_account_submission: Path, schema_path: Path
    ) -> None:
        """Valid account submission passes validation (companion .md exists)."""
        errors = validate_submission(sample_account_submission, schema_path)
        assert errors == []

    def test_missing_required_field(
        self, schema_path: Path, tmp_path: Path
    ) -> None:
        """Submission missing required fields fails validation."""
        bad_yaml = tmp_path / "bad.yaml"
        # Missing date_added (required by schema)
        bad_yaml.write_text(yaml.dump({"source": {"title": "Test"}}))
        errors = validate_submission(bad_yaml, schema_path)
        assert len(errors) > 0
        assert any("required" in e.lower() or "type" in e.lower() for e in errors)

    def test_invalid_source_type(
        self, schema_path: Path, tmp_path: Path
    ) -> None:
        """Submission with invalid source type fails validation."""
        bad_yaml = tmp_path / "bad.yaml"
        data = {
            "source": {
                "title": "Test",
                "type": "fax",
                "date_added": "2026-03-26",
            }
        }
        bad_yaml.write_text(yaml.dump(data))
        errors = validate_submission(bad_yaml, schema_path)
        assert len(errors) > 0
        assert any("fax" in e for e in errors)

    def test_url_type_requires_url_field(
        self, schema_path: Path, tmp_path: Path
    ) -> None:
        """URL-type submission without url field fails validation.

        The schema uses allOf/if/then to require 'url' when type is 'url'.
        """
        bad_yaml = tmp_path / "bad.yaml"
        data = {
            "source": {
                "title": "Test",
                "type": "url",
                "date_added": "2026-03-26",
            }
        }
        bad_yaml.write_text(yaml.dump(data))
        errors = validate_submission(bad_yaml, schema_path)
        assert any("url" in e.lower() for e in errors)

    def test_pdf_type_requires_file_field(
        self, schema_path: Path, tmp_path: Path
    ) -> None:
        """PDF-type submission without file field fails validation.

        The schema uses allOf/if/then to require 'file' when type is 'pdf'.
        """
        bad_yaml = tmp_path / "bad.yaml"
        data = {
            "source": {
                "title": "Test",
                "type": "pdf",
                "date_added": "2026-03-26",
            }
        }
        bad_yaml.write_text(yaml.dump(data))
        errors = validate_submission(bad_yaml, schema_path)
        assert any("file" in e.lower() for e in errors)

    def test_empty_yaml_file(
        self, schema_path: Path, tmp_path: Path
    ) -> None:
        """Empty YAML file returns an error."""
        empty_yaml = tmp_path / "empty.yaml"
        empty_yaml.write_text("")
        errors = validate_submission(empty_yaml, schema_path)
        assert len(errors) > 0

    def test_invalid_yaml_syntax(
        self, schema_path: Path, tmp_path: Path
    ) -> None:
        """Malformed YAML does not crash the validator."""
        bad_yaml = tmp_path / "malformed.yaml"
        bad_yaml.write_text("source:\n  title: [unterminated")
        errors = validate_submission(bad_yaml, schema_path)
        # Should not crash regardless of parse outcome
        assert isinstance(errors, list)

    def test_account_missing_companion_md(
        self, schema_path: Path, tmp_path: Path
    ) -> None:
        """Account-type submission without companion .md fails semantic check."""
        bad_yaml = tmp_path / "my-story.yaml"
        data = {
            "source": {
                "title": "My Story",
                "type": "account",
                "date_added": "2026-03-26",
            }
        }
        bad_yaml.write_text(yaml.dump(data))
        # No companion .md file created
        errors = validate_submission(bad_yaml, schema_path)
        assert any("companion" in e.lower() or "markdown" in e.lower() for e in errors)

    def test_minimal_valid_url_submission(
        self, schema_path: Path, tmp_path: Path
    ) -> None:
        """Minimal valid URL submission with only required fields passes."""
        good_yaml = tmp_path / "minimal.yaml"
        data = {
            "source": {
                "title": "Example",
                "type": "url",
                "url": "https://example.com",
                "date_added": "2026-03-26",
            }
        }
        good_yaml.write_text(yaml.dump(data))
        errors = validate_submission(good_yaml, schema_path)
        assert errors == []
