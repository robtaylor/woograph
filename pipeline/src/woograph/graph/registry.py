"""Entity registry for cross-source disambiguation."""

import json
import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

logger = logging.getLogger(__name__)


class EntityRegistry:
    """CRUD interface for the entity registry JSON file."""

    def __init__(self, registry_path: Path) -> None:
        self.path = registry_path
        self.data = self._load()

    def _load(self) -> dict:
        """Load registry from disk, or create empty if missing."""
        if not self.path.exists():
            logger.info("Registry file not found at %s, creating empty", self.path)
            return {"entities": {}, "last_updated": None}
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupt registry at %s, starting fresh", self.path)
            return {"entities": {}, "last_updated": None}

    def save(self) -> None:
        """Persist registry to disk."""
        self.data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2) + "\n")

    def lookup(self, canonical_id: str) -> dict | None:
        """Look up an entity by canonical ID."""
        return self.data["entities"].get(canonical_id)

    def lookup_by_name(self, name: str, entity_type: str) -> dict | None:
        """Look up by primary name or alias, filtered by type."""
        for entry in self.data["entities"].values():
            if entry.get("type") != entity_type:
                continue
            if entry["name"] == name:
                return entry
            if name in entry.get("aliases", []):
                return entry
        return None

    def find_fuzzy_matches(
        self, name: str, entity_type: str, threshold: float = 0.8
    ) -> list[dict]:
        """Find entities with similar names using SequenceMatcher."""
        matches = []
        for canonical_id, entry in self.data["entities"].items():
            if entry.get("type") != entity_type:
                continue
            # Check primary name
            ratio = SequenceMatcher(None, name.lower(), entry["name"].lower()).ratio()
            if ratio >= threshold:
                matches.append({**entry, "canonical_id": canonical_id, "score": ratio})
                continue
            # Check aliases
            for alias in entry.get("aliases", []):
                ratio = SequenceMatcher(None, name.lower(), alias.lower()).ratio()
                if ratio >= threshold:
                    matches.append(
                        {**entry, "canonical_id": canonical_id, "score": ratio}
                    )
                    break
        # Sort by score descending
        matches.sort(key=lambda m: m["score"], reverse=True)
        return matches

    def add_entity(
        self,
        canonical_id: str,
        name: str,
        entity_type: str,
        aliases: list[str] | None = None,
        sources: list[str] | None = None,
    ) -> None:
        """Add a new entity to the registry."""
        self.data["entities"][canonical_id] = {
            "name": name,
            "type": entity_type,
            "aliases": aliases or [],
            "sources": sources or [],
        }

    def add_alias(self, canonical_id: str, alias: str) -> None:
        """Add an alias to an existing entity (no duplicates)."""
        entry = self.data["entities"].get(canonical_id)
        if entry is None:
            logger.warning("Cannot add alias: entity %s not found", canonical_id)
            return
        if alias not in entry["aliases"]:
            entry["aliases"].append(alias)
