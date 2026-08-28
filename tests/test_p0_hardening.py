# tests/test_p0_hardening.py
"""Prompt 09 — P0 regression suite: ward context, capacity semantics, workflow
integrity.

Every test starts from a FRESH, EMPTY audit/collection DB (autouse fixture in
conftest.py under pytest; per-test reset in run_offline.py offline), so results
are identical whether a test runs alone, in the suite, or after run_offline.

Three invariants are pinned here:
  * WARD is operational CONTEXT resolved against the facility registry — never
    invented, never silently defaulted, always reconstructable from the event.
  * CAPACITY is grounded on items still awaiting collection. Zero pending means
    an EMPTY bin (0%); STARTING a job does not empty a bin, COMPLETING one does.
  * WORKFLOWS are backend-defined and route-resolved; step lists and counts come
    from disposal.py, and route-specific steps trace to policy_engine.STREAMS.
"""

import os
import tempfile

import audit_store

# Point at an isolated DB at import so the service modules resolve cleanly before
# the first per-test reset takes over.
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
audit_store.DB_PATH = _TMP.name
audit_store.init_db()

import collection    # noqa: E402
import disposal      # noqa: E402
import facility      # noqa: E402
import operations    # noqa: E402
import policy_engine  # noqa: E402


def _mk(route, ward="ER", status="CORRECT"):
    """Create a verified audit event routed to ``route``."""
    ev = audit_store.create_event({
        "image_id": "img", "canonical_category": "X",
        "expected_route": route, "actual_route": route,
        "compliance_status": status, "ward": ward,
    })
    return ev["event_id"]


def _run_to_completion(job_id, route):
    """Complete every step of ``job_id`` that is not already done, in order."""
    done = {s["id"] for s in collection.get_job(job_id)["workflow"]["steps"]
            if s["status"] == "DONE"}
    for step in disposal.steps_for_route(route):
        if step["id"] in done:
            continue
        payload, status = collection.complete_step(job_id, step["id"])
        assert status == 200, (step["id"], payload)
    return collection.get_job(job_id)


# ---------------------------------------------------------------------------
# WARD (1-7)
# ---------------------------------------------------------------------------
def test_ward_1_configured_ward_is_accepted_and_canonicalised():
    assert facility.wards(), "the ward registry must never be empty"
    first = facility.ward_ids()[0]
    ward, ok = facility.normalize_ward(first)
    assert ok and ward == first
    # Case/whitespace tolerant, but the PERSISTED id is always canonical.
    ward, ok = facility.normalize_ward(f"  {first.lower()} ")
    assert ok and ward == first


def test_ward_2_unconfigured_ward_is_rejected():
    ward, ok = facility.normalize_ward("WARD-THAT-DOES-NOT-EXIST")
    assert ok is False
    assert ward == "WARD-THAT-DOES-NOT-EXIST"   # echoed, never coerced
    assert facility.is_valid_ward("WARD-THAT-DOES-NOT-EXIST") is False
    # Rejection must NOT fall back to some other ward.
    assert ward not in facility.ward_ids()


def test_ward_3_omitted_ward_is_the_intentional_unknown_state():
    for value in (None, "", "   "):
        ward, ok = facility.normalize_ward(value)
        assert ok is True and ward is None
    ctx = facility.context()
    assert ctx["unknown_ward_allowed"] is True
    # No default: the operator must choose, so no event is attributed blindly.
    assert ctx["default_ward"] is None


def test_ward_4_selected_ward_reaches_the_persisted_audit_event():
    ward_id = facility.ward_ids()[0]
    eid = _mk("YELLOW", ward=ward_id)
    stored = audit_store.get_event(eid)
    assert stored["ward"] == ward_id
    # Reconstructable from the list endpoint's shape too (what /events renders).
    listed = {e["event_id"]: e for e in audit_store.list_events(limit=50)}
    assert listed[eid]["ward"] == ward_id


def test_ward_5_ward_survives_every_compliance_outcome():
    ward_id = facility.ward_ids()[1]
    cases = {
        "CORRECT": _mk("YELLOW", ward=ward_id, status="CORRECT"),
        "VIOLATION": _mk("RED", ward=ward_id, status="VIOLATION"),
        "REVIEW_REQUIRED": _mk("BLACK", ward=ward_id, status="REVIEW_REQUIRED"),
    }
    for expected_status, eid in cases.items():
        ev = audit_store.get_event(eid)
        assert ev["compliance_status"] == expected_status
        assert ev["ward"] == ward_id
    # A verification update must not drop the ward that is already on the event.
    eid = cases["CORRECT"]
    audit_store.update_event(eid, actual_route="RED", compliance_status="VIOLATION",
                             reason_code="WRONG_WASTE_STREAM")
    assert audit_store.get_event(eid)["ward"] == ward_id


def test_ward_6_registry_is_configuration_not_hardcoded_ui():
    """The ward list is facility CONFIGURATION: overridable without code edits."""
    previous = os.environ.get("FACILITY_WARDS")
    os.environ["FACILITY_WARDS"] = "ZONE-1:Zone One,ZONE-2"
    try:
        assert facility.ward_ids() == ["ZONE-1", "ZONE-2"]
        assert facility.get_ward("zone-2")["label"] == "ZONE-2"  # label defaults to id
        ward, ok = facility.normalize_ward("ER")   # not configured in this profile
        assert ok is False
    finally:
        if previous is None:
            os.environ.pop("FACILITY_WARDS", None)
        else:
            os.environ["FACILITY_WARDS"] = previous
    assert "ER" in facility.ward_ids()   # default profile restored


def test_ward_7_ward_analytics_come_from_real_events_only():
    ward_id = facility.ward_ids()[0]
    _mk("YELLOW", ward=ward_id)
    _mk("YELLOW", ward=ward_id)
    a = audit_store.analytics()
    assert a["has_ward_data"] is True
    assert a["by_ward"][ward_id]["total"] == 2
    # No ward the facility never recorded may appear in the analytics buckets.
    for seen in a["by_ward"]:
        assert seen == ward_id


# ---------------------------------------------------------------------------
# CAPACITY (8-15)
# ---------------------------------------------------------------------------
def test_capacity_8_zero_pending_means_an_empty_bin():
    for b in operations.list_bins()["bins"]:
        assert b["pending_collection_count"] == 0
        assert b["fill_percent"] == 0          # no fabricated historical fill
        assert b["fill_status"] == "OK"
        assert b["is_empty"] is True
        assert b["collection_state"] == "EMPTY"
        assert b["collection_state_label"] == "No items pending collection"
        assert b["can_start_collection"] is False


def test_capacity_9_pending_items_give_a_deterministic_non_zero_capacity():
    _mk("YELLOW")
    first = operations.get_bin("yellow")
    assert first["pending_collection_count"] == 1
    assert first["fill_percent"] > 0
    assert first["collection_state"] == "PENDING_COLLECTION"
    assert first["can_start_collection"] is True
    # Deterministic: the same state renders the same number every time.
    assert operations.get_bin("yellow")["fill_percent"] == first["fill_percent"]
    # And it only grows with real routed items.
    _mk("YELLOW")
    assert operations.get_bin("yellow")["fill_percent"] >= first["fill_percent"]


def test_capacity_10_starting_a_collection_does_not_empty_the_bin():
    _mk("BLUE"); _mk("BLUE")
    before = operations.get_bin("blue")
    payload, status = collection.start_collection("blue")
    assert status == 201
    after = operations.get_bin("blue")
    # Still physically in the bin -> capacity unchanged, visibly in progress.
    assert after["pending_collection_count"] == before["pending_collection_count"] == 2
    assert after["fill_percent"] == before["fill_percent"]
    assert after["fill_percent"] > 0
    assert after["collection_state"] == "IN_PROGRESS"
    assert after["active_job"]["job_id"] == payload["job"]["job_id"]
    # But no second cycle may be opened over the same items.
    assert after["eligible_for_collection_count"] == 0
    assert after["can_start_collection"] is False


def test_capacity_11_completing_a_collection_empties_the_bin():
    _mk("WHITE"); _mk("WHITE")
    payload, status = collection.start_collection("white")
    assert status == 201
    _run_to_completion(payload["job"]["job_id"], "WHITE")
    after = operations.get_bin("white")
    assert after["pending_collection_count"] == 0
    assert after["fill_percent"] == 0
    assert after["collection_state"] == "EMPTY"
    assert after["can_start_collection"] is False
    # The audit total is a permanent tally and must NOT fall.
    assert after["routed_event_count"] >= 2


def test_capacity_12_audit_events_are_never_consumed_by_a_collection():
    a, b = _mk("BROWN"), _mk("BROWN")
    payload, status = collection.start_collection("brown")
    assert status == 201
    job_id = payload["job"]["job_id"]
    _run_to_completion(job_id, "BROWN")
    for eid in (a, b):
        ev = audit_store.get_event(eid)
        assert ev is not None                       # never deleted
        assert ev["compliance_status"] == "CORRECT"  # never mutated
    # Association is metadata only.
    assert audit_store.event_job_map()[a] == job_id


def test_capacity_13_new_event_after_completion_starts_a_future_cycle():
    _mk("RED")
    p1, s1 = collection.start_collection("red")
    assert s1 == 201
    _run_to_completion(p1["job"]["job_id"], "RED")
    assert operations.get_bin("red")["collection_state"] == "EMPTY"

    _mk("RED")   # a new item arrives AFTER the previous cycle closed
    bin_now = operations.get_bin("red")
    assert bin_now["pending_collection_count"] == 1
    assert bin_now["fill_percent"] > 0
    assert bin_now["collection_state"] == "PENDING_COLLECTION"
    assert bin_now["can_start_collection"] is True
    p2, s2 = collection.start_collection("red")
    assert s2 == 201 and p2["job"]["job_id"] != p1["job"]["job_id"]
    assert p2["job"]["event_count"] == 1   # only the new item


def test_capacity_14_bins_are_independent():
    _mk("YELLOW")
    _mk("BLACK"); _mk("BLACK")
    payload, status = collection.start_collection("black")
    assert status == 201
    _run_to_completion(payload["job"]["job_id"], "BLACK")

    black = operations.get_bin("black")
    yellow = operations.get_bin("yellow")
    assert black["collection_state"] == "EMPTY" and black["fill_percent"] == 0
    # Collecting BLACK must not touch YELLOW's capacity or actionability.
    assert yellow["pending_collection_count"] == 1
    assert yellow["fill_percent"] > 0
    assert yellow["can_start_collection"] is True
    for other in operations.list_bins()["bins"]:
        if other["bin_id"] not in ("black", "yellow"):
            assert other["pending_collection_count"] == 0
            assert other["fill_percent"] == 0


def test_capacity_15_capacity_stays_explicitly_simulated():
    """Honesty boundary: no IoT / sensor / weight / RFID claim may appear."""
    data = operations.list_bins()
    assert data["data_source"] == "SIMULATED"
    text = (data["disclaimer"] + " " + data["capacity_basis"]).lower()
    for banned in ("iot", "sensor", "weight cell", "rfid"):
        # These words may only appear as explicit DENIALS ("no ... is used").
        if banned in text:
            assert "no " in text
    for b in data["bins"]:
        assert b["data_source"] == "SIMULATED"
        assert b["sensing"] == "none"
        assert b["capacity_basis"] == "pending_collection_count"
        assert 0 <= b["fill_percent"] <= 100


# ---------------------------------------------------------------------------
# WORKFLOW (16-21)
# ---------------------------------------------------------------------------
def test_workflow_16_every_selectable_route_resolves_to_a_backend_workflow():
    for route in policy_engine.valid_routes():
        steps = disposal.steps_for_route(route)
        assert steps, route
        ids = [s["id"] for s in steps]
        assert len(ids) == len(set(ids))          # no duplicated step
        for s in steps:
            assert s["id"] and s["label"] and s["description"]


def test_workflow_17_definition_is_authoritative_and_self_describing():
    for route in policy_engine.valid_routes():
        d = disposal.definition(route)
        assert d["route_code"] == route
        assert d["total_steps"] == len(d["steps"]) >= 1
        assert [s["order"] for s in d["steps"]] == list(range(1, d["total_steps"] + 1))
        assert d["workflow_source"] and d["workflow_version"]
        # Provenance is the repo's own policy data — no external regulation cited.
        assert "policy_engine.STREAMS" in d["workflow_source"]


def test_workflow_18_route_differences_trace_to_the_policy_source():
    """Route-specific steps must be justified by that stream's handling text."""
    def _desc(route):
        return (policy_engine.route_meta(route) or {}).get("description", "").lower()

    red = [s["id"] for s in disposal.steps_for_route("RED")]
    assert "puncture_proof" in red and "puncture-proof" in _desc("RED")

    brown = [s["id"] for s in disposal.steps_for_route("BROWN")]
    assert "quarantine" in brown and "cytotoxic" in _desc("BROWN")

    radio = [s["id"] for s in disposal.steps_for_route("RADIOACTIVE_STORAGE")]
    radio_desc = _desc("RADIOACTIVE_STORAGE")
    assert "shielded_storage" in radio and "shielded" in radio_desc
    assert "decay_release" in radio and "decay" in radio_desc
    # Storage/decay IS the terminal handling for this stream — no treatment step.
    assert "treatment" not in radio

    # Routes without a distinguishing handling note legitimately share the
    # generic workflow; no step is invented merely to look different.
    generic_ids = [s["id"] for s in disposal.GENERIC_STEPS]
    for route in ("YELLOW", "BLUE", "WHITE", "BLACK"):
        assert [s["id"] for s in disposal.steps_for_route(route)] == generic_ids


def test_workflow_19_steps_cannot_be_skipped_or_reordered():
    _mk("YELLOW")
    payload, status = collection.start_collection("yellow")
    assert status == 201
    job_id = payload["job"]["job_id"]
    steps = disposal.steps_for_route("YELLOW")

    # Jumping ahead is refused with a 409 and changes nothing.
    p, s = collection.complete_step(job_id, steps[-1]["id"])
    assert s == 409 and p["code"] == "OUT_OF_ORDER"
    assert collection.get_job(job_id)["workflow"]["completed_count"] == 0

    # The first step is accepted; repeating it is refused.
    p, s = collection.complete_step(job_id, steps[0]["id"])
    assert s == 200
    p, s = collection.complete_step(job_id, steps[0]["id"])
    assert s == 409 and p["code"] == "ALREADY_COMPLETE"
    # Unknown steps cannot be injected.
    p, s = collection.complete_step(job_id, "not_a_step")
    assert s == 404 and p["code"] == "UNKNOWN_STEP"


def test_workflow_20_final_step_completes_the_job_backend_side():
    _mk("RADIOACTIVE_STORAGE")
    payload, status = collection.start_collection("radioactive_storage")
    assert status == 201
    job_id = payload["job"]["job_id"]
    steps = disposal.steps_for_route("RADIOACTIVE_STORAGE")

    for s in steps[:-1]:
        p, code = collection.complete_step(job_id, s["id"])
        assert code == 200
        assert p["job"]["status"] == "IN_PROGRESS"       # not complete early
        assert p["job"]["workflow"]["is_complete"] is False

    p, code = collection.complete_step(job_id, steps[-1]["id"])
    assert code == 200
    assert p["job"]["status"] == "COMPLETED"
    assert p["job"]["completed_at"]
    assert p["job"]["workflow"]["is_complete"] is True
    assert p["job"]["workflow"]["completed_count"] == len(steps)
    # A completed job is closed for further steps.
    p, code = collection.complete_step(job_id, steps[0]["id"])
    assert code == 409 and p["code"] == "JOB_COMPLETE"


def test_workflow_21_concurrent_bin_cycles_stay_independent():
    _mk("RED"); _mk("BROWN")
    p_red, s_red = collection.start_collection("red")
    p_brown, s_brown = collection.start_collection("brown")
    assert s_red == 201 and s_brown == 201
    red_id, brown_id = p_red["job"]["job_id"], p_brown["job"]["job_id"]
    assert red_id != brown_id

    # One active job per bin: clicking the same bin resumes, never duplicates.
    p_again, s_again = collection.start_collection("red")
    assert s_again == 200 and p_again["resumed"] is True
    assert p_again["job"]["job_id"] == red_id

    # Advancing RED must not advance BROWN.
    collection.complete_step(red_id, disposal.steps_for_route("RED")[0]["id"])
    assert collection.get_job(red_id)["workflow"]["completed_count"] == 1
    assert collection.get_job(brown_id)["workflow"]["completed_count"] == 0

    _run_to_completion(red_id, "RED")
    assert collection.get_job(red_id)["status"] == "COMPLETED"
    assert collection.get_job(brown_id)["status"] == "IN_PROGRESS"
    # A finished cycle cannot be reopened while no new item has arrived...
    p_none, s_none = collection.start_collection("red")
    assert s_none == 409 and p_none["code"] == "NO_ELIGIBLE_EVENTS"
    assert operations.get_bin("red")["collection_state"] == "EMPTY"
    # ...and BROWN's independent cycle is untouched by any of it.
    assert operations.get_bin("brown")["active_job"]["job_id"] == brown_id
