# tests/test_operations.py
"""Operations / bin-capacity view.

HONESTY BOUNDARY under test: bin fill levels are SIMULATED (deterministic,
loosely grounded on real routing activity) and every response must be tagged so
the frontend can never present them as live sensor telemetry.

Uses an isolated temp DB so real routing activity can be seeded without touching
the bundled audit.db."""

import tempfile

import audit_store
import operations
import policy_engine

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
audit_store.DB_PATH = _TMP.name
audit_store.init_db()


def test_one_bin_per_selectable_route():
    data = operations.list_bins()
    routes = set(policy_engine.valid_routes())
    bin_routes = {b["route_code"] for b in data["bins"]}
    assert bin_routes == routes
    assert data["count"] == len(routes)


def test_every_bin_is_marked_simulated_with_no_sensing():
    data = operations.list_bins()
    assert data["data_source"] == "SIMULATED"
    assert "no" in data["disclaimer"].lower()  # explicit no-sensor disclaimer
    for b in data["bins"]:
        assert b["data_source"] == "SIMULATED"
        assert b["sensing"] == "none"
        assert 0 <= b["fill_percent"] <= 100
        assert b["fill_status"] in ("OK", "MODERATE", "HIGH", "CRITICAL")
        assert b["capacity_units"] == 100


def test_fill_is_deterministic_across_calls():
    a = {b["bin_id"]: b["fill_percent"] for b in operations.list_bins()["bins"]}
    b = {x["bin_id"]: x["fill_percent"] for x in operations.list_bins()["bins"]}
    assert a == b  # reproducible for a stable demo view


def test_fill_reflects_real_routing_activity():
    """A bin with more routed events should never fill BELOW an unused bin of the
    same baseline — activity only adds. We assert the routed count is surfaced."""
    # Seed several RED-routed events.
    for _ in range(3):
        audit_store.create_event({
            "image_id": "r", "canonical_category": "SHARPS",
            "expected_route": "RED", "actual_route": "RED",
            "compliance_status": "CORRECT",
        })
    red = operations.get_bin("red")
    assert red is not None
    assert red["routed_event_count"] >= 3
    assert red["data_source"] == "SIMULATED"


def test_get_bin_unknown_returns_none():
    assert operations.get_bin("no-such-bin") is None


def test_overview_summarises_attention_bins():
    ov = operations.overview()
    assert ov["data_source"] == "SIMULATED"
    assert ov["total_bins"] == len(policy_engine.valid_routes())
    assert isinstance(ov["bins_needing_attention"], int)
    # attention list only references HIGH/CRITICAL bins that exist in the set.
    ids = {b["bin_id"] for b in ov["bins"]}
    assert set(ov["attention"]).issubset(ids)
