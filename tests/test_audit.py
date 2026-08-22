# tests/test_audit.py
"""SQLite audit trail: create, get, update, list, count, analytics.

Uses an isolated temporary DB so it never touches the real audit.db. The store
reads audit_store.DB_PATH fresh on every connection, so reassigning it here is
robust regardless of module import order (important under pytest, where app.py
may import audit_store first)."""

import tempfile

import audit_store

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
audit_store.DB_PATH = _TMP.name
audit_store.init_db()


def _sample(**overrides):
    e = {
        "image_filename": "abc_needle.jpg",
        "image_id": "abc",
        "station": "ST-1",
        "detected_items": ["SHARPS"],
        "raw_labels": ["NEEDLE"],
        "confidence": 0.91,
        "visual_context": {"Used": "YES"},
        "canonical_category": "SHARPS",
        "expected_route": "RED",
        "actual_route": None,
        "compliance_status": "PENDING_VERIFICATION",
        "reason_code": None,
        "rule_id": "R-SHARPS",
        "policy_version": "1.1.0",
        "model_id": "medbin_dataset-fqhi7",
        "model_version": "1",
        "evidence_ids": ["e1", "e2"],
        "rag_status": "OK",
        "llm_status": "OK",
    }
    e.update(overrides)
    return e


def test_create_generates_ids_and_roundtrips_json():
    stored = audit_store.create_event(_sample())
    assert stored["event_id"]        # auto-generated
    assert stored["created_at"]      # auto-generated
    got = audit_store.get_event(stored["event_id"])
    assert got["detected_items"] == ["SHARPS"]     # JSON column decoded to list
    assert got["evidence_ids"] == ["e1", "e2"]
    assert got["visual_context"] == {"Used": "YES"}
    assert got["expected_route"] == "RED"


def test_update_event_changes_fields():
    stored = audit_store.create_event(_sample())
    updated = audit_store.update_event(
        stored["event_id"], actual_route="BLACK",
        compliance_status="VIOLATION", reason_code="WRONG_WASTE_STREAM",
    )
    assert updated["actual_route"] == "BLACK"
    assert updated["compliance_status"] == "VIOLATION"
    assert updated["reason_code"] == "WRONG_WASTE_STREAM"
    assert updated["updated_at"] >= stored["created_at"]


def test_update_missing_event_returns_none():
    assert audit_store.update_event("does-not-exist", actual_route="RED") is None


def test_count_and_list_reflect_inserts():
    before = audit_store.count_events()
    a = audit_store.create_event(_sample(image_id="one"))
    b = audit_store.create_event(_sample(image_id="two"))
    assert audit_store.count_events() == before + 2
    recent = audit_store.list_events(limit=2)
    ids = {e["event_id"] for e in recent}
    assert a["event_id"] in ids or b["event_id"] in ids


def test_extra_keys_are_preserved_in_payload():
    stored = audit_store.create_event(_sample(some_extra="keep-me"))
    got = audit_store.get_event(stored["event_id"])
    assert got["payload"]["some_extra"] == "keep-me"


def test_analytics_shape_and_counts():
    audit_store.create_event(
        _sample(compliance_status="CORRECT", actual_route="RED", station="ST-A"))
    audit_store.create_event(
        _sample(compliance_status="VIOLATION", actual_route="BLACK",
                canonical_category="SHARPS", station="ST-A"))
    a = audit_store.analytics()
    assert "total_events" in a
    assert a["correct"] >= 1
    assert a["violations"] >= 1
    assert a["verified"] >= 2
    assert a["compliance_rate"] is not None       # verified > 0
    assert a["violations_by_route"].get("BLACK", 0) >= 1
    assert a["has_station_data"] is True
