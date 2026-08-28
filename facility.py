# facility.py
"""
Facility CONTEXT configuration — the single source of truth for the wards an
operator may attribute a scan to.

Why this is separate from ``policy_engine``:
    ``policy_engine`` is the disposal DECISION authority (waste type, expected
    route, compliance). Ward/station is operational *context* attached to an
    audit event; it never influences a disposal decision. Keeping it in its own
    module preserves that boundary — nothing here can change a route.

Ward context is what makes the Dashboard's per-ward compliance analytics real:
every ward figure is aggregated from the ``ward`` column of persisted audit
events, so the value chosen at scan time must be a configured ward id.

Configuration
-------------
Override the list without code changes via ``FACILITY_WARDS``, a comma-separated
list of ``id:label`` pairs (label optional), e.g.

    FACILITY_WARDS="ER:Emergency,ICU-1:Intensive Care 1,LAB"

UNKNOWN ward
------------
``None`` is an intentional, pre-existing state: historical events (and the
legacy staff UI, which never collected a ward) have no ward. The API therefore
accepts an omitted ward and stores NULL rather than silently inventing one, but
REJECTS a ward that is not configured. The /scan UI requires an explicit
selection so no new event is defaulted to an arbitrary ward.
"""

import os

FACILITY_PROFILE = os.getenv("FACILITY_PROFILE", "default")

# Default ward registry for the exhibition facility profile. Ids are stable
# identifiers persisted on the audit event; labels are display-only.
_DEFAULT_WARDS = [
    {"id": "ER", "label": "Emergency", "department": "Emergency"},
    {"id": "ICU-1", "label": "Intensive Care 1", "department": "Critical Care"},
    {"id": "ICU-2", "label": "Intensive Care 2", "department": "Critical Care"},
    {"id": "OT-1", "label": "Operating Theatre 1", "department": "Surgery"},
    {"id": "WARD-A", "label": "General Ward A", "department": "Inpatient"},
    {"id": "LAB", "label": "Pathology Lab", "department": "Diagnostics"},
    {"id": "OPD", "label": "Outpatient Department", "department": "Outpatient"},
]


def _parse_env_wards(raw):
    """Parse FACILITY_WARDS ("id:label,id2" -> ward dicts). Invalid/empty -> []."""
    out = []
    seen = set()
    for chunk in (raw or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        ward_id, _, label = chunk.partition(":")
        ward_id = ward_id.strip()
        if not ward_id or ward_id.upper() in seen:
            continue
        seen.add(ward_id.upper())
        out.append({"id": ward_id, "label": (label.strip() or ward_id),
                    "department": None})
    return out


def wards():
    """The configured wards, in display order. Never empty."""
    return _parse_env_wards(os.getenv("FACILITY_WARDS")) or list(_DEFAULT_WARDS)


def ward_ids():
    """Just the ward ids (what gets persisted on an audit event)."""
    return [w["id"] for w in wards()]


def get_ward(ward_id):
    """The ward dict for an id (case-insensitive), or None."""
    key = ("" if ward_id is None else str(ward_id)).strip().upper()
    if not key:
        return None
    for w in wards():
        if w["id"].upper() == key:
            return w
    return None


def normalize_ward(value):
    """
    Resolve an incoming ward value to its canonical configured id.

    Returns ``(ward_id, ok)``:
        (None, True)      -> no ward supplied; the intentional UNKNOWN state
        ("ER", True)      -> recognised, canonicalised
        (raw, False)      -> supplied but NOT configured; caller should reject
    """
    raw = ("" if value is None else str(value)).strip()
    if not raw:
        return None, True
    ward = get_ward(raw)
    if ward:
        return ward["id"], True
    return raw, False


def is_valid_ward(value):
    _, ok = normalize_ward(value)
    return ok


def context():
    """Facility context metadata for the UI (no secrets)."""
    return {
        "facility_profile": FACILITY_PROFILE,
        "wards": wards(),
        "ward_count": len(wards()),
        # There is no default ward on purpose: the operator must choose, so a
        # ward figure on the dashboard always reflects a real attribution.
        "default_ward": None,
        "unknown_ward_allowed": True,
    }
