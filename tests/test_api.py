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
