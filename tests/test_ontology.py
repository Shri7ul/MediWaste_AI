# tests/test_ontology.py
"""Ontology normalization: known classes map; unknown -> UNKNOWN (never GENERAL)."""

import waste_ontology as wo


def test_known_classes_map_to_canonical():
    assert wo.normalize_class("NEEDLE") == "SHARPS"
    assert wo.normalize_class("MEDICAL_GLOVES") == "GLOVES"
    assert wo.normalize_class("RADIOACTIVE_OBJECTS") == "RADIOACTIVE"
    assert wo.normalize_class("GLASS_BOTTLE") == "GLASS"


def test_key_normalisation_is_case_and_separator_insensitive():
    assert wo.normalize_class("needle") == "SHARPS"
    assert wo.normalize_class(" face-mask ") == "PPE"
    assert wo.normalize_class("plastic medical bottle") == "PLASTIC"


def test_unmapped_class_returns_UNKNOWN_not_general():
    assert wo.normalize_class("unicorn_horn") == wo.UNKNOWN
    assert wo.normalize_class("random") != "GENERAL"


def test_empty_returns_UNKNOWN():
    assert wo.normalize_class("") == wo.UNKNOWN
    assert wo.normalize_class(None) == wo.UNKNOWN


def test_is_known():
    assert wo.is_known("NEEDLE") is True
    assert wo.is_known("unicorn_horn") is False
    assert wo.is_known("") is False


def test_canonical_items_are_stable_set():
    items = wo.canonical_items()
    assert "SHARPS" in items and "GENERAL" in items
    assert wo.UNKNOWN not in items  # sentinel is never a canonical item
