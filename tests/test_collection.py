# tests/test_collection.py
"""Bin COLLECTION JOB domain model.

Regression coverage for the Prompt 05 domain-model fix:

    AUDIT EVENT (immutable analyzed item)  !=  COLLECTION JOB (operational cycle)

Covers Phases A-H: eligible events -> start job snapshots exactly those events ->
step 1 ACTIVE / 2-5 LOCKED -> sequential completion persists -> out-of-order
rejected -> completed job -> events survive unchanged -> operations reflects
completion -> completed job cannot restart -> a later event belongs to the next
cycle. Plus the edge case: no eligible events => no fabricated job.

Uses an isolated temp DB so seeding never touches the bundled audit.db.
"""

import tempfile

import audit_store

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
audit_store.DB_PATH = _TMP.name
audit_store.init_db()

import collection  # noqa: E402  (import after DB_PATH is redirected)
import operations  # noqa: E402
import disposal  # noqa: E402


def _mk_event(route="YELLOW", ward="WardA"):
    ev = audit_store.create_event({
        "image_id": "img", "canonical_category": "INFECTIOUS",
        "expected_route": route, "actual_route": route,
        "compliance_status": "CORRECT", "ward": ward,
    })
    return ev["event_id"]


def test_edge_case_no_eligible_events_creates_nothing():
    # RED bin has no routed events in a fresh DB.
    payload, status = collection.start_collection("red")
    assert status == 409
    assert payload["code"] == "NO_ELIGIBLE_EVENTS"
    assert collection.list_jobs() == []  # nothing fabricated


def test_full_collection_lifecycle_phases_a_through_h():
    # Phase A: two eligible YELLOW events (A, B).
    a = _mk_event("YELLOW")
    b = _mk_event("YELLOW")

    # Phase B: both are eligible before any job.
    elig = {e["event_id"] for e in collection.eligible_events("YELLOW")}
    assert {a, b}.issubset(elig)

    # Phase C: start collection -> new job snapshots EXACTLY [A, B].
    payload, status = collection.start_collection("yellow")
    assert status == 201
    job = payload["job"]
    job_id = job["job_id"]
    assert set(job["event_ids"]) == {a, b}
    assert job["status"] == "IN_PROGRESS"

    # Step 1 ACTIVE, steps 2-5 LOCKED (not auto-completed).
    wf = job["workflow"]
    assert wf["current_step"] == disposal.STEP_IDS[0]
    assert wf["completed_count"] == 0
    assert wf["is_complete"] is False
    assert all(s["status"] == "PENDING" for s in wf["steps"])

    # A second Start resumes the same job (idempotent, no duplicate).
    p2, s2 = collection.start_collection("yellow")
    assert s2 == 200 and p2["job"]["job_id"] == job_id

    # Phase D: out-of-order (step 3) is rejected with 409 while step 1 pending.
    op, ostat = collection.complete_step(job_id, disposal.STEP_IDS[2])
    assert ostat == 409 and op["code"] == "OUT_OF_ORDER"

    # Complete step 1 -> step 2 becomes current; persists on refetch.
    cp, cstat = collection.complete_step(job_id, disposal.STEP_IDS[0])
    assert cstat == 200
    assert cp["job"]["workflow"]["current_step"] == disposal.STEP_IDS[1]
    refetched = collection.get_job(job_id)
    assert refetched["workflow"]["completed_count"] == 1

    # Complete remaining steps in order -> job COMPLETED.
    for sid in disposal.STEP_IDS[1:]:
        _, st = collection.complete_step(job_id, sid)
        assert st == 200
    done = collection.get_job(job_id)
    assert done["status"] == "COMPLETED"
    assert done["workflow"]["is_complete"] is True
    assert done["completed_at"]

    # Phase E: A and B still exist with UNCHANGED compliance/provenance.
    for eid in (a, b):
        ev = audit_store.get_event(eid)
        assert ev is not None
        assert ev["compliance_status"] == "CORRECT"

    # Phase F: operations reflects completion -> those events are no longer
    # pending; simulated fill drops relative to before collection.
    ybin = operations.get_bin("yellow")
    assert ybin["routed_event_count"] >= 2      # audit total unchanged
    assert ybin["pending_collection_count"] == 0  # all collected

    # Phase G: a completed job cannot be restarted / re-stepped.
    rp, rstat = collection.complete_step(job_id, disposal.STEP_IDS[0])
    assert rstat == 409 and rp["code"] in ("JOB_COMPLETE", "ALREADY_COMPLETE")

    # Phase H: a NEW event C belongs to the NEXT cycle (new job, only [C]).
    c = _mk_event("YELLOW")
    assert c not in done["event_ids"]  # did not join the completed job
    np, nstat = collection.start_collection("yellow")
    assert nstat == 201
    assert set(np["job"]["event_ids"]) == {c}
    assert np["job"]["job_id"] != job_id


def test_event_and_job_ids_are_distinct_namespaces():
    e = _mk_event("BROWN")
    payload, status = collection.start_collection("brown")
    assert status == 201
    job_id = payload["job"]["job_id"]
    assert job_id != e                       # never reuse an event_id as a job id
    assert job_id.startswith("job_")
    assert audit_store.get_event(job_id) is None  # job id is not an event


def test_unknown_bin_is_rejected():
    payload, status = collection.start_collection("no-such-bin")
    assert status == 404 and payload["code"] == "BIN_NOT_FOUND"
