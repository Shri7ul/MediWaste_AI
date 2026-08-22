# tests/test_verification.py
"""Expected-vs-Actual compliance verification is deterministic."""

import policy_engine as pe


def test_correct_when_actual_matches_expected():
    v = pe.verify_compliance("RED", "RED")
    assert v["status"] == "CORRECT"
    assert v["reason_code"] is None


def test_violation_when_actual_differs():
    v = pe.verify_compliance("RED", "BLACK")
    assert v["status"] == "VIOLATION"
    assert v["reason_code"] == "WRONG_WASTE_STREAM"
    assert v["expected_route"] == "RED"
    assert v["actual_route"] == "BLACK"


def test_pending_when_no_actual_route_yet():
    v = pe.verify_compliance("RED", None)
    assert v["status"] == "PENDING_VERIFICATION"
    assert v["reason_code"] is None


def test_review_when_no_expected_route():
    v = pe.verify_compliance(None, "RED")
    assert v["status"] == "REVIEW_REQUIRED"
    assert v["reason_code"] == "NO_EXPECTED_ROUTE"


def test_invalid_route_is_rejected():
    v = pe.verify_compliance("RED", "PURPLE")
    assert v["status"] == "INVALID_ROUTE"
    assert v["reason_code"] == "UNKNOWN_ROUTE"


def test_valid_routes_and_metadata():
    routes = pe.valid_routes()
    assert "RED" in routes and "YELLOW" in routes
    assert len(routes) == 7  # all selectable streams
    meta = pe.route_meta("RED")
    assert meta["hex"].startswith("#")
    assert meta["category"] == "Sharps"
    assert pe.route_meta("NOPE") is None
