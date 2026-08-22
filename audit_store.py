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
    "image_filename", "image_id", "station",
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
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    with _write_lock, _connect() as conn:
        conn.executescript(_SCHEMA)


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
    """Aggregate compliance analytics computed live from the DB."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM events").fetchall()

    total = len(rows)
    status_counts = {"CORRECT": 0, "VIOLATION": 0, "REVIEW_REQUIRED": 0,
                     "PENDING_VERIFICATION": 0, "OTHER": 0}
    violations_by_type = {}
    violations_by_route = {}
    by_station = {}

    for r in rows:
        status = r["compliance_status"] or "PENDING_VERIFICATION"
        status_counts[status] = status_counts.get(status, 0) + 1

        if status == "VIOLATION":
            wt = r["canonical_category"] or "UNKNOWN"
            violations_by_type[wt] = violations_by_type.get(wt, 0) + 1
            ar = r["actual_route"] or "UNKNOWN"
            violations_by_route[ar] = violations_by_route.get(ar, 0) + 1

        station = r["station"]
        if station:
            s = by_station.setdefault(
                station, {"total": 0, "correct": 0, "violations": 0})
            s["total"] += 1
            if status == "CORRECT":
                s["correct"] += 1
            elif status == "VIOLATION":
                s["violations"] += 1

    verified = status_counts.get("CORRECT", 0) + status_counts.get("VIOLATION", 0)
    compliance_rate = (
        round(status_counts.get("CORRECT", 0) / verified * 100, 1)
        if verified else None
    )

    return {
        "total_events": total,
        "correct": status_counts.get("CORRECT", 0),
        "violations": status_counts.get("VIOLATION", 0),
        "review_required": status_counts.get("REVIEW_REQUIRED", 0),
        "pending_verification": status_counts.get("PENDING_VERIFICATION", 0),
        "verified": verified,
        "compliance_rate": compliance_rate,
        "violations_by_waste_type": violations_by_type,
        "violations_by_route": violations_by_route,
        "station_performance": by_station,
        "has_station_data": bool(by_station),
    }
