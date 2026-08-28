# tests/test_api.py
"""HTTP surface tests (Flask).

Only the endpoints that do NOT require the vision stack or network are exercised
here; live inference is covered by verify_integrations.py. The whole module is
skipped automatically when Flask/pytest is not installed (e.g. the offline
runner), so it never blocks the deterministic-core suite."""

import tempfile

import pytest

pytest.importorskip("flask")

import audit_store  # noqa: E402

# Isolate the audit DB before the app touches it.
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
audit_store.DB_PATH = _TMP.name
audit_store.init_db()

from app import app  # noqa: E402


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health_exposes_booleans_no_secret_values(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    cfg = data["config"]
    for k in ("roboflow_configured", "pinecone_configured", "openrouter_configured"):
        assert isinstance(cfg[k], bool)
    # No secret material should ever appear in the health payload.
    body = r.get_data(as_text=True).lower()
    assert "api_key" not in body
    assert "bearer" not in body


def test_policy_endpoint_is_single_source_of_truth(client):
    r = client.get("/policy")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["valid_routes"]) == 7
    assert data["route_meta"]["RED"]["hex"].startswith("#")
    assert data["policy_version"]
    assert data["accept_threshold"] is not None


def test_events_and_analytics_ok(client):
    r1 = client.get("/events")
    assert r1.status_code == 200
    assert "events" in r1.get_json()
    r2 = client.get("/analytics")
    assert r2.status_code == 200
    assert "total_events" in r2.get_json()["analytics"]


def test_analyze_without_file_is_400(client):
    r = client.post("/analyze")
    assert r.status_code == 400
    assert r.get_json()["status"] == "error"


def test_verify_requires_event_id(client):
    r = client.post("/verify", json={})
    assert r.status_code == 400
    assert "event_id" in r.get_json()["error"]


def test_verify_unknown_event_is_404(client):
    r = client.post("/verify", json={"event_id": "nope", "actual_route": "RED"})
    assert r.status_code == 404


def test_unknown_route_is_404(client):
    assert client.get("/no-such-endpoint").status_code == 404


# --- Upload error handling ---------------------------------------------------
def test_analyze_unsupported_file_type_is_415(client):
    import io
    data = {"image": (io.BytesIO(b"not an image"), "notes.txt")}
    r = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert r.status_code == 415
    body = r.get_json()
    assert body["status"] == "error"
    assert body["code"] == "UNSUPPORTED_TYPE"


def test_analyze_empty_filename_is_400(client):
    import io
    data = {"image": (io.BytesIO(b""), "")}
    r = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert r.status_code == 400
    assert r.get_json()["status"] == "error"


# --- Operations (SIMULATED bins) --------------------------------------------
def test_operations_bins_marked_simulated(client):
    r = client.get("/operations/bins")
    assert r.status_code == 200
    data = r.get_json()
    assert data["data_source"] == "SIMULATED"
    assert data["count"] == 7
    for b in data["bins"]:
        assert b["data_source"] == "SIMULATED"
        assert b["sensing"] == "none"
    # No claim of physical sensing anywhere in the payload.
    body = r.get_data(as_text=True).lower()
    assert "iot" not in body or "no " in body  # disclaimer negates IoT claims


def test_operations_overview_ok(client):
    r = client.get("/operations")
    assert r.status_code == 200
    ov = r.get_json()["operations"]
    assert ov["data_source"] == "SIMULATED"
    assert ov["total_bins"] == 7


def test_operations_single_bin_and_404(client):
    r = client.get("/operations/bins/red")
    assert r.status_code == 200
    assert r.get_json()["bin"]["route_code"] == "RED"
    r2 = client.get("/operations/bins/not-a-bin")
    assert r2.status_code == 404
    assert r2.get_json()["code"] == "BIN_NOT_FOUND"


# --- Disposal workflow -------------------------------------------------------
def _seed_event():
    return audit_store.create_event({
        "image_id": "api-wf", "canonical_category": "SHARPS",
        "expected_route": "RED", "compliance_status": "PENDING_VERIFICATION",
    })["event_id"]


def test_disposal_definition_lists_five_steps(client):
    r = client.get("/disposal/definition")
    assert r.status_code == 200
    assert r.get_json()["total_steps"] == 5


def test_disposal_get_missing_event_is_404(client):
    r = client.get("/disposal/does-not-exist")
    assert r.status_code == 404
    assert r.get_json()["code"] == "EVENT_NOT_FOUND"


def test_disposal_creation_and_sequential_completion(client):
    eid = _seed_event()
    r = client.get(f"/disposal/{eid}")
    assert r.status_code == 200
    wf = r.get_json()["workflow"]
    assert wf["current_step"] == "segregate"
    assert wf["completed_count"] == 0

    # Skipping ahead is rejected with 409 OUT_OF_ORDER.
    bad = client.post(f"/disposal/{eid}/steps/treatment/complete")
    assert bad.status_code == 409
    assert bad.get_json()["code"] == "OUT_OF_ORDER"

    # Completing in order advances the workflow.
    ok = client.post(f"/disposal/{eid}/steps/segregate/complete")
    assert ok.status_code == 200
    assert ok.get_json()["workflow"]["completed_count"] == 1

    # Re-completing is 409 ALREADY_COMPLETE.
    dup = client.post(f"/disposal/{eid}/steps/segregate/complete")
    assert dup.status_code == 409
    assert dup.get_json()["code"] == "ALREADY_COMPLETE"


def test_disposal_unknown_step_is_404(client):
    eid = _seed_event()
    r = client.post(f"/disposal/{eid}/steps/ghost/complete")
    assert r.status_code == 404
    assert r.get_json()["code"] == "UNKNOWN_STEP"


# --- Analytics enrichment surfaced over HTTP --------------------------------
def test_analytics_enrichment_keys_present(client):
    r = client.get("/analytics")
    a = r.get_json()["analytics"]
    for key in ("by_waste_type", "by_ward", "by_station", "top_violations",
                "compliance_rate", "violation_rate", "review_rate",
                "has_ward_data", "has_station_data", "data_source"):
        assert key in a
    assert a["data_source"] == "REAL_EVENTS"
