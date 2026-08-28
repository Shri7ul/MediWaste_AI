# tests/test_disposal.py
"""Sequential disposal-workflow state machine.

Two layers are exercised:
  * PURE state-machine logic (new_state / current_step_id / apply_completion) —
    no DB, no fixtures, so the offline runner executes it directly.
  * The SERVICE layer (get_workflow / complete_step) against an isolated temp DB,
    proving event-existence checks, first-access creation, sequential
    enforcement, and clean failures for illegal transitions.

The store reads audit_store.DB_PATH fresh per connection, so reassigning it here
keeps the real audit.db untouched regardless of import order."""

import tempfile

import audit_store
import disposal

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
audit_store.DB_PATH = _TMP.name
audit_store.init_db()


def _new_event():
    """Create a minimal real event so a workflow can attach to it."""
    e = audit_store.create_event({
        "image_id": "wf",
        "canonical_category": "SHARPS",
        "expected_route": "RED",
        "compliance_status": "PENDING_VERIFICATION",
    })
    return e["event_id"]


# --- Pure state-machine logic (offline, no DB) ------------------------------
def test_new_state_has_all_steps_pending():
    st = disposal.new_state()
    assert set(st["steps"].keys()) == set(disposal.STEP_IDS)
    assert all(s["status"] == disposal.PENDING for s in st["steps"].values())
    assert disposal.current_step_id(st) == disposal.STEP_IDS[0]
    assert disposal.is_complete(st) is False


def test_apply_completion_advances_in_order():
    st = disposal.new_state()
    st, err = disposal.apply_completion(st, "segregate")
    assert err is None
    assert st["steps"]["segregate"]["status"] == disposal.DONE
    assert st["steps"]["segregate"]["completed_at"]      # timestamp recorded
    assert disposal.current_step_id(st) == "secure"      # advanced to step 2


def test_skipping_ahead_is_out_of_order():
    st = disposal.new_state()
    # 'secure' is step 2; cannot complete before 'segregate'.
    st2, err = disposal.apply_completion(st, "secure")
    assert err == "OUT_OF_ORDER"
    assert st2["steps"]["secure"]["status"] == disposal.PENDING  # unchanged


def test_recompleting_step_is_already_complete():
    st = disposal.new_state()
    st, err = disposal.apply_completion(st, "segregate")
    assert err is None
    st, err = disposal.apply_completion(st, "segregate")
    assert err == "ALREADY_COMPLETE"


def test_unknown_step_is_rejected():
    st = disposal.new_state()
    _, err = disposal.apply_completion(st, "not-a-step")
    assert err == "UNKNOWN_STEP"


def test_full_in_order_run_completes_workflow():
    st = disposal.new_state()
    for step_id in disposal.STEP_IDS:
        st, err = disposal.apply_completion(st, step_id)
        assert err is None, step_id
    assert disposal.is_complete(st) is True
    assert disposal.current_step_id(st) is None


def test_definition_lists_five_ordered_steps():
    d = disposal.definition()
    assert d["total_steps"] == 5
    orders = [s["order"] for s in d["steps"]]
    assert orders == [1, 2, 3, 4, 5]
    labels = [s["label"] for s in d["steps"]]
    assert labels == ["Segregate", "Secure", "Seal & Label",
                      "Authorized Collection", "Treatment / Final Disposal"]


# --- Service layer (isolated temp DB) ---------------------------------------
def test_get_workflow_none_for_missing_event():
    assert disposal.get_workflow("does-not-exist") is None


def test_get_workflow_creates_on_first_access():
    eid = _new_event()
    wf = disposal.get_workflow(eid)
    assert wf is not None
    assert wf["event_id"] == eid
    assert wf["total_steps"] == 5
    assert wf["current_step"] == "segregate"
    assert wf["completed_count"] == 0
    assert wf["is_complete"] is False
    # Persisted: a second read returns the same (still-pending) state.
    again = disposal.get_workflow(eid)
    assert again["completed_count"] == 0


def test_complete_step_service_enforces_sequence():
    eid = _new_event()
    disposal.get_workflow(eid)  # materialise

    # Skipping ahead -> 409 OUT_OF_ORDER, state untouched.
    payload, status = disposal.complete_step(eid, "treatment")
    assert status == 409
    assert payload["code"] == "OUT_OF_ORDER"

    # First step in order -> 200 and progress recorded.
    payload, status = disposal.complete_step(eid, "segregate")
    assert status == 200
    assert payload["workflow"]["completed_count"] == 1
    assert payload["workflow"]["current_step"] == "secure"

    # Re-completing the same step -> 409 ALREADY_COMPLETE.
    payload, status = disposal.complete_step(eid, "segregate")
    assert status == 409
    assert payload["code"] == "ALREADY_COMPLETE"

    # Unknown step -> 404 UNKNOWN_STEP.
    payload, status = disposal.complete_step(eid, "ghost")
    assert status == 404
    assert payload["code"] == "UNKNOWN_STEP"


def test_complete_step_missing_event_is_404():
    payload, status = disposal.complete_step("nope", "segregate")
    assert status == 404
    assert payload["code"] == "EVENT_NOT_FOUND"


def test_workflow_progress_does_not_mutate_event_provenance():
    eid = _new_event()
    before = audit_store.get_event(eid)
    disposal.complete_step(eid, "segregate")
    after = audit_store.get_event(eid)
    # The audit event's decision provenance is never touched by workflow steps.
    assert after["expected_route"] == before["expected_route"]
    assert after["canonical_category"] == before["canonical_category"]
    assert after["compliance_status"] == before["compliance_status"]
