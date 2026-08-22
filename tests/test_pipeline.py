# tests/test_pipeline.py
"""The pipeline orchestrates vision -> normalization -> policy but NEVER decides
a route itself. analyze_predictions is a pure function (no network), so it is
fully unit-testable offline."""

import mediwaste_pipeline as mp


def _pred(cls, conf, x=10, y=10, w=5, h=5):
    return {"class": cls, "confidence": conf, "x": x, "y": y, "width": w, "height": h}


def test_single_confident_needle_routes_to_red():
    a = mp.analyze_predictions([_pred("NEEDLE", 0.92)], {})
    assert a["objects_detected"] == 1
    assert a["primary"]["item"] == "SHARPS"
    assert a["decision"]["status"] == "DECIDED"
    assert a["decision"]["expected_route"] == "RED"
    assert a["decision"]["rule_id"] == "R-SHARPS"
    assert a["detections"][0]["bbox"] == {"x": 10, "y": 10, "width": 5, "height": 5}


def test_no_predictions_is_no_detection_review():
    a = mp.analyze_predictions([], {})
    assert a["objects_detected"] == 0
    assert a["primary"] is None
    assert a["decision"]["status"] == "REVIEW_REQUIRED"
    assert a["decision"]["reason"] == "NO_DETECTION"


def test_below_review_floor_is_dropped_as_noise():
    # confidence < REVIEW_FLOOR (0.2) -> dropped entirely, treated as no detection
    a = mp.analyze_predictions([_pred("NEEDLE", 0.05)], {})
    assert a["objects_detected"] == 0
    assert a["decision"]["reason"] == "NO_DETECTION"


def test_mid_confidence_is_kept_but_reviewed_low_confidence():
    # REVIEW_FLOOR (0.2) <= conf < ACCEPT_THRESHOLD (0.4): kept, but LOW_CONFIDENCE
    a = mp.analyze_predictions([_pred("NEEDLE", 0.30)], {})
    assert a["objects_detected"] == 1
    assert a["decision"]["status"] == "REVIEW_REQUIRED"
    assert a["decision"]["reason"] == "LOW_CONFIDENCE"
    assert a["decision"]["expected_route"] is None


def test_unknown_class_is_kept_but_reviewed_not_defaulted():
    a = mp.analyze_predictions([_pred("unicorn_horn", 0.99)], {})
    assert a["objects_detected"] == 1
    assert a["detections"][0]["item"] == "UNKNOWN"
    assert a["decision"]["status"] == "REVIEW_REQUIRED"
    assert a["decision"]["expected_route"] is None


def test_mixed_waste_flagged_when_two_streams_present():
    a = mp.analyze_predictions(
        [_pred("NEEDLE", 0.9), _pred("PLASTIC_MEDICAL_BOTTLE", 0.8)], {}
    )
    assert a["mixed_waste"]["is_mixed"] is True
    assert a["mixed_waste"]["streams"] == ["BLUE", "RED"]
    assert a["mixed_waste"]["waste_types"] == ["RECYCLABLE", "SHARPS"]
    # primary is the highest-confidence DECIDED detection (needle @ 0.9)
    assert a["primary"]["item"] == "SHARPS"


def test_not_mixed_for_single_stream():
    a = mp.analyze_predictions(
        [_pred("NEEDLE", 0.9), _pred("SYRINGE", 0.8)], {}
    )
    assert a["mixed_waste"]["is_mixed"] is False
    assert a["mixed_waste"]["streams"] == ["RED"]


def test_detections_sorted_by_confidence_desc():
    a = mp.analyze_predictions(
        [_pred("PLASTIC_MEDICAL_BOTTLE", 0.5), _pred("NEEDLE", 0.95)], {}
    )
    confs = [d["confidence"] for d in a["detections"]]
    assert confs == sorted(confs, reverse=True)


def test_model_metadata_and_counts_present():
    a = mp.analyze_predictions([_pred("NEEDLE", 0.9)], {})
    assert a["model_ref"]
    assert "model_id" in a and "model_version" in a
    assert a["raw_prediction_count"] == 1


def test_gloves_decision_comes_from_policy_not_pipeline():
    # GLOVES is context-dependent; with no context it resolves via the policy
    # engine's clean-PPE rule (a DECIDED outcome), never invented by the pipeline.
    a = mp.analyze_predictions([_pred("MEDICAL_GLOVES", 0.9)], {})
    assert a["decision"]["rule_id"] in ("R-PPE-CLEAN", "R-PPE-CONTAMINATED")
    assert a["decision"]["expected_route"] in ("BLACK", "YELLOW")
