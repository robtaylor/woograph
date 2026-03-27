"""Git utilities for detecting changed submissions."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def get_changed_submissions(repo_root: Path) -> list[Path]:
    """Find submission YAML files that changed in the last commit.

    Uses `git diff HEAD~1 HEAD` to detect new or modified submission
    YAML files in the submissions/ directory.

    Args:
        repo_root: Root of the git repository.

    Returns:
        List of paths to changed submission YAML files.
    """
    try:
        result = subprocess.run(
            [
                "git", "diff", "--name-only", "--diff-filter=AM",
                "HEAD~1", "HEAD", "--", "submissions/*.yaml",
            ],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning("git diff failed: %s", exc.stderr.strip())
        return []
    except FileNotFoundError:
        logger.warning("git not found on PATH")
        return []

    paths: list[Path] = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if line and line.endswith(".yaml"):
            # Skip the schema file
            if line.endswith("_schema.yaml"):
                continue
            full_path = repo_root / line
            if full_path.exists():
                paths.append(full_path)

    logger.info("Found %d changed submissions", len(paths))
    return paths
