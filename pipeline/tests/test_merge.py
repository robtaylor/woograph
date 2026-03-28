"""Tests for global graph merge and stats generation."""

import json
from pathlib import Path

from woograph.graph.merge import generate_stats, merge_global_graph


def _write_fragment(path: Path, fragment: dict) -> None:
    """Helper to write a fragment JSON-LD file."""
    path.write_text(json.dumps(fragment, indent=2) + "\n")


def _make_fragment(
    source_id: str,
    source_name: str,
    entities: list[dict],
    relationships: list[dict] | None = None,
) -> dict:
    """Build a minimal fragment dict for testing."""
    fragment: dict = {
        "@context": "../context.jsonld",
        "@id": source_id,
        "name": source_name,
        "entities": entities,
    }
    if relationships:
        fragment["relationships"] = relationships
    return fragment


def _make_context(tmp_path: Path) -> Path:
    """Write a minimal context.jsonld and return its path."""
    context_path = tmp_path / "context.jsonld"
    context_path.write_text(
        json.dumps(
            {
                "@context": {
                    "@vocab": "https://schema.org/",
                    "woo": "https://woograph.github.io/ontology/",
                }
            },
            indent=2,
        )
        + "\n"
    )
    return context_path


class TestMergeEmptyFragments:
    def test_zero_fragments_returns_empty_graph(self, tmp_path: Path) -> None:
        fragments_dir = tmp_path / "fragments"
        fragments_dir.mkdir()
        context_path = _make_context(tmp_path)

        result = merge_global_graph(fragments_dir, context_path)

        assert "@context" in result
        assert result["entities"] == []
        assert result["relationships"] == []

    def test_nonexistent_fragments_dir_returns_empty(self, tmp_path: Path) -> None:
        fragments_dir = tmp_path / "fragments"  # does not exist
        context_path = _make_context(tmp_path)

        result = merge_global_graph(fragments_dir, context_path)

        assert result["entities"] == []
        assert result["relationships"] == []


class TestMergeSingleFragment:
    def test_preserves_all_entities(self, tmp_path: Path) -> None:
        fragments_dir = tmp_path / "fragments"
        fragments_dir.mkdir()
        context_path = _make_context(tmp_path)

        fragment = _make_fragment(
            "source:nimitz-bio",
            "Nimitz Biography",
            entities=[
                {
                    "@id": "entity:person-chester-nimitz",
                    "@type": "Person",
                    "name": "Chester Nimitz",
                    "aliases": [],
                    "mentionedIn": "source:nimitz-bio",
                },
                {
                    "@id": "entity:place-texas",
                    "@type": "Place",
                    "name": "Texas",
                    "aliases": [],
                    "mentionedIn": "source:nimitz-bio",
                },
            ],
        )
        _write_fragment(fragments_dir / "nimitz-bio.jsonld", fragment)

        result = merge_global_graph(fragments_dir, context_path)

        assert len(result["entities"]) == 2
        ids = {e["@id"] for e in result["entities"]}
        assert "entity:person-chester-nimitz" in ids
        assert "entity:place-texas" in ids

    def test_preserves_relationships(self, tmp_path: Path) -> None:
        fragments_dir = tmp_path / "fragments"
        fragments_dir.mkdir()
        context_path = _make_context(tmp_path)

        fragment = _make_fragment(
            "source:nimitz-bio",
            "Nimitz Biography",
            entities=[
                {
                    "@id": "entity:person-chester-nimitz",
                    "@type": "Person",
                    "name": "Chester Nimitz",
                    "aliases": [],
                    "mentionedIn": "source:nimitz-bio",
                },
            ],
            relationships=[
                {
                    "@type": "woo:Relationship",
                    "subject": {"@id": "entity:person-chester-nimitz"},
                    "predicate": "woo:bornIn",
                    "object": {"@id": "entity:place-texas"},
                    "confidence": 0.95,
                    "extractedBy": "claude-haiku",
                },
            ],
        )
        _write_fragment(fragments_dir / "nimitz-bio.jsonld", fragment)

        result = merge_global_graph(fragments_dir, context_path)

        assert len(result["relationships"]) == 1
        rel = result["relationships"][0]
        assert rel["subject"]["@id"] == "entity:person-chester-nimitz"
        assert rel["predicate"] == "woo:bornIn"

    def test_entity_mentioned_in_is_list(self, tmp_path: Path) -> None:
        """After merge, mentionedIn should always be a list."""
        fragments_dir = tmp_path / "fragments"
        fragments_dir.mkdir()
        context_path = _make_context(tmp_path)

        fragment = _make_fragment(
            "source:nimitz-bio",
            "Nimitz Biography",
            entities=[
                {
                    "@id": "entity:person-chester-nimitz",
                    "@type": "Person",
                    "name": "Chester Nimitz",
                    "aliases": [],
                    "mentionedIn": "source:nimitz-bio",
                },
            ],
        )
        _write_fragment(fragments_dir / "nimitz-bio.jsonld", fragment)

        result = merge_global_graph(fragments_dir, context_path)

        entity = result["entities"][0]
        assert isinstance(entity["mentionedIn"], list)
        assert entity["mentionedIn"] == ["source:nimitz-bio"]


class TestMergeDeduplication:
    def test_deduplicates_entities_by_id(self, tmp_path: Path) -> None:
        fragments_dir = tmp_path / "fragments"
        fragments_dir.mkdir()
        context_path = _make_context(tmp_path)

        frag1 = _make_fragment(
            "source:nimitz-bio",
            "Nimitz Biography",
            entities=[
                {
                    "@id": "entity:person-chester-nimitz",
                    "@type": "Person",
                    "name": "Chester Nimitz",
                    "aliases": [],
                    "mentionedIn": "source:nimitz-bio",
                },
            ],
        )
        frag2 = _make_fragment(
            "source:midway-battle",
            "Battle of Midway",
            entities=[
                {
                    "@id": "entity:person-chester-nimitz",
                    "@type": "Person",
                    "name": "Chester Nimitz",
                    "aliases": [],
                    "mentionedIn": "source:midway-battle",
                },
                {
                    "@id": "entity:place-midway",
                    "@type": "Place",
                    "name": "Midway Atoll",
                    "aliases": [],
                    "mentionedIn": "source:midway-battle",
                },
            ],
        )
        _write_fragment(fragments_dir / "nimitz-bio.jsonld", frag1)
        _write_fragment(fragments_dir / "midway-battle.jsonld", frag2)

        result = merge_global_graph(fragments_dir, context_path)

        # Should have 2 unique entities, not 3
        assert len(result["entities"]) == 2
        ids = {e["@id"] for e in result["entities"]}
        assert ids == {"entity:person-chester-nimitz", "entity:place-midway"}

    def test_merges_mentioned_in_lists(self, tmp_path: Path) -> None:
        fragments_dir = tmp_path / "fragments"
        fragments_dir.mkdir()
        context_path = _make_context(tmp_path)

        frag1 = _make_fragment(
            "source:nimitz-bio",
            "Nimitz Biography",
            entities=[
                {
                    "@id": "entity:person-chester-nimitz",
                    "@type": "Person",
                    "name": "Chester Nimitz",
                    "aliases": [],
                    "mentionedIn": "source:nimitz-bio",
                },
            ],
        )
        frag2 = _make_fragment(
            "source:midway-battle",
            "Battle of Midway",
            entities=[
                {
                    "@id": "entity:person-chester-nimitz",
                    "@type": "Person",
                    "name": "Chester Nimitz",
                    "aliases": [],
                    "mentionedIn": "source:midway-battle",
                },
            ],
        )
        _write_fragment(fragments_dir / "nimitz-bio.jsonld", frag1)
        _write_fragment(fragments_dir / "midway-battle.jsonld", frag2)

        result = merge_global_graph(fragments_dir, context_path)

        nimitz = [e for e in result["entities"] if e["@id"] == "entity:person-chester-nimitz"][0]
        assert isinstance(nimitz["mentionedIn"], list)
        assert set(nimitz["mentionedIn"]) == {"source:nimitz-bio", "source:midway-battle"}

    def test_duplicate_relationships_keep_highest_confidence(self, tmp_path: Path) -> None:
        fragments_dir = tmp_path / "fragments"
        fragments_dir.mkdir()
        context_path = _make_context(tmp_path)

        rel_base = {
            "@type": "woo:Relationship",
            "subject": {"@id": "entity:person-chester-nimitz"},
            "predicate": "woo:commandedAt",
            "object": {"@id": "entity:event-battle-of-midway"},
        }

        frag1 = _make_fragment(
            "source:nimitz-bio",
            "Nimitz Biography",
            entities=[],
            relationships=[{**rel_base, "confidence": 0.7, "extractedBy": "claude-haiku"}],
        )
        frag2 = _make_fragment(
            "source:midway-battle",
            "Battle of Midway",
            entities=[],
            relationships=[{**rel_base, "confidence": 0.95, "extractedBy": "claude-sonnet"}],
        )
        _write_fragment(fragments_dir / "nimitz-bio.jsonld", frag1)
        _write_fragment(fragments_dir / "midway-battle.jsonld", frag2)

        result = merge_global_graph(fragments_dir, context_path)

        assert len(result["relationships"]) == 1
        assert result["relationships"][0]["confidence"] == 0.95

    def test_duplicate_relationships_merge_sources(self, tmp_path: Path) -> None:
        fragments_dir = tmp_path / "fragments"
        fragments_dir.mkdir()
        context_path = _make_context(tmp_path)

        rel_base = {
            "@type": "woo:Relationship",
            "subject": {"@id": "entity:person-chester-nimitz"},
            "predicate": "woo:commandedAt",
            "object": {"@id": "entity:event-battle-of-midway"},
        }

        frag1 = _make_fragment(
            "source:nimitz-bio",
            "Nimitz Biography",
            entities=[],
            relationships=[{**rel_base, "confidence": 0.7, "extractedBy": "claude-haiku"}],
        )
        frag2 = _make_fragment(
            "source:midway-battle",
            "Battle of Midway",
            entities=[],
            relationships=[{**rel_base, "confidence": 0.95, "extractedBy": "claude-sonnet"}],
        )
        _write_fragment(fragments_dir / "nimitz-bio.jsonld", frag1)
        _write_fragment(fragments_dir / "midway-battle.jsonld", frag2)

        result = merge_global_graph(fragments_dir, context_path)

        rel = result["relationships"][0]
        assert "sources" in rel
        assert set(rel["sources"]) == {"source:nimitz-bio", "source:midway-battle"}


class TestMergeContextHandling:
    def test_uses_context_from_file(self, tmp_path: Path) -> None:
        fragments_dir = tmp_path / "fragments"
        fragments_dir.mkdir()
        context_path = _make_context(tmp_path)

        result = merge_global_graph(fragments_dir, context_path)

        # Should embed the context object, not a path reference
        assert isinstance(result["@context"], dict)
        assert "@vocab" in result["@context"]


class TestGenerateStats:
    def test_stats_totals(self) -> None:
        global_graph = {
            "@context": {},
            "entities": [
                {"@id": "entity:person-nimitz", "@type": "Person", "name": "Nimitz", "mentionedIn": ["source:a"]},
                {"@id": "entity:place-texas", "@type": "Place", "name": "Texas", "mentionedIn": ["source:a", "source:b"]},
            ],
            "relationships": [
                {
                    "@type": "woo:Relationship",
                    "subject": {"@id": "entity:person-nimitz"},
                    "predicate": "woo:bornIn",
                    "object": {"@id": "entity:place-texas"},
                    "confidence": 0.9,
                    "sources": ["source:a"],
                },
            ],
        }

        stats = generate_stats(global_graph)

        assert stats["total_entities"] == 2
        assert stats["total_relationships"] == 1

    def test_stats_sources_count(self) -> None:
        global_graph = {
            "@context": {},
            "entities": [
                {"@id": "e1", "@type": "Person", "mentionedIn": ["source:a"]},
                {"@id": "e2", "@type": "Place", "mentionedIn": ["source:a", "source:b"]},
            ],
            "relationships": [],
        }

        stats = generate_stats(global_graph)

        assert stats["total_sources"] == 2

    def test_stats_entities_by_type(self) -> None:
        global_graph = {
            "@context": {},
            "entities": [
                {"@id": "e1", "@type": "Person", "mentionedIn": ["source:a"]},
                {"@id": "e2", "@type": "Person", "mentionedIn": ["source:a"]},
                {"@id": "e3", "@type": "Place", "mentionedIn": ["source:a"]},
            ],
            "relationships": [],
        }

        stats = generate_stats(global_graph)

        assert stats["entities_by_type"]["Person"] == 2
        assert stats["entities_by_type"]["Place"] == 1

    def test_stats_has_last_updated(self) -> None:
        global_graph = {
            "@context": {},
            "entities": [],
            "relationships": [],
        }

        stats = generate_stats(global_graph)

        assert "last_updated" in stats
        # Should be ISO format
        assert "T" in stats["last_updated"]

    def test_stats_empty_graph(self) -> None:
        global_graph = {
            "@context": {},
            "entities": [],
            "relationships": [],
        }

        stats = generate_stats(global_graph)

        assert stats["total_entities"] == 0
        assert stats["total_relationships"] == 0
        assert stats["total_sources"] == 0
        assert stats["entities_by_type"] == {}
