# disposal.py
"""
Sequential disposal-workflow state machine (data-driven, route-aware).

A recorded compliance event, or a bin collection job, can be walked through an
ordered set of handling steps. This module owns ONLY the workflow rules (what
the steps are for a given route, what order they must happen in, what
transitions are legal). Persistence lives elsewhere (audit_store); the
deterministic policy decision and an event's audit provenance are never
modified by workflow progress.

WORKFLOW PROVENANCE (read this before assuming clinical/legal meaning)
----------------------------------------------------------------------
These are OPERATIONAL workflow states for the exhibition prototype. They are
NOT a claim of any universal clinical or legal disposal procedure and cite no
regulation. The generic sequence is a facility workflow definition. Where a
route carries a genuinely distinct handling note, an extra step is DERIVED from
that stream's own handling description in ``policy_engine.STREAMS`` (the repo's
single source of truth) — e.g. RED/Sharps says "puncture-proof container", so
the RED workflow adds a rigid-container step. No route-specific step is invented
beyond what the repository's own policy data already states.

The workflow is therefore data-driven and variable-length: different routes may
have different step counts (5 or 6 here). Callers must never hardcode the count.

Rules (per workflow, whatever its length):
    * Steps must be completed strictly in order.
    * Completing an out-of-order step (skipping ahead) fails with OUT_OF_ORDER.
    * Completing an already-done step fails with ALREADY_COMPLETE.
    * An unknown step id fails with UNKNOWN_STEP.
"""

from datetime import datetime, timezone

import audit_store

# Provenance metadata surfaced to the UI / report so no one mistakes these
# operational steps for a regulatory citation.
WORKFLOW_SOURCE = (
    "Facility workflow definition (exhibition prototype). Route-specific steps "
    "are derived from the stream handling descriptions in policy_engine.STREAMS; "
    "no external regulation is cited or invented."
)
WORKFLOW_VERSION = "2.0.0"

# ---------------------------------------------------------------------------
# Generic ordered workflow. Order is 1-based and defines the legal sequence.
# Shared by every route that has no distinct handling note.
# ---------------------------------------------------------------------------
GENERIC_STEPS = [
    {"id": "segregate", "label": "Segregate",
     "description": "Place the item in the policy-determined colour stream."},
    {"id": "secure", "label": "Secure",
     "description": "Contain the waste so it cannot spill or injure."},
    {"id": "seal_label", "label": "Seal & Label",
     "description": "Seal the container and label it with the waste category."},
    {"id": "collection", "label": "Authorized Collection",
     "description": "Hand over to authorized waste-collection personnel."},
    {"id": "treatment", "label": "Treatment / Final Disposal",
     "description": "Route to treatment or final disposal per facility policy."},
]

# Route-specific workflows. Each extra/renamed step is traceable to that
# stream's handling description in policy_engine.STREAMS.
ROUTE_WORKFLOWS = {
    # RED / Sharps — description: "...(puncture-proof container)."
    "RED": [
        {"id": "segregate", "label": "Segregate",
         "description": "Place sharps in the RED (sharps) stream only."},
        {"id": "secure", "label": "Secure",
         "description": "Contain the sharps so they cannot spill or injure."},
        {"id": "puncture_proof", "label": "Puncture-Proof Container",
         "description": "Transfer into a rigid, puncture-proof sharps container "
                        "(per the RED stream handling description)."},
        {"id": "seal_label", "label": "Seal & Label",
         "description": "Seal the container and label it as sharps."},
        {"id": "collection", "label": "Authorized Collection",
         "description": "Hand over to authorized waste-collection personnel."},
        {"id": "treatment", "label": "Treatment / Final Disposal",
         "description": "Route to treatment or final disposal per facility policy."},
    ],
    # BROWN / Pharmaceutical — description: "Expired / discarded pharmaceuticals
    # and cytotoxic drugs."
    "BROWN": [
        {"id": "segregate", "label": "Segregate",
         "description": "Place expired/discarded pharmaceuticals in the BROWN stream."},
        {"id": "secure", "label": "Secure",
         "description": "Contain the pharmaceutical waste so it cannot leak."},
        {"id": "quarantine", "label": "Quarantine Cytotoxic",
         "description": "Set aside cytotoxic/expired drug waste for return-or-"
                        "incineration handling (per the BROWN stream description)."},
        {"id": "seal_label", "label": "Seal & Label",
         "description": "Seal the container and label it as pharmaceutical waste."},
        {"id": "collection", "label": "Authorized Collection",
         "description": "Hand over to authorized waste-collection personnel."},
        {"id": "treatment", "label": "Treatment / Final Disposal",
         "description": "Route to treatment or final disposal per facility policy."},
    ],
    # RADIOACTIVE_STORAGE — description: "Shielded radioactive-waste storage /
    # decay area." Final handling is storage/decay, not treatment.
    "RADIOACTIVE_STORAGE": [
        {"id": "segregate", "label": "Segregate",
         "description": "Place radioactive waste in the shielded (radioactive) stream."},
        {"id": "secure", "label": "Secure",
         "description": "Contain the waste so it cannot spill or contaminate."},
        {"id": "seal_label", "label": "Seal & Label",
         "description": "Seal and label with the radioactive category and activity."},
        {"id": "shielded_storage", "label": "Shielded Storage",
         "description": "Move to shielded radioactive-waste storage "
                        "(per the stream handling description)."},
        {"id": "decay_release", "label": "Decay & Release",
         "description": "Hold in the decay area until release criteria are met."},
    ],
}

PENDING = "PENDING"
DONE = "DONE"

# Backwards-compatible alias: the event-level workflow and existing callers use
# the generic 5-step sequence.
STEPS = GENERIC_STEPS
STEP_IDS = [s["id"] for s in GENERIC_STEPS]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def steps_for_route(route_code):
    """Ordered step list for a route (falls back to the generic workflow)."""
    return ROUTE_WORKFLOWS.get(route_code, GENERIC_STEPS)


def _resolve(steps):
    """Normalise a steps argument to (steps_list, {id: step})."""
    steps = steps if steps is not None else GENERIC_STEPS
    return steps, {s["id"]: s for s in steps}


# ---------------------------------------------------------------------------
# Pure state-machine logic (no DB; unit-testable offline)
# ---------------------------------------------------------------------------
def new_state(steps=None):
    """A fresh workflow with every step PENDING (for the given step list)."""
    steps, _ = _resolve(steps)
    return {"steps": {s["id"]: {"status": PENDING, "completed_at": None}
                      for s in steps}}


def current_step_id(state, steps=None):
    """The next step that must be completed, or None if the workflow is done."""
    steps, _ = _resolve(steps)
    done = (state or {}).get("steps", {})
    for s in steps:
        if done.get(s["id"], {}).get("status") != DONE:
            return s["id"]
    return None


def is_complete(state, steps=None):
    return current_step_id(state, steps) is None


def apply_completion(state, step_id, now=None, steps=None):
    """
    Attempt to mark ``step_id`` complete within the given workflow.

    Returns ``(new_state, error_code)``. On success error_code is None; on
    failure new_state is unchanged and error_code is one of:
    UNKNOWN_STEP, ALREADY_COMPLETE, OUT_OF_ORDER.
    """
    steps, by_id = _resolve(steps)
    if step_id not in by_id:
        return state, "UNKNOWN_STEP"

    current = dict((state or new_state(steps)).get("steps", {}))
    if current.get(step_id, {}).get("status") == DONE:
        return state, "ALREADY_COMPLETE"

    expected = current_step_id(state, steps)
    if step_id != expected:
        return state, "OUT_OF_ORDER"

    now = now or _now()
    new_steps = {k: dict(v) for k, v in current.items()}
    new_steps[step_id] = {"status": DONE, "completed_at": now}
    return {"steps": new_steps}, None


# ---------------------------------------------------------------------------
# View builder (frontend-friendly, ordered)
# ---------------------------------------------------------------------------
def view(subject_id, state, steps=None):
    steps, _ = _resolve(steps)
    done = (state or {}).get("steps", {})
    ordered = []
    for i, s in enumerate(steps):
        st = done.get(s["id"], {})
        ordered.append({
            "id": s["id"],
            "order": i + 1,
            "label": s["label"],
            "description": s["description"],
            "status": st.get("status", PENDING),
            "completed_at": st.get("completed_at"),
        })
    completed = sum(1 for s in ordered if s["status"] == DONE)
    cur = current_step_id(state, steps)
    return {
        "event_id": subject_id,
        "steps": ordered,
        "current_step": cur,
        "completed_count": completed,
        "total_steps": len(steps),
        "is_complete": cur is None,
        "workflow_source": WORKFLOW_SOURCE,
        "workflow_version": WORKFLOW_VERSION,
        "note": ("Operational workflow states for the exhibition prototype; "
                 "not a universal clinical or legal procedure."),
    }


# ---------------------------------------------------------------------------
# Service layer (ties event existence + persistence together)
# ---------------------------------------------------------------------------
def get_workflow(event_id):
    """
    Return the workflow view for an event, creating it on first access.

    Returns None if the event does not exist (caller -> 404). Event-level
    disposal uses the generic workflow (kept for backward compatibility).
    """
    if not audit_store.get_event(event_id):
        return None
    state = audit_store.get_disposal(event_id)
    if state is None:
        state = new_state()
        audit_store.save_disposal(event_id, state)
    return view(event_id, state)


# error_code -> HTTP status for the route layer.
_HTTP_FOR_ERROR = {
    "EVENT_NOT_FOUND": 404,
    "UNKNOWN_STEP": 404,
    "ALREADY_COMPLETE": 409,
    "OUT_OF_ORDER": 409,
}


def complete_step(event_id, step_id):
    """
    Complete a workflow step for an event (generic event-level workflow).

    Returns ``(payload, http_status)``.
    """
    if not audit_store.get_event(event_id):
        return {"status": "error", "error": "Event not found.",
                "code": "EVENT_NOT_FOUND"}, 404

    state = audit_store.get_disposal(event_id)
    if state is None:
        state = new_state()

    new_state_, err = apply_completion(state, step_id)
    if err:
        msg = {
            "UNKNOWN_STEP": f"Unknown workflow step '{step_id}'.",
            "ALREADY_COMPLETE": f"Step '{step_id}' is already complete.",
            "OUT_OF_ORDER": (
                f"Cannot complete '{step_id}' before earlier steps; "
                f"next required step is '{current_step_id(state)}'."),
        }[err]
        return {"status": "error", "error": msg, "code": err,
                "workflow": view(event_id, state)}, _HTTP_FOR_ERROR[err]

    audit_store.save_disposal(event_id, new_state_)
    return {"status": "ok", "workflow": view(event_id, new_state_)}, 200


def definition(route_code=None):
    """Workflow definition for the frontend to render the tracker.

    When ``route_code`` is given, returns that route's (possibly route-specific)
    workflow; otherwise the generic workflow. Always carries provenance.
    """
    steps = steps_for_route(route_code) if route_code else GENERIC_STEPS
    ordered = [{**s, "order": i + 1} for i, s in enumerate(steps)]
    return {
        "route_code": route_code,
        "steps": ordered,
        "total_steps": len(ordered),
        "workflow_source": WORKFLOW_SOURCE,
        "workflow_version": WORKFLOW_VERSION,
    }
