# tests/test_policy.py
"""policy_engine is the single source of truth: static rules, context rules,
and the uncertainty gates (low confidence / unknown -> REVIEW_REQUIRED)."""

import policy_engine as pe


def _route(item, ctx=None, conf=0.9):
    return pe.policy_decision(item, ctx or {}, conf)


def test_static_rules_map_items_to_streams():
    cases = {
        "SHARPS": ("RED", "R-SHARPS"),
        "INFECTIOUS": ("YELLOW", "R-INFECTIOUS"),
        "RADIOACTIVE": ("RADIOACTIVE_STORAGE", "R-RADIOACTIVE"),
        "PHARMACEUTICAL": ("BROWN", "R-PHARMA"),
        "CHEMICAL": ("WHITE", "R-CHEMICAL"),
        "PLASTIC": ("BLUE", "R-RECYCLABLE"),
        "GLASS": ("BLUE", "R-RECYCLABLE"),
        "GENERAL": ("BLACK", "R-GENERAL"),
    }
    for item, (route, rule) in cases.items():
        d = _route(item)
        assert d["status"] == "DECIDED", (item, d)
        assert d["expected_route"] == route, (item, d)
        assert d["rule_id"] == rule, (item, d)
        assert d["policy_version"] == pe.POLICY_VERSION


def test_context_dependent_gloves_used_and_contaminated_is_infectious():
    d = _route("GLOVES", {"Used": "YES", "Contaminated": "YES"})
    assert d["expected_route"] == "YELLOW"
    assert d["waste_type"] == "INFECTIOUS"
    assert d["rule_id"] == "R-PPE-CONTAMINATED"


def test_context_dependent_gloves_clean_is_general():
    d = _route("GLOVES", {"Used": "NO", "Contaminated": "NO"})
    assert d["expected_route"] == "BLACK"
    assert d["rule_id"] == "R-PPE-CLEAN"


def test_unknown_item_is_review_with_null_route():
    d = _route("UNKNOWN")
    assert d["status"] == "REVIEW_REQUIRED"
    assert d["expected_route"] is None
    assert d["reason"] == "UNKNOWN_CLASS"


def test_canonical_item_without_a_rule_is_review_not_defaulted():
    # A canonical-looking item we have no rule for must NOT fall back to BLACK.
    d = _route("SOME_ITEM_WITHOUT_RULE")
    assert d["status"] == "REVIEW_REQUIRED"
    assert d["expected_route"] is None


def test_low_confidence_gate():
    d = pe.policy_decision("SHARPS", {}, 0.10)
    assert d["status"] == "REVIEW_REQUIRED"
    assert d["reason"] == "LOW_CONFIDENCE"
    assert d["expected_route"] is None


def test_accept_threshold_boundary_is_inclusive():
    # confidence == ACCEPT_THRESHOLD should be accepted (not < threshold).
    d = pe.policy_decision("SHARPS", {}, pe.ACCEPT_THRESHOLD)
    assert d["status"] == "DECIDED"


def test_none_item_reviews():
    d = pe.policy_decision(None, {}, 0.9)
    assert d["status"] == "REVIEW_REQUIRED"


def test_public_review_wrapper():
    d = pe.review("NO_DETECTION")
    assert d["status"] == "REVIEW_REQUIRED"
    assert d["reason"] == "NO_DETECTION"
    assert d["expected_route"] is None
