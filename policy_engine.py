# policy_engine.py
"""
Deterministic policy engine — the SINGLE source of truth for disposal
decisions and compliance verification.

Design boundary (non-negotiable):
    VISION observes      -> raw detections (Roboflow)
    NORMALIZATION        -> canonical item (waste_ontology)
    THIS ENGINE decides  -> waste_type, expected route, compliance
    RAG                  -> supporting evidence only
    LLM                  -> natural-language explanation only

Nothing outside this module is allowed to *decide* a waste category, an
expected route, or a compliance status. RAG/LLM never override it.
"""

import os

# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------
POLICY_VERSION = "1.1.0"
# Facility profile is a hook for multi-facility policy packs. The rules below
# are the default (colour-coded biomedical waste segregation).
FACILITY_PROFILE = os.getenv("FACILITY_PROFILE", "default")


# ---------------------------------------------------------------------------
# Confidence thresholds (env-overridable, so demos can be tuned without code
# changes). A detection at or above ACCEPT_THRESHOLD is trusted enough to
# receive a route; between REVIEW_FLOOR and ACCEPT_THRESHOLD it becomes
# REVIEW_REQUIRED; below REVIEW_FLOOR the pipeline treats it as noise.
# ---------------------------------------------------------------------------
def _f(env_name, default):
    try:
        return float(os.getenv(env_name, default))
    except (TypeError, ValueError):
        return float(default)


ACCEPT_THRESHOLD = _f("POLICY_ACCEPT_THRESHOLD", 0.40)
REVIEW_FLOOR = _f("POLICY_REVIEW_FLOOR", 0.20)


# ---------------------------------------------------------------------------
# Disposal streams (colour-coded). This is also what the UI renders, so the
# UI colour guide must be derived from here — never hard-coded separately.
# ---------------------------------------------------------------------------
STREAMS = {
    "YELLOW": {
        "code": "YELLOW", "label": "Yellow", "category": "Infectious",
        "hex": "#eab308", "bin_asset": "yellow_bin.png",
        "description": "Infectious / soiled waste, contaminated dressings, "
                       "human tissues.",
        "selectable": True,
    },
    "RED": {
        "code": "RED", "label": "Red", "category": "Sharps",
        "hex": "#ef4444", "bin_asset": "red_bin.png",
        "description": "Sharps: needles, syringes, scalpels, blades "
                       "(puncture-proof container).",
        "selectable": True,
    },
    "BLUE": {
        "code": "BLUE", "label": "Blue", "category": "Recyclable",
        "hex": "#3b82f6", "bin_asset": "blue_bin.png",
        "description": "Recyclable, uncontaminated plastic and glass.",
        "selectable": True,
    },
    "WHITE": {
        "code": "WHITE", "label": "White", "category": "Chemical",
        "hex": "#e5e7eb", "bin_asset": "white_bin.png",
        "description": "Chemical waste, reagents, disinfectants.",
        "selectable": True,
    },
    "BROWN": {
        "code": "BROWN", "label": "Brown", "category": "Pharmaceutical",
        "hex": "#a16207", "bin_asset": "brown_bin.png",
        "description": "Expired / discarded pharmaceuticals and cytotoxic drugs.",
        "selectable": True,
    },
    "BLACK": {
        "code": "BLACK", "label": "Black", "category": "General",
        "hex": "#1f2937", "bin_asset": "black_bin.png",
        "description": "General, non-hazardous municipal waste.",
        "selectable": True,
    },
    "RADIOACTIVE_STORAGE": {
        "code": "RADIOACTIVE_STORAGE", "label": "Radioactive", "category": "Radioactive",
        "hex": "#d946ef", "bin_asset": None,
        "description": "Shielded radioactive-waste storage / decay area.",
        "selectable": True,
    },
}


# ---------------------------------------------------------------------------
# Canonical item -> rule.  Each rule yields (waste_type, required_stream).
# Some items are context-dependent and handled explicitly below.
# ---------------------------------------------------------------------------
_STATIC_RULES = {
    "SHARPS":         ("SHARPS",         "RED",                 "R-SHARPS"),
    "INFECTIOUS":     ("INFECTIOUS",     "YELLOW",              "R-INFECTIOUS"),
    "RADIOACTIVE":    ("RADIOACTIVE",    "RADIOACTIVE_STORAGE", "R-RADIOACTIVE"),
    "PHARMACEUTICAL": ("PHARMACEUTICAL", "BROWN",               "R-PHARMA"),
    "CHEMICAL":       ("CHEMICAL",       "WHITE",               "R-CHEMICAL"),
    "PLASTIC":        ("RECYCLABLE",     "BLUE",                "R-RECYCLABLE"),
    "GLASS":          ("RECYCLABLE",     "BLUE",                "R-RECYCLABLE"),
    "GENERAL":        ("GENERAL",        "BLACK",               "R-GENERAL"),
}

# Items whose stream depends on visual context (used + contaminated).
_CONTEXT_ITEMS = {"GLOVES", "PPE"}


def _decided(waste_type, required_stream, rule_id, context_applied=None):
    return {
        "status": "DECIDED",
        "waste_type": waste_type,
        "required_stream": required_stream,
        "expected_route": required_stream,
        "rule_id": rule_id,
        "policy_version": POLICY_VERSION,
        "facility_profile": FACILITY_PROFILE,
        "reason": None,
        "context_applied": context_applied or {},
    }


def _review(reason):
    return {
        "status": "REVIEW_REQUIRED",
        "waste_type": None,
        "required_stream": None,
        "expected_route": None,
        "rule_id": "R-REVIEW",
        "policy_version": POLICY_VERSION,
        "facility_profile": FACILITY_PROFILE,
        "reason": reason,
        "context_applied": {},
    }


def review(reason):
    """Public constructor for a REVIEW_REQUIRED decision (e.g. NO_DETECTION)."""
    return _review(reason)


def policy_decision(item, context=None, confidence=None):
    """
    Decide the expected disposal stream for a canonical item.

    Parameters
    ----------
    item : str
        Canonical waste item (from waste_ontology.normalize_class).
        The sentinel "UNKNOWN" yields REVIEW_REQUIRED.
    context : dict | None
        Visual-context estimate (keys "Used"/"Contaminated" == "YES"/"NO").
        Only consulted for context-dependent items (GLOVES, PPE).
    confidence : float | None
        Detection confidence. Below ACCEPT_THRESHOLD -> REVIEW_REQUIRED
        (LOW_CONFIDENCE) with a null expected route.

    Returns a structured, deterministic decision dict.
    """
    context = context or {}
    item = ("" if item is None else str(item)).upper().strip()

    # 1) Uncertainty gates first — never invent a route we cannot justify.
    if confidence is not None and confidence < ACCEPT_THRESHOLD:
        return _review("LOW_CONFIDENCE")
    if item in ("", "UNKNOWN"):
        return _review("UNKNOWN_CLASS")

    # 2) Context-dependent items.
    if item in _CONTEXT_ITEMS:
        used = context.get("Used") == "YES"
        contaminated = context.get("Contaminated") == "YES"
        applied = {"Used": context.get("Used"),
                   "Contaminated": context.get("Contaminated")}
        if used and contaminated:
            return _decided("INFECTIOUS", "YELLOW", "R-PPE-CONTAMINATED", applied)
        return _decided("GENERAL", "BLACK", "R-PPE-CLEAN", applied)

    # 3) Static rules.
    if item in _STATIC_RULES:
        waste_type, stream, rule_id = _STATIC_RULES[item]
        return _decided(waste_type, stream, rule_id)

    # 4) A canonical item we don't have a rule for -> review, do NOT default.
    return _review("UNKNOWN_CLASS")


# ---------------------------------------------------------------------------
# Compliance verification (Expected vs Actual)
# ---------------------------------------------------------------------------
def valid_routes():
    """Route codes the operator may select as the *actual* disposal route."""
    return [c for c, s in STREAMS.items() if s.get("selectable")]


def route_meta(code):
    """UI metadata for a stream code (or None)."""
    return STREAMS.get(code)


def verify_compliance(expected_route, actual_route):
    """
    Deterministically compare the expected route (from policy) against the
    actual route selected by the operator.

    Returns one of:
        PENDING_VERIFICATION  — no actual route chosen yet
        CORRECT               — actual == expected
        VIOLATION             — actual != expected (reason WRONG_WASTE_STREAM)
        REVIEW_REQUIRED       — no expected route (item was under review)
        INVALID_ROUTE         — actual route not a known stream (defensive)
    """
    expected = (expected_route or None)
    actual = (actual_route or None)

    if expected is None:
        # Item never received an expected route (REVIEW_REQUIRED upstream).
        return {
            "status": "REVIEW_REQUIRED",
            "expected_route": None,
            "actual_route": actual,
            "reason_code": "NO_EXPECTED_ROUTE",
        }

    if actual is None:
        return {
            "status": "PENDING_VERIFICATION",
            "expected_route": expected,
            "actual_route": None,
            "reason_code": None,
        }

    if actual not in STREAMS:
        return {
            "status": "INVALID_ROUTE",
            "expected_route": expected,
            "actual_route": actual,
            "reason_code": "UNKNOWN_ROUTE",
        }

    if actual == expected:
        return {
            "status": "CORRECT",
            "expected_route": expected,
            "actual_route": actual,
            "reason_code": None,
        }

    return {
        "status": "VIOLATION",
        "expected_route": expected,
        "actual_route": actual,
        "reason_code": "WRONG_WASTE_STREAM",
    }
