# waste_ontology.py
"""
Waste ontology normalization.

Maps the raw Roboflow MedBin detection class labels onto a small set of
canonical waste *items*. The policy engine then maps canonical items onto
disposal streams.

IMPORTANT (P0): An unmapped / unrecognised raw class is NOT forced into
GENERAL. It is returned as the sentinel ``UNKNOWN`` so the pipeline can raise
a REVIEW_REQUIRED decision instead of inventing a disposal route the system
cannot justify.
"""

# Sentinel returned when a raw class cannot be confidently mapped.
UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Raw MedBin class label  ->  canonical waste item
# ---------------------------------------------------------------------------
CLASS_MAPPING = {

    # --- Infectious / soiled ---
    "MEDICAL_GLOVES": "GLOVES",
    "MEDICAL_GLOVE": "GLOVES",
    "GLOVES": "GLOVES",
    "GLOVE": "GLOVES",

    "BLOODY_OBJECTS": "INFECTIOUS",
    "BLOODY_OBJECT": "INFECTIOUS",
    "GAUZE": "INFECTIOUS",
    "COTTON_SWAB": "INFECTIOUS",
    "BANDAGE": "INFECTIOUS",

    # --- Sharps ---
    "NEEDLE": "SHARPS",
    "SYRINGE": "SHARPS",
    "SCALPEL": "SHARPS",
    "BLADE": "SHARPS",

    # --- PPE ---
    "N95": "PPE",
    "MASK": "PPE",
    "FACE_MASK": "PPE",

    # --- Pharmaceutical ---
    "PILL": "PHARMACEUTICAL",
    "CAPSULE": "PHARMACEUTICAL",
    "UNGENT": "PHARMACEUTICAL",
    "OINTMENT": "PHARMACEUTICAL",
    "DRUG_PACKAGING": "PHARMACEUTICAL",

    # --- Chemical ---
    "REAGENT_TUBE": "CHEMICAL",
    "REAGENT_TUBE_CAP": "CHEMICAL",
    "IODINE_SWAB": "CHEMICAL",

    # --- Radioactive ---
    "RADIOACTIVE_OBJECTS": "RADIOACTIVE",
    "RADIOACTIVE_OBJECT": "RADIOACTIVE",

    # --- Recyclable plastic ---
    "PLASTIC_MEDICAL_BAG": "PLASTIC",
    "PLASTIC_MEDICAL_BOTTLE": "PLASTIC",

    # --- Recyclable glass ---
    "GLASS_BOTTLE": "GLASS",

    # --- General (explicitly non-hazardous items) ---
    "PAPERBOX": "GENERAL",
    "COVID_BUFFER_BOX": "GENERAL",
}


def _key(raw_class):
    """Normalise a raw label to the lookup key format."""
    return (
        str(raw_class)
        .upper()
        .strip()
        .replace(" ", "_")
        .replace("-", "_")
    )


def normalize_class(raw_class):
    """
    Return the canonical waste item for a raw MedBin class.

    Returns the ``UNKNOWN`` sentinel when the raw class is empty or not present
    in the ontology, so callers can route it to REVIEW_REQUIRED rather than
    silently defaulting to GENERAL.
    """
    if not raw_class:
        return UNKNOWN
    return CLASS_MAPPING.get(_key(raw_class), UNKNOWN)


def is_known(raw_class):
    """True if the raw class has an explicit ontology mapping."""
    if not raw_class:
        return False
    return _key(raw_class) in CLASS_MAPPING


def canonical_items():
    """The distinct set of canonical items the ontology can emit."""
    return sorted(set(CLASS_MAPPING.values()))
