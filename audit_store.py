# audit_store.py
"""
Local, persistent audit trail (SQLite).

Every completed analysis creates an event; verification updates it. The store
survives application restarts (file-backed at audit.db) and is safe for Flask's
threaded dev server (one short-lived connection per call + a write lock).

Nothing here is cached in memory across requests — audit state is always read
fresh from disk.
"""

import os
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

DB_PATH = os.getenv(
    "AUDIT_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit.db"),
)

_write_lock = threading.Lock()

# Columns stored as JSON text.
_JSON_COLS = {"detected_items", "raw_labels", "visual_context", "evidence_ids", "payload"}

_COLUMNS = [
    "event_id", "created_at", "updated_at",
    "image_filename", "image_id", "station", "ward",
    "detected_items", "raw_labels", "confidence",
    "visual_context", "canonical_category",
    "expected_route", "actual_route",
    "compliance_status", "reason_code",
    "rule_id", "policy_version",
    "model_id", "model_version",
    "evidence_ids", "rag_status", "llm_status",
    "payload",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id           TEXT PRIMARY KEY,
    created_at         TEXT NOT NULL,
    updated_at         TEXT,
    image_filename     TEXT,
    image_id           TEXT,
    station            TEXT,
    ward               TEXT,
    detected_items     TEXT,
    raw_labels         TEXT,
    confidence         REAL,
    visual_context     TEXT,
    canonical_category TEXT,
    expected_route     TEXT,
    actual_route       TEXT,
    compliance_status  TEXT,
    reason_code        TEXT,
    rule_id            TEXT,
    policy_version     TEXT,
    model_id           TEXT,
    model_version      TEXT,
    evidence_ids       TEXT,
    rag_status         TEXT,
    llm_status         TEXT,
    payload            TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_status  ON events(compliance_status);

-- Disposal workflow state, one row per event. The workflow is a sequential
-- state machine (see disposal.py); the full state dict is stored as JSON so a
-- schema change to the step list never requires a DB migration. Provenance in
-- the events table is never overwritten by workflow progress.
CREATE TABLE IF NOT EXISTS disposal_workflow (
    event_id    TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    updated_at  TEXT,
    state       TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(event_id)
);

-- Bin COLLECTION JOB. An operational disposal cycle for one bin / waste
-- stream. It is a DISTINCT domain object from an audit event: it references a
-- snapshot of existing audit event_ids (event_ids JSON array) but never owns,
-- mutates, or deletes them. The 5-step workflow (see disposal.py) is persisted
-- here as `state`; job lifecycle status is IN_PROGRESS -> COMPLETED. Audit
-- provenance and compliance results in the events table are never touched by a
-- collection job.
CREATE TABLE IF NOT EXISTS collection_job (
    job_id       TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL,
    updated_at   TEXT,
    completed_at TEXT,
    bin_id       TEXT,
    route_code   TEXT,
    waste_stream TEXT,
    ward         TEXT,
    event_ids    TEXT NOT NULL,
    status       TEXT NOT NULL,
    state        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cjob_route  ON collection_job(route_code);
CREATE INDEX IF NOT EXISTS idx_cjob_status ON collection_job(status);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _migrate(conn):
    """Add columns introduced after the first release, idempotently.

    Existing databases (e.g. the bundled audit.db with historical events) are
    upgraded in place without destroying any recorded provenance.
    """
    existing = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    if "ward" not in existing:
        conn.execute("ALTER TABLE events ADD COLUMN ward TEXT")


def init_db():
    with _write_lock, _connect() as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)


# Ensure the table exists as soon as the module is imported.
init_db()


def _encode(col, value):
    if col in _JSON_COLS:
        return json.dumps(value, ensure_ascii=False) if value is not None else None
    return value


def _decode(col, value):
    if col in _JSON_COLS and value is not None:
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _row_to_dict(row):
    if row is None:
        return None
    return {col: _decode(col, row[col]) for col in row.keys()}


def create_event(event):
    """
    Insert a new audit event. Generates event_id / created_at if absent.
    Unknown keys are preserved inside the 'payload' JSON blob.
    Returns the stored event dict.
    """
    event = dict(event or {})
    event.setdefault("event_id", uuid.uuid4().hex)
    event.setdefault("created_at", _now())
    event.setdefault("updated_at", event["created_at"])

    known = {k: event.get(k) for k in _COLUMNS}
    # Stash any extra keys into payload without losing them.
    extra = {k: v for k, v in event.items() if k not in _COLUMNS}
    if extra:
        payload = known.get("payload") or {}
        if isinstance(payload, dict):
            payload = {**extra, **payload}
        known["payload"] = payload

    cols = list(_COLUMNS)
    placeholders = ",".join("?" for _ in cols)
    values = [_encode(c, known.get(c)) for c in cols]

    with _write_lock, _connect() as conn:
        conn.execute(
            f"INSERT INTO events ({','.join(cols)}) VALUES ({placeholders})",
            values,
        )
    return get_event(known["event_id"])


def update_event(event_id, **fields):
    """Update selected columns of an existing event (e.g. after verification)."""
    fields = {k: v for k, v in fields.items() if k in _COLUMNS and k != "event_id"}
    fields["updated_at"] = _now()
    assignments = ",".join(f"{k}=?" for k in fields)
    values = [_encode(k, v) for k, v in fields.items()] + [event_id]
    with _write_lock, _connect() as conn:
        cur = conn.execute(
            f"UPDATE events SET {assignments} WHERE event_id=?", values
        )
        changed = cur.rowcount
    return get_event(event_id) if changed else None


def get_event(event_id):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE event_id=?", (event_id,)
        ).fetchone()
    return _row_to_dict(row)


def list_events(limit=100, offset=0):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY created_at DESC, rowid DESC "
            "LIMIT ? OFFSET ?",
            (int(limit), int(offset)),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_events():
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]


def analytics():
    """Aggregate compliance analytics computed live from the DB.

    All figures are derived from REAL persisted events — nothing is fabricated.
    Rates are null (not zero) when there is no denominator, so the frontend can
    distinguish "0%" from "not enough data yet".
    """
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM events").fetchall()

    total = len(rows)
    status_counts = {"CORRECT": 0, "VIOLATION": 0, "REVIEW_REQUIRED": 0,
                     "PENDING_VERIFICATION": 0, "OTHER": 0}
    violations_by_type = {}
    violations_by_route = {}
    by_type = {}
    by_station = {}
    by_ward = {}
    top_violations = []

    def _bucket(mapping, key):
        return mapping.setdefault(
            key, {"total": 0, "correct": 0, "violations": 0,
                  "review_required": 0, "pending": 0})

    for r in rows:
        status = r["compliance_status"] or "PENDING_VERIFICATION"
        status_counts[status] = status_counts.get(status, 0) + 1

        wt = r["canonical_category"] or "UNKNOWN"
        t = _bucket(by_type, wt)
        t["total"] += 1
        if status == "CORRECT":
            t["correct"] += 1
        elif status == "VIOLATION":
            t["violations"] += 1
        elif status == "REVIEW_REQUIRED":
            t["review_required"] += 1
        elif status == "PENDING_VERIFICATION":
            t["pending"] += 1

        if status == "VIOLATION":
            violations_by_type[wt] = violations_by_type.get(wt, 0) + 1
            ar = r["actual_route"] or "UNKNOWN"
            violations_by_route[ar] = violations_by_route.get(ar, 0) + 1
            top_violations.append({
                "event_id": r["event_id"],
                "waste_type": wt,
                "expected_route": r["expected_route"],
                "actual_route": r["actual_route"],
                "reason_code": r["reason_code"],
                "station": r["station"],
                "ward": r["ward"] if "ward" in r.keys() else None,
                "created_at": r["created_at"],
            })

        station = r["station"]
        if station:
            s = _bucket(by_station, station)
            s["total"] += 1
            if status == "CORRECT":
                s["correct"] += 1
            elif status == "VIOLATION":
                s["violations"] += 1
            elif status == "REVIEW_REQUIRED":
                s["review_required"] += 1
            elif status == "PENDING_VERIFICATION":
                s["pending"] += 1

        ward = r["ward"] if "ward" in r.keys() else None
        if ward:
            w = _bucket(by_ward, ward)
            w["total"] += 1
            if status == "CORRECT":
                w["correct"] += 1
            elif status == "VIOLATION":
                w["violations"] += 1
            elif status == "REVIEW_REQUIRED":
                w["review_required"] += 1
            elif status == "PENDING_VERIFICATION":
                w["pending"] += 1

    correct = status_counts.get("CORRECT", 0)
    violations = status_counts.get("VIOLATION", 0)
    review_required = status_counts.get("REVIEW_REQUIRED", 0)
    verified = correct + violations

    def _rate(num, den):
        return round(num / den * 100, 1) if den else None

    # Most recent violations first, capped.
    top_violations.sort(key=lambda v: v["created_at"] or "", reverse=True)

    return {
        "total_events": total,
        "correct": correct,
        "violations": violations,
        "review_required": review_required,
        "pending_verification": status_counts.get("PENDING_VERIFICATION", 0),
        "verified": verified,
        # Compliance rate is over VERIFIED events; violation/review rates are
        # over ALL events so they sum meaningfully for the dashboard.
        "compliance_rate": _rate(correct, verified),
        "violation_rate": _rate(violations, total),
        "review_rate": _rate(review_required, total),
        "by_waste_type": by_type,
        "by_station": by_station,
        "by_ward": by_ward,
        "top_violations": top_violations[:10],
        "has_station_data": bool(by_station),
        "has_ward_data": bool(by_ward),
        # Retained for backward compatibility with the existing UI/tests.
        "violations_by_waste_type": violations_by_type,
        "violations_by_route": violations_by_route,
        "station_performance": by_station,
        "data_source": "REAL_EVENTS",
    }


def route_usage():
    """Count events per disposal route (actual route if verified, else expected).

    Used by the operations view to ground simulated bin fill on real routing
    activity. Returns {ROUTE_CODE: count}.
    """
    counts = {}
    with _connect() as conn:
        rows = conn.execute(
            "SELECT expected_route, actual_route FROM events").fetchall()
    for r in rows:
        route = r["actual_route"] or r["expected_route"]
        if route:
            counts[route] = counts.get(route, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Disposal workflow persistence (state machine logic lives in disposal.py).
# ---------------------------------------------------------------------------
def get_disposal(event_id):
    """Return the stored workflow state dict for an event, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT state FROM disposal_workflow WHERE event_id=?", (event_id,)
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["state"])
    except (ValueError, TypeError):
        return None


def save_disposal(event_id, state):
    """Upsert the workflow state dict for an event."""
    now = _now()
    blob = json.dumps(state, ensure_ascii=False)
    with _write_lock, _connect() as conn:
        conn.execute(
            "INSERT INTO disposal_workflow (event_id, created_at, updated_at, state) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(event_id) DO UPDATE SET updated_at=excluded.updated_at, "
            "state=excluded.state",
            (event_id, now, now, blob),
        )
    return get_disposal(event_id)


# ---------------------------------------------------------------------------
# Bin collection jobs (operational). Service logic lives in collection.py.
# An event_id may appear in at most one job; membership takes it out of the
# pending-collection queue but NEVER removes it from the audit trail.
# ---------------------------------------------------------------------------
def _cjob_to_dict(row):
    if row is None:
        return None
    d = {k: row[k] for k in row.keys()}
    try:
        d["event_ids"] = json.loads(d.get("event_ids") or "[]")
    except (ValueError, TypeError):
        d["event_ids"] = []
    try:
        d["state"] = json.loads(d["state"]) if d.get("state") else None
    except (ValueError, TypeError):
        d["state"] = None
    return d


def create_collection_job(job):
    """Insert a new collection job. Generates job_id/created_at if absent.

    `event_ids` is a snapshot list; `state` is the workflow-state dict.
    Returns the stored job dict.
    """
    job = dict(job or {})
    job.setdefault("job_id", "job_" + uuid.uuid4().hex[:12])
    now = _now()
    job.setdefault("created_at", now)
    job.setdefault("updated_at", now)
    job.setdefault("status", "IN_PROGRESS")
    event_ids = json.dumps(job.get("event_ids") or [], ensure_ascii=False)
    state = json.dumps(job.get("state") or {}, ensure_ascii=False)
    with _write_lock, _connect() as conn:
        conn.execute(
            "INSERT INTO collection_job (job_id, created_at, updated_at, "
            "completed_at, bin_id, route_code, waste_stream, ward, event_ids, "
            "status, state) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (job["job_id"], job["created_at"], job["updated_at"],
             job.get("completed_at"), job.get("bin_id"), job.get("route_code"),
             job.get("waste_stream"), job.get("ward"), event_ids,
             job["status"], state),
        )
    return get_collection_job(job["job_id"])


def get_collection_job(job_id):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM collection_job WHERE job_id=?", (job_id,)
        ).fetchone()
    return _cjob_to_dict(row)


def list_collection_jobs(limit=100, offset=0):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM collection_job ORDER BY created_at DESC, rowid DESC "
            "LIMIT ? OFFSET ?", (int(limit), int(offset)),
        ).fetchall()
    return [_cjob_to_dict(r) for r in rows]


def update_collection_job(job_id, **fields):
    """Update selected columns of a job. `state` (dict) is JSON-encoded."""
    allowed = {"updated_at", "completed_at", "status", "state", "event_ids"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if "state" in fields and fields["state"] is not None:
        fields["state"] = json.dumps(fields["state"], ensure_ascii=False)
    if "event_ids" in fields and fields["event_ids"] is not None:
        fields["event_ids"] = json.dumps(fields["event_ids"], ensure_ascii=False)
    fields["updated_at"] = _now()
    assignments = ",".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [job_id]
    with _write_lock, _connect() as conn:
        cur = conn.execute(
            f"UPDATE collection_job SET {assignments} WHERE job_id=?", values
        )
        changed = cur.rowcount
    return get_collection_job(job_id) if changed else None


def active_job_for_route(route_code):
    """The oldest IN_PROGRESS job for a route, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM collection_job WHERE route_code=? AND status='IN_PROGRESS' "
            "ORDER BY created_at ASC, rowid ASC LIMIT 1", (route_code,)
        ).fetchone()
    return _cjob_to_dict(row)


def collected_event_ids():
    """Set of every event_id referenced by ANY collection job (in-progress or
    completed). Membership removes an event from the pending-collection queue."""
    ids = set()
    with _connect() as conn:
        rows = conn.execute("SELECT event_ids FROM collection_job").fetchall()
    for r in rows:
        try:
            for eid in json.loads(r["event_ids"] or "[]"):
                ids.add(eid)
        except (ValueError, TypeError):
            pass
    return ids


def event_job_map():
    """Map of event_id -> job_id for every event referenced by a collection job.

    An event is snapshotted into at most one job (once collected it is excluded
    from future eligibility), so this is a clean 1:1 lookup used to tag events
    with their collection job. If a duplicate is ever seen, the most recently
    created job wins."""
    mapping = {}
    with _connect() as conn:
        rows = conn.execute(
            "SELECT job_id, event_ids FROM collection_job "
            "ORDER BY created_at ASC, rowid ASC").fetchall()
    for r in rows:
        try:
            for eid in json.loads(r["event_ids"] or "[]"):
                mapping[eid] = r["job_id"]
        except (ValueError, TypeError):
            pass
    return mapping


def route_usage_pending():
    """Per-route count of events NOT yet part of any collection job.

    Uses the effective route (actual if verified, else expected), mirroring
    ``route_usage``. This is what the simulated bin fill is grounded on, so a
    completed collection deterministically lowers the bin's fill level.
    """
    collected = collected_event_ids()
    counts = {}
    with _connect() as conn:
        rows = conn.execute(
            "SELECT event_id, expected_route, actual_route FROM events").fetchall()
    for r in rows:
        if r["event_id"] in collected:
            continue
        route = r["actual_route"] or r["expected_route"]
        if route:
            counts[route] = counts.get(route, 0) + 1
    return counts


def events_by_effective_route(route_code):
    """All events whose effective route (actual if set, else expected) equals
    ``route_code``, oldest first. Used to snapshot a bin's eligible events."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE actual_route=? "
            "OR (actual_route IS NULL AND expected_route=?) "
            "ORDER BY created_at ASC, rowid ASC",
            (route_code, route_code),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]
