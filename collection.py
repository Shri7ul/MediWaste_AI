# collection.py
"""
Bin COLLECTION JOB service (operational).

A collection job is a DISTINCT domain object from an audit event:

    * AUDIT EVENT  = one analyzed waste item (immutable provenance + compliance).
    * COLLECTION JOB = one operational disposal/collection cycle for a bin /
      waste stream, referencing a SNAPSHOT of existing audit event_ids.

A job NEVER owns, mutates, merges, or deletes audit events. Completing a job
records operational collection state only; every event's compliance result and
provenance in the events table remain untouched.

Workflow rules reuse the sequential state machine in ``disposal.py``. The step
LIST is resolved PER ROUTE via ``disposal.steps_for_route`` — most routes share
the generic facility workflow, but a route with a distinct handling note (e.g.
RED/Sharps, BROWN/Pharmaceutical, RADIOACTIVE) has a route-specific, possibly
longer sequence derived from the repo's own policy data. The transition logic
(OUT_OF_ORDER / ALREADY_COMPLETE / UNKNOWN_STEP) is identical for every route,
so there is a single source of truth for the state machine.

Snapshot semantics: eligibility is computed AT START (effective route match AND
the event is not already part of any other job). The chosen event_ids are frozen
into the job. An event analyzed AFTER the job starts does NOT join a running job
— it belongs to the next collection cycle.
"""

import audit_store
import policy_engine
import disposal

_HTTP_FOR_ERROR = {
    "JOB_NOT_FOUND": 404,
    "UNKNOWN_STEP": 404,
    "ALREADY_COMPLETE": 409,
    "OUT_OF_ORDER": 409,
    "JOB_COMPLETE": 409,
}


def _now():
    return disposal._now()


def _steps_for(job):
    """The ordered step list for a job, resolved from its route."""
    return disposal.steps_for_route(job.get("route_code"))


def _route_for_bin(bin_id):
    """Resolve a bin_id to its canonical route_code via the policy engine
    (single source of truth for streams). Returns None if unknown."""
    bin_id = (bin_id or "").strip().lower()
    for code in policy_engine.valid_routes():
        if code.lower() == bin_id:
            return code
    return None


def eligible_events(route_code):
    """Events eligible for a NEW collection job on ``route_code``:
    effective route matches AND the event is not already in any job."""
    collected = audit_store.collected_event_ids()
    out = []
    for ev in audit_store.events_by_effective_route(route_code):
        if ev["event_id"] in collected:
            continue
        out.append(ev)
    return out


def view(job):
    """Frontend-friendly view of a job (workflow + collection metadata)."""
    if not job:
        return None
    steps = _steps_for(job)
    state = job.get("state") or disposal.new_state(steps)
    wf = disposal.view(job["job_id"], state, steps)
    meta = policy_engine.route_meta(job.get("route_code")) or {}
    return {
        "job_id": job["job_id"],
        "bin_id": job.get("bin_id"),
        "route_code": job.get("route_code"),
        "waste_stream": job.get("waste_stream") or meta.get("category"),
        "route_meta": meta,
        "ward": job.get("ward"),
        "status": job.get("status"),
        "event_ids": job.get("event_ids") or [],
        "event_count": len(job.get("event_ids") or []),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "completed_at": job.get("completed_at"),
        "workflow": {
            "steps": wf["steps"],
            "current_step": wf["current_step"],
            "completed_count": wf["completed_count"],
            "total_steps": wf["total_steps"],
            "is_complete": wf["is_complete"],
            "workflow_source": wf["workflow_source"],
            "workflow_version": wf["workflow_version"],
            "note": wf["note"],
        },
    }


def start_collection(bin_id):
    """
    Start (or resume) a collection job for a bin.

    Returns ``(payload, http_status)``. If an IN_PROGRESS job already exists for
    the route it is resumed (idempotent Start). Otherwise eligible events are
    snapshotted into a new job. If there are no eligible events, returns
    NO_ELIGIBLE_EVENTS (409) and creates nothing — never fabricates a job.
    """
    route_code = _route_for_bin(bin_id)
    if not route_code:
        return {"status": "error", "error": f"Unknown bin '{bin_id}'.",
                "code": "BIN_NOT_FOUND"}, 404

    existing = audit_store.active_job_for_route(route_code)
    if existing:
        # Resume the in-progress cycle rather than starting a duplicate.
        return {"status": "ok", "job": view(existing), "resumed": True}, 200

    events = eligible_events(route_code)
    if not events:
        return {"status": "error",
                "error": ("No routed item records are available to collect for "
                          "this stream."),
                "code": "NO_ELIGIBLE_EVENTS"}, 409

    meta = policy_engine.route_meta(route_code) or {}
    # Snapshot the eligible event ids at start; a later event won't join.
    event_ids = [ev["event_id"] for ev in events]
    # Ward is informational; use the most common ward among the snapshot.
    wards = [ev.get("ward") for ev in events if ev.get("ward")]
    ward = max(set(wards), key=wards.count) if wards else None

    job = audit_store.create_collection_job({
        "bin_id": (bin_id or "").strip().lower(),
        "route_code": route_code,
        "waste_stream": meta.get("category"),
        "ward": ward,
        "event_ids": event_ids,
        "status": "IN_PROGRESS",
        "state": disposal.new_state(disposal.steps_for_route(route_code)),
    })
    return {"status": "ok", "job": view(job), "resumed": False}, 201


def get_job(job_id):
    """Return the job view, or None if the job does not exist."""
    job = audit_store.get_collection_job(job_id)
    return view(job)


def complete_step(job_id, step_id):
    """
    Complete a workflow step for a collection job.

    Returns ``(payload, http_status)``. On the final step the job transitions to
    COMPLETED and ``completed_at`` is stamped. Audit events referenced by the job
    are never modified here — only the operational job state changes.
    """
    job = audit_store.get_collection_job(job_id)
    if not job:
        return {"status": "error", "error": "Collection job not found.",
                "code": "JOB_NOT_FOUND"}, 404

    if job.get("status") == "COMPLETED":
        return {"status": "error", "error": "This collection job is complete.",
                "code": "JOB_COMPLETE", "job": view(job)}, 409

    steps = _steps_for(job)
    state = job.get("state") or disposal.new_state(steps)
    new_state, err = disposal.apply_completion(state, step_id, steps=steps)
    if err:
        msg = {
            "UNKNOWN_STEP": f"Unknown workflow step '{step_id}'.",
            "ALREADY_COMPLETE": f"Step '{step_id}' is already complete.",
            "OUT_OF_ORDER": (
                f"Cannot complete '{step_id}' before earlier steps; next "
                f"required step is '{disposal.current_step_id(state, steps)}'."),
        }[err]
        return {"status": "error", "error": msg, "code": err,
                "job": view(job)}, _HTTP_FOR_ERROR[err]

    fields = {"state": new_state}
    if disposal.is_complete(new_state, steps):
        fields["status"] = "COMPLETED"
        fields["completed_at"] = _now()

    updated = audit_store.update_collection_job(job_id, **fields)
    return {"status": "ok", "job": view(updated)}, 200


def list_jobs(limit=100, offset=0):
    jobs = audit_store.list_collection_jobs(limit=limit, offset=offset)
    return [view(j) for j in jobs]


def events_for_job(job_id):
    """The audit events referenced by a job's snapshot, in snapshot order.

    Returns ``None`` if the job does not exist. Events are returned READ-ONLY
    (straight from the audit store); this never mutates the audit trail. Missing
    events (should not happen) are simply skipped.
    """
    job = audit_store.get_collection_job(job_id)
    if not job:
        return None
    out = []
    for eid in job.get("event_ids") or []:
        ev = audit_store.get_event(eid)
        if ev:
            out.append(ev)
    return out


def active_job_summary(route_code):
    """Compact view of the IN_PROGRESS job for a route (or None) — used by the
    Operations bin cards to render the 'Collection in progress / Continue' state
    without the frontend deriving workflow state itself."""
    job = audit_store.active_job_for_route(route_code)
    if not job:
        return None
    steps = _steps_for(job)
    state = job.get("state") or disposal.new_state(steps)
    wf = disposal.view(job["job_id"], state, steps)
    cur = next((s for s in wf["steps"] if s["id"] == wf["current_step"]), None)
    return {
        "job_id": job["job_id"],
        "status": job.get("status"),
        "item_count": len(job.get("event_ids") or []),
        "completed_count": wf["completed_count"],
        "total_steps": wf["total_steps"],
        "current_step": wf["current_step"],
        "current_step_label": cur["label"] if cur else None,
    }


def definition(route_code=None):
    """Workflow definition (route-aware), shared with the event-level tracker."""
    return disposal.definition(route_code)
