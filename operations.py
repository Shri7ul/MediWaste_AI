# operations.py
"""
Operations / bin-capacity view (SIMULATED for the exhibition).

IMPORTANT — HONESTY BOUNDARY:
    There is NO physical bin sensing, IoT hardware, weight cell, or RFID in this
    system. Bin fill levels here are SIMULATED. Every response is tagged
    ``"data_source": "SIMULATED"`` so the frontend cannot present it as live
    sensor telemetry.

The simulation is deterministic and lightly grounded on REAL recorded routing
activity (how many audit events were routed to each stream), so the demo view
is stable across reloads and loosely tracks actual usage — but it remains a
prototype visualisation, not a measurement.
"""

import hashlib

import audit_store
import policy_engine
import collection

DATA_SOURCE = "SIMULATED"

# A nominal capacity per bin (arbitrary demo units), used only to render a
# fill percentage. Not a physical measurement.
_NOMINAL_CAPACITY = 100


def _bins_from_policy():
    """One bin per selectable disposal stream, derived from the policy engine
    (the single source of truth for streams/colours)."""
    bins = []
    for code in policy_engine.valid_routes():
        meta = policy_engine.route_meta(code) or {}
        bins.append({
            "bin_id": code.lower(),
            "route_code": code,
            "label": meta.get("label"),
            "category": meta.get("category"),
            "hex": meta.get("hex"),
            "description": meta.get("description"),
        })
    return bins


def _simulated_fill(bin_id, route_code, event_count):
    """Deterministic pseudo fill level in [0, 100].

    Combines a stable per-bin base (hash of the id) with real routing activity
    so the number is reproducible and loosely reflects usage — but simulated.
    """
    h = hashlib.sha256(bin_id.encode("utf-8")).hexdigest()
    base = int(h[:2], 16) % 40  # stable 0..39 baseline
    activity = min(event_count * 7, 60)  # grows with real routed events, capped
    return min(base + activity, 100)


def _status_for(pct):
    if pct >= 90:
        return "CRITICAL"
    if pct >= 75:
        return "HIGH"
    if pct >= 40:
        return "MODERATE"
    return "OK"


def _enrich(b, usage, pending):
    # Total routed events ever (informational); PENDING = not yet collected by
    # any collection job. Simulated fill is grounded on PENDING so a completed
    # collection deterministically lowers the bin — no fabricated sensor.
    total = usage.get(b["route_code"], 0)
    pending_count = pending.get(b["route_code"], 0)
    pct = _simulated_fill(b["bin_id"], b["route_code"], pending_count)
    # Backend owns the collection state: if an IN_PROGRESS job exists for this
    # route the card should offer "Continue disposal", not a fresh "Start".
    active_job = collection.active_job_summary(b["route_code"])
    return {
        **b,
        "capacity_units": _NOMINAL_CAPACITY,
        "fill_percent": pct,
        "fill_status": _status_for(pct),
        "routed_event_count": total,
        "pending_collection_count": pending_count,
        "active_job": active_job,
        "data_source": DATA_SOURCE,
        "sensing": "none",  # explicit: no physical sensing exists
    }


def list_bins():
    """All simulated bins, one per disposal stream."""
    usage = audit_store.route_usage()
    pending = audit_store.route_usage_pending()
    bins = [_enrich(b, usage, pending) for b in _bins_from_policy()]
    return {
        "data_source": DATA_SOURCE,
        "disclaimer": ("Bin fill levels are SIMULATED for the exhibition. No "
                       "physical bin sensor, IoT device, weight cell, or RFID "
                       "is used."),
        "count": len(bins),
        "bins": bins,
    }


def get_bin(bin_id):
    """A single simulated bin by id, or None if unknown."""
    bin_id = (bin_id or "").strip().lower()
    usage = audit_store.route_usage()
    pending = audit_store.route_usage_pending()
    for b in _bins_from_policy():
        if b["bin_id"] == bin_id:
            return _enrich(b, usage, pending)
    return None


def overview():
    """Operations summary across all simulated bins."""
    data = list_bins()
    bins = data["bins"]
    attention = [b for b in bins if b["fill_status"] in ("HIGH", "CRITICAL")]
    # Collection metrics are kept SEPARATE from event-based compliance analytics
    # (which live in /analytics and are never derived from bins/jobs).
    jobs = audit_store.list_collection_jobs(limit=1000)
    in_progress = sum(1 for j in jobs if j.get("status") == "IN_PROGRESS")
    completed = sum(1 for j in jobs if j.get("status") == "COMPLETED")
    return {
        "data_source": DATA_SOURCE,
        "disclaimer": data["disclaimer"],
        "total_bins": len(bins),
        "bins_needing_attention": len(attention),
        "attention": [b["bin_id"] for b in attention],
        "collections": {
            "total": len(jobs),
            "in_progress": in_progress,
            "completed": completed,
        },
        "bins": bins,
    }
