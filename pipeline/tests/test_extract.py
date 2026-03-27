"""Tests for NER entity extraction."""

from woograph.extract.ner import Entity, extract_entities


SAMPLE_TEXT = """\
Admiral Chester Nimitz commanded the United States Pacific Fleet during
World War II. He was born in Fredericksburg, Texas, and graduated from
the United States Naval Academy. Nimitz served alongside General Douglas
MacArthur in the Pacific Theater. The Battle of Midway in June 1942 was
a turning point under his command. He later signed the Japanese Instrument
of Surrender aboard USS Missouri in Tokyo Bay on September 2, 1945.
"""

SAMPLE_SOURCE_ID = "source:nimitz-biography"


class TestExtractEntities:
    """Test the extract_entities function."""

    def test_returns_list_of_entities(self):
        result = extract_entities(SAMPLE_TEXT, SAMPLE_SOURCE_ID)
        assert isinstance(result, list)
        assert all(isinstance(e, Entity) for e in result)

    def test_extracts_person_entities(self):
        result = extract_entities(SAMPLE_TEXT, SAMPLE_SOURCE_ID)
        person_names = [e.name for e in result if e.entity_type == "PERSON"]
        # spaCy should find at least Nimitz and MacArthur
        assert any("Nimitz" in name for name in person_names)
        assert any("MacArthur" in name for name in person_names)

    def test_extracts_place_entities(self):
        result = extract_entities(SAMPLE_TEXT, SAMPLE_SOURCE_ID)
        gpe_names = [e.name for e in result if e.entity_type in ("GPE", "LOC", "FAC")]
        # Should find Texas or Fredericksburg
        combined = " ".join(gpe_names)
        assert "Texas" in combined or "Fredericksburg" in combined

    def test_extracts_org_entities(self):
        result = extract_entities(SAMPLE_TEXT, SAMPLE_SOURCE_ID)
        org_names = [e.name for e in result if e.entity_type == "ORG"]
        # Should find some organization (Naval Academy, Pacific Fleet, etc)
        assert len(org_names) > 0, "Expected at least one ORG, got none"

    def test_deduplication(self):
        """Same entity mentioned multiple times should be merged."""
        text = "Chester Nimitz was great. Nimitz led the fleet. Admiral Nimitz won."
        result = extract_entities(text, SAMPLE_SOURCE_ID)
        nimitz_entities = [e for e in result if "Nimitz" in e.name]
        # All Nimitz mentions should be merged into one (or very few) entities
        assert len(nimitz_entities) <= 2, (
            f"Expected deduplication of Nimitz, got {len(nimitz_entities)} entities: "
            f"{[e.name for e in nimitz_entities]}"
        )

    def test_canonical_id_format(self):
        result = extract_entities(SAMPLE_TEXT, SAMPLE_SOURCE_ID)
        for entity in result:
            assert entity.canonical_id.startswith("entity:"), (
                f"Expected canonical_id to start with 'entity:', got '{entity.canonical_id}'"
            )
            # Should contain the type prefix
            assert "-" in entity.canonical_id

    def test_mention_count(self):
        text = "Chester Nimitz was great. Nimitz led the fleet. Admiral Nimitz won."
        result = extract_entities(text, SAMPLE_SOURCE_ID)
        nimitz_entities = [e for e in result if "Nimitz" in e.name]
        if nimitz_entities:
            # The merged entity should have multiple mentions
            total_mentions = sum(e.mention_count for e in nimitz_entities)
            assert total_mentions >= 2

    def test_context_snippets(self):
        result = extract_entities(SAMPLE_TEXT, SAMPLE_SOURCE_ID)
        for entity in result:
            assert len(entity.context_snippets) > 0, (
                f"Entity '{entity.name}' has no context snippets"
            )
            for snippet in entity.context_snippets:
                assert len(snippet) > 0

    def test_filters_short_entities(self):
        """Single-character entities should be filtered out."""
        result = extract_entities(SAMPLE_TEXT, SAMPLE_SOURCE_ID)
        for entity in result:
            assert len(entity.name) > 1, (
                f"Single-char entity should be filtered: '{entity.name}'"
            )

    def test_entity_types_are_valid(self):
        valid_types = {"PERSON", "ORG", "GPE", "LOC", "DATE", "EVENT", "WORK_OF_ART", "FAC"}
        result = extract_entities(SAMPLE_TEXT, SAMPLE_SOURCE_ID)
        for entity in result:
            assert entity.entity_type in valid_types, (
                f"Unexpected entity type: '{entity.entity_type}'"
            )

    def test_empty_text_returns_empty(self):
        result = extract_entities("", SAMPLE_SOURCE_ID)
        assert result == []

    def test_strips_markdown_formatting(self):
        """Markdown syntax should not appear in entity names."""
        md_text = "**Admiral Chester Nimitz** commanded the *Pacific Fleet*."
        result = extract_entities(md_text, SAMPLE_SOURCE_ID)
        for entity in result:
            assert "**" not in entity.name
            assert "*" not in entity.name
