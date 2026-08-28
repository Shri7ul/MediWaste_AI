# tests/test_collection_isolation.py
"""Prompt 07 — deterministic, isolated collection tests.

Every test here starts from a FRESH, EMPTY audit/collection database (guaranteed
by the autouse fixture in conftest.py under pytest, and by the per-test reset in
run_offline.py offline). These cover the explicit Prompt 07 acceptance cases and
double as proof that state no longer leaks between tests: run any one alone, the
whole suite, or after tests/run_offline.py and the results are identical.

No production behaviour is exercised differently from real usage — only the DB
the store points at is swapped between tests.
"""

import tempfile

import audit_store

# Point at an isolated DB at import so `import collection` resolves cleanly even
# before the first per-test reset. The reset (conftest fixture / run_offline)
# takes over from the first test onward.
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
audit_store.DB_PATH = _TMP.name
audit_store.init_db()

import collection  # noqa: E402
import operations  # noqa: E402
import disposal    # noqa: E402


def _mk(route, ward="WardA"):
    ev = audit_store.create_event({
        "image_id": "img", "canonical_category": "X",
        "expected_route": route, "actual_route": route,
        "compliance_status": "CORRECT", "ward": ward,
    })
    return ev["event_id"]


def _run_to_completion(job_id, route):
    for step in disposal.steps_for_route(route):
        _, st = collection.complete_step(job_id, step["id"])
        assert st == 200, (route, step["id"], st)


def test_empty_red_bin_returns_409():
    payload, status = collection.start_collection("red")
    assert status == 409
    assert payload["code"] == "NO_ELIGIBLE_EVENTS"
    assert collection.list_jobs() == []  # nothing fabricated


def test_yellow_with_exactly_two_events_snapshots_those_two():
    a = _mk("YELLOW")
    b = _mk("YELLOW")
    payload, status = collection.start_collection("yellow")
    assert status == 201
    assert set(payload["job"]["event_ids"]) == {a, b}
    assert payload["job"]["event_count"] == 2


def test_yellow_and_blue_run_concurrently_and_independently():
    _mk("YELLOW")
    _mk("BLUE")
    py, sy = collection.start_collection("yellow")
    pb, sb = collection.start_collection("blue")
    assert sy == 201 and sb == 201
    jy, jb = py["job"]["job_id"], pb["job"]["job_id"]
    assert jy != jb
    # Completing YELLOW leaves BLUE untouched.
    _run_to_completion(jy, "YELLOW")
    assert collection.get_job(jy)["status"] == "COMPLETED"
    assert collection.get_job(jb)["status"] == "IN_PROGRESS"


def test_red_workflow_has_exactly_six_steps():
    _mk("RED")
    payload, status = collection.start_collection("red")
    assert status == 201
    wf = payload["job"]["workflow"]
    assert wf["total_steps"] == 6
    assert len(wf["steps"]) == 6


def test_brown_workflow_has_exactly_six_steps():
    _mk("BROWN")
    payload, status = collection.start_collection("brown")
    assert status == 201
    wf = payload["job"]["workflow"]
    assert wf["total_steps"] == 6
    assert len(wf["steps"]) == 6


def test_radioactive_storage_workflow_has_exactly_five_steps():
    _mk("RADIOACTIVE_STORAGE")
    payload, status = collection.start_collection("radioactive_storage")
    assert status == 201
    wf = payload["job"]["workflow"]
    assert wf["total_steps"] == 5
    assert len(wf["steps"]) == 5
    ids = [s["id"] for s in wf["steps"]]
    assert "treatment" not in ids


def test_completed_collection_clears_pending_capacity():
    _mk("WHITE")
    _mk("WHITE")
    before = operations.get_bin("white")
    assert before["pending_collection_count"] == 2
    payload, status = collection.start_collection("white")
    assert status == 201
    _run_to_completion(payload["job"]["job_id"], "WHITE")
    after = operations.get_bin("white")
    assert after["pending_collection_count"] == 0        # bin emptied
    assert after["routed_event_count"] >= 2              # audit total unchanged


def test_audit_events_remain_after_collection():
    a = _mk("BLACK")
    b = _mk("BLACK")
    payload, status = collection.start_collection("black")
    assert status == 201
    _run_to_completion(payload["job"]["job_id"], "BLACK")
    for eid in (a, b):
        ev = audit_store.get_event(eid)
        assert ev is not None                            # never deleted
        assert ev["compliance_status"] == "CORRECT"      # never mutated


def test_new_event_after_completion_creates_a_new_job():
    _mk("YELLOW")
    p1, s1 = collection.start_collection("yellow")
    assert s1 == 201
    j1 = p1["job"]["job_id"]
    _run_to_completion(j1, "YELLOW")
    assert collection.get_job(j1)["status"] == "COMPLETED"

    # No eligible events remain -> completed job does NOT block; 409, no fabrication.
    p_none, s_none = collection.start_collection("yellow")
    assert s_none == 409 and p_none["code"] == "NO_ELIGIBLE_EVENTS"

    # A new event arrives -> a brand-new, distinct job.
    _mk("YELLOW")
    p2, s2 = collection.start_collection("yellow")
    assert s2 == 201 and p2["job"]["job_id"] != j1
