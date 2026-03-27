"""Shared test fixtures for WooGraph pipeline tests."""

from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def sample_submission(fixtures_dir: Path) -> Path:
    """Return path to the sample PDF submission YAML."""
    return fixtures_dir / "sample-submission.yaml"


@pytest.fixture
def sample_url_submission(fixtures_dir: Path) -> Path:
    """Return path to the sample URL submission YAML."""
    return fixtures_dir / "sample-url-submission.yaml"


@pytest.fixture
def sample_account_submission(fixtures_dir: Path) -> Path:
    """Return path to the sample account submission YAML."""
    return fixtures_dir / "sample-account-submission.yaml"


@pytest.fixture
def schema_path() -> Path:
    """Return path to the submission schema."""
    return Path(__file__).parent.parent.parent / "submissions" / "_schema.yaml"


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    """Return a temporary output directory for converter tests."""
    out = tmp_path / "output"
    out.mkdir()
    return out
