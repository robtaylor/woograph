"""Personal account (markdown) passthrough converter."""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_account(account_md_path: Path, output_dir: Path) -> Path:
    """Copy a personal account markdown file to the output directory.

    For 'account' type submissions, the contributor writes their narrative
    in a companion .md file. This converter simply copies it to
    output_dir/content.md.

    Args:
        account_md_path: Path to the source markdown file.
        output_dir: Directory to write the output file.

    Returns:
        Path to the copied content.md file.

    Raises:
        FileNotFoundError: If the source markdown file does not exist.
    """
    if not account_md_path.exists():
        raise FileNotFoundError(
            f"Account markdown not found: {account_md_path}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    content_path = output_dir / "content.md"

    shutil.copy2(account_md_path, content_path)

    logger.info(
        "Account copied: %s -> %s", account_md_path.name, content_path
    )
    return content_path
