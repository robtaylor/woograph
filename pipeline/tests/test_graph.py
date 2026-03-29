"""Tests for JSON-LD fragment generation and utilities."""

from woograph.extract.ner import Entity
from woograph.graph.fragment import create_fragment
from woograph.graph.jsonld import make_entity_id, schema_type_for_spacy_label, slugify


class TestSlugify:
    def test_simple_name(self):
        assert slugify("Chester Nimitz") == "chester-nimitz"

    def test_special_characters(self):
        assert slugify("U.S.S. Missouri") == "u-s-s-missouri"

    def test_extra_whitespace(self):
        assert slugify("  Chester   Nimitz  ") == "chester-nimitz"

    def test_unicode(self):
        result = slugify("Tokio")
        assert result == "tokio"

    def test_empty_string(self):
        assert slugify("") == ""


class TestMakeEntityId:
    def test_person(self):
        result = make_entity_id("PERSON", "Chester Nimitz")
        assert result == "entity:person-chester-nimitz"

    def test_org(self):
        result = make_entity_id("ORG", "United States Navy")
        assert result == "entity:organization-united-states-navy"

    def test_gpe(self):
        result = make_entity_id("GPE", "Texas")
        assert result == "entity:place-texas"

    def test_loc(self):
        result = make_entity_id("LOC", "Pacific Ocean")
        assert result == "entity:place-pacific-ocean"

    def test_date(self):
        result = make_entity_id("DATE", "June 1942")
        assert result == "entity:date-june-1942"

    def test_event(self):
        result = make_entity_id("EVENT", "Battle of Midway")
        assert result == "entity:event-battle-of-midway"

    def test_work_of_art(self):
        result = make_entity_id("WORK_OF_ART", "The Art of War")
        assert result == "entity:creativework-the-art-of-war"

    def test_fac(self):
        result = make_entity_id("FAC", "Pearl Harbor")
        assert result == "entity:place-pearl-harbor"


class TestSchemaTypeForSpacyLabel:
    def test_person(self):
        assert schema_type_for_spacy_label("PERSON") == "Person"

    def test_org(self):
        assert schema_type_for_spacy_label("ORG") == "Organization"

    def test_gpe(self):
        assert schema_type_for_spacy_label("GPE") == "Place"

    def test_loc(self):
        assert schema_type_for_spacy_label("LOC") == "Place"

    def test_fac(self):
        assert schema_type_for_spacy_label("FAC") == "Place"

    def test_date(self):
        assert schema_type_for_spacy_label("DATE") == "Date"

    def test_event(self):
        assert schema_type_for_spacy_label("EVENT") == "Event"

    def test_work_of_art(self):
        assert schema_type_for_spacy_label("WORK_OF_ART") == "CreativeWork"

    def test_unknown_returns_thing(self):
        assert schema_type_for_spacy_label("UNKNOWN") == "Thing"


class TestCreateFragment:
    def _make_entities(self):
        return [
            Entity(
                name="Chester Nimitz",
                entity_type="PERSON",
                canonical_id="entity:person-chester-nimitz",
                spans=[(0, 15)],
                context_snippets=["Admiral Chester Nimitz commanded"],
                mention_count=3,
            ),
            Entity(
                name="Texas",
                entity_type="GPE",
                canonical_id="entity:place-texas",
                spans=[(80, 85)],
                context_snippets=["born in Fredericksburg, Texas"],
                mention_count=1,
            ),
        ]

    def test_has_context(self):
        fragment = create_fragment("source:nimitz-bio", "Nimitz Biography", self._make_entities())
        assert "@context" in fragment

    def test_has_id(self):
        fragment = create_fragment("source:nimitz-bio", "Nimitz Biography", self._make_entities())
        assert fragment["@id"] == "source:nimitz-bio"

    def test_has_entities(self):
        fragment = create_fragment("source:nimitz-bio", "Nimitz Biography", self._make_entities())
        assert "entities" in fragment
        # 2 entities + 1 source node
        assert len(fragment["entities"]) == 3

    def test_source_node_present(self):
        fragment = create_fragment("source:nimitz-bio", "Nimitz Biography", self._make_entities())
        source_node = fragment["entities"][0]
        assert source_node["@id"] == "source:nimitz-bio"
        assert source_node["@type"] == "woo:Source"

    def test_entity_structure(self):
        fragment = create_fragment("source:nimitz-bio", "Nimitz Biography", self._make_entities())
        person = fragment["entities"][1]  # index 1, after source node
        assert person["@id"] == "entity:person-chester-nimitz"
        assert person["@type"] == "Person"
        assert person["name"] == "Chester Nimitz"
        assert "aliases" in person
        assert "mentionedIn" in person

    def test_entity_mentioned_in(self):
        fragment = create_fragment("source:nimitz-bio", "Nimitz Biography", self._make_entities())
        # Skip source node (index 0), check entity nodes
        for entity in fragment["entities"][1:]:
            assert entity["mentionedIn"] == "source:nimitz-bio"

    def test_mentioned_in_relationships(self):
        fragment = create_fragment("source:nimitz-bio", "Nimitz Biography", self._make_entities())
        mentioned_rels = [r for r in fragment["relationships"] if r["predicate"] == "woo:mentionedIn"]
        assert len(mentioned_rels) == 2  # one per entity

    def test_entity_type_mapping(self):
        fragment = create_fragment("source:nimitz-bio", "Nimitz Biography", self._make_entities())
        types = {e["name"]: e["@type"] for e in fragment["entities"]}
        assert types["Chester Nimitz"] == "Person"
        assert types["Texas"] == "Place"

    def test_empty_entities(self):
        fragment = create_fragment("source:empty", "Empty Source", [])
        # Still has the source node
        assert len(fragment["entities"]) == 1
        assert fragment["entities"][0]["@type"] == "woo:Source"

    def test_source_title_in_fragment(self):
        fragment = create_fragment("source:nimitz-bio", "Nimitz Biography", self._make_entities())
        assert fragment.get("name") == "Nimitz Biography"
