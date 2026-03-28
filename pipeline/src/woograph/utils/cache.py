"""LLM response caching to avoid redundant API calls."""

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class LLMCache:
    """File-based cache for LLM responses, keyed by content hash."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _hash_key(self, *args: str) -> str:
        """SHA256 hash of concatenated args."""
        combined = "\n---\n".join(args)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def _path_for(self, key_hash: str) -> Path:
        return self.cache_dir / f"{key_hash}.json"

    def get(self, *key_parts: str) -> dict | list | None:
        """Look up cached response. Returns None if not cached."""
        key_hash = self._hash_key(*key_parts)
        path = self._path_for(key_hash)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupt cache entry %s, ignoring", key_hash)
            return None

    def put(self, value: dict | list, *key_parts: str) -> None:
        """Cache a response."""
        key_hash = self._hash_key(*key_parts)
        path = self._path_for(key_hash)
        path.write_text(json.dumps(value, indent=2))
