"""Tests for Claude API relationship extraction."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from woograph.extract.ner import Entity
from woograph.extract.relationships import (
    PREDICATES,
    Relationship,
    chunk_text_with_entities,
    extract_relationships,
)
from woograph.utils.cache import LLMCache


def _make_entities() -> list[Entity]:
    return [
        Entity(
            name="Chester Nimitz",
            entity_type="PERSON",
            canonical_id="entity:person-chester-nimitz",
            spans=[(10, 25)],
            context_snippets=["Admiral Chester Nimitz commanded the fleet"],
            mention_count=3,
        ),
        Entity(
            name="Battle of Midway",
            entity_type="EVENT",
            canonical_id="entity:event-battle-of-midway",
            spans=[(100, 116)],
            context_snippets=["The Battle of Midway was a turning point"],
            mention_count=2,
        ),
        Entity(
            name="Pacific Ocean",
            entity_type="LOC",
            canonical_id="entity:place-pacific-ocean",
            spans=[(200, 213)],
            context_snippets=["across the Pacific Ocean"],
            mention_count=1,
        ),
    ]


SAMPLE_TEXT = (
    "In 1942, Admiral Chester Nimitz took command of the Pacific Fleet. "
    "He played a crucial role in the Battle of Midway, which was fought in the "
    "Pacific Ocean. This victory turned the tide of the war in the Pacific Theater."
)


class TestChunkTextWithEntities:
    def test_returns_chunks_with_entity_annotations(self):
        entities = _make_entities()
        chunks = chunk_text_with_entities(SAMPLE_TEXT, entities, max_chunk_tokens=200)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert "text" in chunk
            assert "entities" in chunk

    def test_filters_chunks_with_fewer_than_two_entities(self):
        """Chunks with <2 entities should be excluded."""
        # Single entity, short text
        single = [
            Entity(
                name="Nimitz",
                entity_type="PERSON",
                canonical_id="entity:person-nimitz",
                spans=[(5, 11)],
                mention_count=1,
            )
        ]
        text = "Only Nimitz is mentioned here."
        chunks = chunk_text_with_entities(text, single, max_chunk_tokens=200)
        assert len(chunks) == 0

    def test_chunk_text_not_empty(self):
        entities = _make_entities()
        chunks = chunk_text_with_entities(SAMPLE_TEXT, entities, max_chunk_tokens=200)
        for chunk in chunks:
            assert len(chunk["text"]) > 0

    def test_each_chunk_has_at_least_two_entities(self):
        entities = _make_entities()
        chunks = chunk_text_with_entities(SAMPLE_TEXT, entities, max_chunk_tokens=200)
        for chunk in chunks:
            assert len(chunk["entities"]) >= 2


class TestExtractRelationships:
    def _mock_anthropic_response(self, relationships_json: list[dict]):
        """Create a mock Anthropic client that returns the given JSON."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=json.dumps(relationships_json))
        ]
        mock_client.messages.create.return_value = mock_response
        return mock_client

    def test_extracts_relationships_from_chunks(self):
        mock_client = self._mock_anthropic_response([
            {
                "subject": "Chester Nimitz",
                "predicate": "participated_in",
                "object": "Battle of Midway",
                "confidence": 0.95,
            }
        ])
        entities = _make_entities()
        chunks = [
            {
                "text": SAMPLE_TEXT,
                "entities": entities[:2],
            }
        ]
        rels = extract_relationships(
            chunks, "source:test", client=mock_client
        )
        assert len(rels) == 1
        assert rels[0].subject == "entity:person-chester-nimitz"
        assert rels[0].predicate == "participated_in"
        assert rels[0].object == "entity:event-battle-of-midway"
        assert rels[0].confidence == 0.95
        assert rels[0].extracted_by == "claude-haiku"

    def test_cache_hit_skips_api_call(self, tmp_path: Path):
        cache = LLMCache(tmp_path / "cache")
        cached_data = [
            {
                "subject": "Chester Nimitz",
                "predicate": "commanded",
                "object": "Battle of Midway",
                "confidence": 0.9,
            }
        ]
        entities = _make_entities()[:2]
        chunk = {"text": SAMPLE_TEXT, "entities": entities}

        # Pre-populate cache
        entity_names = sorted(e.name for e in entities)
        cache.put(cached_data, chunk["text"], str(entity_names))

        mock_client = MagicMock()
        rels = extract_relationships(
            [chunk], "source:test", client=mock_client, cache=cache
        )
        # API should NOT have been called
        mock_client.messages.create.assert_not_called()
        assert len(rels) == 1

    def test_api_error_skips_chunk_gracefully(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        entities = _make_entities()[:2]
        chunks = [{"text": SAMPLE_TEXT, "entities": entities}]
        rels = extract_relationships(
            chunks, "source:test", client=mock_client
        )
        # Should return empty list, not raise
        assert rels == []

    def test_invalid_predicate_filtered(self):
        mock_client = self._mock_anthropic_response([
            {
                "subject": "Chester Nimitz",
                "predicate": "loves",  # not a valid predicate
                "object": "Battle of Midway",
                "confidence": 0.8,
            }
        ])
        entities = _make_entities()[:2]
        chunks = [{"text": SAMPLE_TEXT, "entities": entities}]
        rels = extract_relationships(
            chunks, "source:test", client=mock_client
        )
        assert len(rels) == 0

    def test_unknown_entity_in_response_skipped(self):
        mock_client = self._mock_anthropic_response([
            {
                "subject": "Unknown Person",
                "predicate": "participated_in",
                "object": "Battle of Midway",
                "confidence": 0.9,
            }
        ])
        entities = _make_entities()[:2]
        chunks = [{"text": SAMPLE_TEXT, "entities": entities}]
        rels = extract_relationships(
            chunks, "source:test", client=mock_client
        )
        assert len(rels) == 0


class TestRelationshipDataclass:
    def test_fields(self):
        r = Relationship(
            subject="entity:person-a",
            predicate="related_to",
            object="entity:person-b",
            confidence=0.8,
            extracted_by="claude-haiku",
            source_id="source:test",
        )
        assert r.subject == "entity:person-a"
        assert r.predicate == "related_to"
        assert r.object == "entity:person-b"
        assert r.confidence == 0.8


class TestPredicates:
    def test_predicates_not_empty(self):
        assert len(PREDICATES) > 0

    def test_known_predicates_present(self):
        assert "participated_in" in PREDICATES
        assert "member_of" in PREDICATES
        assert "located_in" in PREDICATES
        assert "commanded" in PREDICATES
