"""Tests for entity disambiguation."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from woograph.extract.disambiguate import disambiguate_entities
from woograph.extract.ner import Entity
from woograph.graph.registry import EntityRegistry


class TestDisambiguateEntities:
    def _make_registry(self, tmp_path: Path) -> EntityRegistry:
        path = tmp_path / "registry.json"
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
        path.write_text(json.dumps(data, indent=2))
        return EntityRegistry(path)

    def test_exact_match_uses_existing_id(self, tmp_path: Path):
        registry = self._make_registry(tmp_path)
        entities = [
            Entity(
                name="John F. Kennedy",
                entity_type="PERSON",
                canonical_id="entity:person-john-f-kennedy",
                mention_count=1,
            )
        ]
        result = disambiguate_entities(entities, registry)
        assert result[0].canonical_id == "entity:person-john-f-kennedy"

    def test_alias_match_uses_existing_id(self, tmp_path: Path):
        registry = self._make_registry(tmp_path)
        entities = [
            Entity(
                name="JFK",
                entity_type="PERSON",
                canonical_id="entity:person-jfk",
                mention_count=1,
            )
        ]
        result = disambiguate_entities(entities, registry)
        assert result[0].canonical_id == "entity:person-john-f-kennedy"

    def test_new_entity_creates_registry_entry(self, tmp_path: Path):
        registry = self._make_registry(tmp_path)
        entities = [
            Entity(
                name="Chester Nimitz",
                entity_type="PERSON",
                canonical_id="entity:person-chester-nimitz",
                mention_count=2,
            )
        ]
        result = disambiguate_entities(entities, registry)
        assert result[0].canonical_id == "entity:person-chester-nimitz"
        # Should now be in registry
        assert registry.lookup("entity:person-chester-nimitz") is not None

    def test_new_entity_has_correct_type(self, tmp_path: Path):
        registry = self._make_registry(tmp_path)
        entities = [
            Entity(
                name="Battle of Midway",
                entity_type="EVENT",
                canonical_id="entity:event-battle-of-midway",
                mention_count=1,
            )
        ]
        disambiguate_entities(entities, registry)
        entry = registry.lookup("entity:event-battle-of-midway")
        assert entry is not None
        assert entry["type"] == "EVENT"

    def test_fuzzy_match_with_claude_confirmation(self, tmp_path: Path):
        """When fuzzy match found, Claude should be asked to confirm."""
        registry = self._make_registry(tmp_path)
        # "John Kennedy" is close to "John F. Kennedy"
        entities = [
            Entity(
                name="John Kennedy",
                entity_type="PERSON",
                canonical_id="entity:person-john-kennedy",
                mention_count=1,
            )
        ]
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Yes")]
        mock_client.messages.create.return_value = mock_response

        result = disambiguate_entities(
            entities, registry, source_context="About JFK's presidency", client=mock_client
        )
        # Should have been reassigned to the existing entity
        assert result[0].canonical_id == "entity:person-john-f-kennedy"
        mock_client.messages.create.assert_called_once()

    def test_fuzzy_match_claude_says_no(self, tmp_path: Path):
        """When Claude says no to fuzzy match, create new entity."""
        registry = self._make_registry(tmp_path)
        entities = [
            Entity(
                name="Robert Kennedy",
                entity_type="PERSON",
                canonical_id="entity:person-robert-kennedy",
                mention_count=1,
            )
        ]
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="No")]
        mock_client.messages.create.return_value = mock_response

        updated = disambiguate_entities(
            entities, registry, source_context="About Bobby Kennedy", client=mock_client
        )
        # Should keep its own ID
        assert updated[0].canonical_id == "entity:person-robert-kennedy"
        assert registry.lookup("entity:person-robert-kennedy") is not None

    def test_no_client_skips_fuzzy_disambiguation(self, tmp_path: Path):
        """Without an API client, fuzzy matches create new entries."""
        registry = self._make_registry(tmp_path)
        entities = [
            Entity(
                name="John Kennedy",
                entity_type="PERSON",
                canonical_id="entity:person-john-kennedy",
                mention_count=1,
            )
        ]
        result = disambiguate_entities(entities, registry, client=None)
        # Without Claude, should create new entry
        assert result[0].canonical_id == "entity:person-john-kennedy"
        assert registry.lookup("entity:person-john-kennedy") is not None

    def test_multiple_entities_processed(self, tmp_path: Path):
        registry = self._make_registry(tmp_path)
        entities = [
            Entity(
                name="John F. Kennedy",
                entity_type="PERSON",
                canonical_id="entity:person-john-f-kennedy",
                mention_count=1,
            ),
            Entity(
                name="USS Enterprise",
                entity_type="FAC",
                canonical_id="entity:place-uss-enterprise",
                mention_count=1,
            ),
        ]
        result = disambiguate_entities(entities, registry)
        assert len(result) == 2
