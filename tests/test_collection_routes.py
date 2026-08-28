# tests/test_collection_routes.py
"""Prompt 06 — bin-level collection, full emptying & ROUTE-SPECIFIC workflows.

Extends the Prompt 05 domain-model coverage with the behaviours Prompt 06
requires:

    * Every bin is independently actionable (multi-bin independence).
    * Route-specific, data-driven workflows with VARIABLE step counts
      (generic 5-step vs RED/BROWN 6-step vs RADIOACTIVE storage/decay).
    * Completing one bin's job never touches another bin's job.
    * A completed job does NOT block a new cycle once new events arrive.
    * Operations surfaces the active job so the UI can show "Continue".
    * event_job_map tags collected events (events stay event-centric).

Isolated temp DB so seeding never touches the bundled audit.db.
"""

import tempfile

import audit_store

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
audit_store.DB_PATH = _TMP.name
audit_store.init_db()

import collection  # noqa: E402
import operations  # noqa: E402
import disposal  # noqa: E402


def _mk(route, ward="WardA"):
    ev = audit_store.create_event({
        "image_id": "img", "canonical_category": "X",
        "expected_route": route, "actual_route": route,
        "compliance_status": "CORRECT", "ward": ward,
    })
    return ev["event_id"]


def _run_to_completion(job_id, route):
    """Complete every step (in order) for a route's workflow."""
    for step in disposal.steps_for_route(route):
        _, st = collection.complete_step(job_id, step["id"])
        assert st == 200, (route, step["id"], st)


def test_multi_bin_independence():
    # Two different bins with pending content each start their own job.
    _mk("YELLOW"); _mk("YELLOW")
    _mk("BLUE")
    py, sy = collection.start_collection("yellow")
    pb, sb = collection.start_collection("blue")
    assert sy == 201 and sb == 201
    jy, jb = py["job"]["job_id"], pb["job"]["job_id"]
    assert jy != jb

    # Completing the YELLOW job must NOT alter the BLUE job.
    _run_to_completion(jy, "YELLOW")
    assert collection.get_job(jy)["status"] == "COMPLETED"
    assert collection.get_job(jb)["status"] == "IN_PROGRESS"


def test_route_specific_workflow_step_counts_and_names():
    # Generic routes share the 5-step facility workflow.
    for route in ("YELLOW", "BLUE", "WHITE", "BLACK"):
        steps = disposal.steps_for_route(route)
        assert [s["id"] for s in steps] == disposal.STEP_IDS
        assert len(steps) == 5

    # RED (Sharps) adds a puncture-proof step -> 6 steps.
    red = disposal.steps_for_route("RED")
    assert len(red) == 6
    assert "puncture_proof" in [s["id"] for s in red]

    # BROWN (Pharmaceutical) adds a cytotoxic quarantine step -> 6 steps.
    brown = disposal.steps_for_route("BROWN")
    assert len(brown) == 6
    assert "quarantine" in [s["id"] for s in brown]

    # RADIOACTIVE ends in shielded storage + decay/release, not "treatment".
    rad = disposal.steps_for_route("RADIOACTIVE_STORAGE")
    rad_ids = [s["id"] for s in rad]
    assert "shielded_storage" in rad_ids and "decay_release" in rad_ids
    assert "treatment" not in rad_ids

    # Provenance is explicit and non-regulatory.
    d = disposal.definition("RED")
    assert d["total_steps"] == 6
    assert "regulation" in d["workflow_source"].lower() or "prototype" in d["workflow_source"].lower()


def test_route_specific_job_runs_full_length():
    # A RED collection must require all 6 steps before completing.
    _mk("RED")
    payload, status = collection.start_collection("red")
    assert status == 201
    job_id = payload["job"]["job_id"]
    assert payload["job"]["workflow"]["total_steps"] == 6

    steps = disposal.steps_for_route("RED")
    # Completing the first 5 leaves the job IN_PROGRESS (not the generic 5).
    for step in steps[:-1]:
        _, st = collection.complete_step(job_id, step["id"])
        assert st == 200
    assert collection.get_job(job_id)["status"] == "IN_PROGRESS"
    # The 6th step finishes it.
    _, st = collection.complete_step(job_id, steps[-1]["id"])
    assert st == 200
    assert collection.get_job(job_id)["status"] == "COMPLETED"


def test_completed_job_does_not_block_new_cycle():
    _mk("WHITE")
    p1, s1 = collection.start_collection("white")
    assert s1 == 201
    j1 = p1["job"]["job_id"]
    _run_to_completion(j1, "WHITE")
    assert collection.get_job(j1)["status"] == "COMPLETED"

    # No eligible events remain -> starting again must NOT fabricate a job.
    p_none, s_none = collection.start_collection("white")
    assert s_none == 409 and p_none["code"] == "NO_ELIGIBLE_EVENTS"

    # A new event arrives -> a brand-new job (distinct id) is allowed.
    _mk("WHITE")
    p2, s2 = collection.start_collection("white")
    assert s2 == 201 and p2["job"]["job_id"] != j1


def test_operations_surfaces_active_job_and_event_mapping():
    _mk("BLACK"); _mk("BLACK")
    payload, status = collection.start_collection("black")
    assert status == 201
    job_id = payload["job"]["job_id"]

    b = operations.get_bin("black")
    assert b["active_job"] is not None
    assert b["active_job"]["job_id"] == job_id
    assert b["active_job"]["item_count"] == 2
    # While a job is active its events are no longer "pending" for a new job.
    assert b["pending_collection_count"] == 0

    # Collected events are tagged with their job (events stay event-centric).
    jmap = audit_store.event_job_map()
    for eid in payload["job"]["event_ids"]:
        assert jmap.get(eid) == job_id
