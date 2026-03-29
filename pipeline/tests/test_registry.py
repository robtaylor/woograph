"""Tests for entity registry CRUD operations."""

import json
from pathlib import Path

from woograph.graph.registry import EntityRegistry


class TestEntityRegistry:
    def _make_registry_file(self, tmp_path: Path) -> Path:
        """Create a registry file with some seed data."""
        registry_path = tmp_path / "registry.json"
        data = {
            "entities": {
                "entity:person-john-f-kennedy": {
                    "name": "John F. Kennedy",
                    "type": "PERSON",
                    "aliases": ["JFK", "Kennedy", "President Kennedy"],
                    "sources": ["source:jfk-file-001"],
                }
            },
            "last_updated": "2026-03-27T00:00:00+00:00",
        }
        registry_path.write_text(json.dumps(data, indent=2))
        return registry_path

    def _make_empty_registry(self, tmp_path: Path) -> Path:
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps({"entities": {}, "last_updated": None}))
        return registry_path

    def test_load_existing(self, tmp_path: Path):
        path = self._make_registry_file(tmp_path)
        reg = EntityRegistry(path)
        assert "entity:person-john-f-kennedy" in reg.data["entities"]

    def test_load_empty(self, tmp_path: Path):
        path = self._make_empty_registry(tmp_path)
        reg = EntityRegistry(path)
        assert reg.data["entities"] == {}

    def test_save_roundtrip(self, tmp_path: Path):
        path = self._make_empty_registry(tmp_path)
        reg = EntityRegistry(path)
        reg.add_entity("entity:person-test", "Test Person", "PERSON")
        reg.save()

        # Reload from disk
        reg2 = EntityRegistry(path)
        assert reg2.lookup("entity:person-test") is not None

    def test_lookup_by_id(self, tmp_path: Path):
        path = self._make_registry_file(tmp_path)
        reg = EntityRegistry(path)
        entry = reg.lookup("entity:person-john-f-kennedy")
        assert entry is not None
        assert entry["name"] == "John F. Kennedy"

    def test_lookup_by_id_missing(self, tmp_path: Path):
        path = self._make_registry_file(tmp_path)
        reg = EntityRegistry(path)
        assert reg.lookup("entity:person-nobody") is None

    def test_lookup_by_name(self, tmp_path: Path):
        path = self._make_registry_file(tmp_path)
        reg = EntityRegistry(path)
        entry = reg.lookup_by_name("John F. Kennedy", "PERSON")
        assert entry is not None
        assert entry["name"] == "John F. Kennedy"

    def test_lookup_by_name_alias(self, tmp_path: Path):
        path = self._make_registry_file(tmp_path)
        reg = EntityRegistry(path)
        entry = reg.lookup_by_name("JFK", "PERSON")
        assert entry is not None
        assert entry["name"] == "John F. Kennedy"

    def test_lookup_by_name_wrong_type(self, tmp_path: Path):
        path = self._make_registry_file(tmp_path)
        reg = EntityRegistry(path)
        assert reg.lookup_by_name("John F. Kennedy", "ORG") is None

    def test_add_entity(self, tmp_path: Path):
        path = self._make_empty_registry(tmp_path)
        reg = EntityRegistry(path)
        reg.add_entity(
            "entity:person-chester-nimitz",
            "Chester Nimitz",
            "PERSON",
            aliases=["Admiral Nimitz"],
        )
        entry = reg.lookup("entity:person-chester-nimitz")
        assert entry is not None
        assert entry["name"] == "Chester Nimitz"
        assert "Admiral Nimitz" in entry["aliases"]

    def test_add_alias(self, tmp_path: Path):
        path = self._make_registry_file(tmp_path)
        reg = EntityRegistry(path)
        reg.add_alias("entity:person-john-f-kennedy", "Jack Kennedy")
        entry = reg.lookup("entity:person-john-f-kennedy")
        assert entry is not None
        assert "Jack Kennedy" in entry["aliases"]

    def test_add_alias_no_duplicate(self, tmp_path: Path):
        path = self._make_registry_file(tmp_path)
        reg = EntityRegistry(path)
        reg.add_alias("entity:person-john-f-kennedy", "JFK")
        entry = reg.lookup("entity:person-john-f-kennedy")
        assert entry is not None
        assert entry["aliases"].count("JFK") == 1

    def test_find_fuzzy_matches(self, tmp_path: Path):
        path = self._make_registry_file(tmp_path)
        reg = EntityRegistry(path)
        # "John Kennedy" should fuzzy-match "John F. Kennedy"
        matches = reg.find_fuzzy_matches("John Kennedy", "PERSON", threshold=0.7)
        assert len(matches) >= 1
        assert matches[0]["name"] == "John F. Kennedy"

    def test_find_fuzzy_matches_no_match(self, tmp_path: Path):
        path = self._make_registry_file(tmp_path)
        reg = EntityRegistry(path)
        matches = reg.find_fuzzy_matches("Completely Different", "PERSON", threshold=0.9)
        assert len(matches) == 0

    def test_find_fuzzy_matches_wrong_type(self, tmp_path: Path):
        path = self._make_registry_file(tmp_path)
        reg = EntityRegistry(path)
        matches = reg.find_fuzzy_matches("John F. Kennedy", "ORG", threshold=0.5)
        assert len(matches) == 0

    def test_load_creates_file_if_missing(self, tmp_path: Path):
        path = tmp_path / "nonexistent.json"
        reg = EntityRegistry(path)
        assert reg.data["entities"] == {}
