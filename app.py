# app.py
"""
MediWaste AI — Flask backend.

Orchestrates the deterministic core (vision -> normalization -> policy ->
compliance) and the best-effort augmentation layers (Pinecone RAG + OpenRouter
explanation), then records an auditable event.

Failure isolation is a first-class requirement: if Pinecone or OpenRouter is
down, /analyze and /verify still return the vision + policy + compliance result.
The app never logs or returns secrets.

Endpoints
---------
GET  /                     Staff UI
POST /analyze              Detect + decide + (RAG + LLM) + create audit event
POST /verify               Compare expected vs actual route, update event
GET  /events               Recent audit events
GET  /events/<event_id>    Single event detail
GET  /analytics            Aggregate compliance analytics
GET  /health               Subsystem status (no secrets)
GET  /uploads/<filename>   Serve an uploaded image (for event detail view)
"""

import os
import time
import uuid

from flask import (
    Flask, request, jsonify, render_template,
    send_from_directory, abort,
)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from dotenv import load_dotenv

import policy_engine
import rag_engine
import llm_client
import audit_store

load_dotenv()

# --- Config ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
TOP_K = int(os.getenv("RAG_TOP_K", "8"))

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# --- Lazy, cached heavy modules (CLIP + Roboflow) ---------------------------
# Imported on first use so the server can start (and serve /health, the UI, and
# audit/analytics endpoints) even before the vision stack is warm. They cache
# their own models/clients internally, so this never reloads per request.
_vision = {}


def _get_vision():
    if "ctx" not in _vision:
        import visual_context
        import mediwaste_pipeline
        _vision["ctx"] = visual_context
        _vision["pipe"] = mediwaste_pipeline
    return _vision["ctx"], _vision["pipe"]


# --- Helpers -----------------------------------------------------------------
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def _valid_image(path):
    """Confirm the saved file is a real, decodable image (defence in depth)."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False


def _route_meta_map():
    return {code: policy_engine.route_meta(code) for code in policy_engine.STREAMS}


def _build_audit_from_analysis(analysis, image_filename, image_id, station,
                               rag_result, llm_result):
    primary = analysis.get("primary") or {}
    decision = analysis.get("decision") or {}
    detections = analysis.get("detections") or []
    verification = policy_engine.verify_compliance(
        decision.get("expected_route"), None
    )
    return {
        "image_filename": image_filename,
        "image_id": image_id,
        "station": station or None,
        "detected_items": [d.get("item") for d in detections],
        "raw_labels": [d.get("raw_class") for d in detections],
        "confidence": primary.get("confidence"),
        "visual_context": analysis.get("context"),
        "canonical_category": decision.get("waste_type"),
        "expected_route": decision.get("expected_route"),
        "actual_route": None,
        "compliance_status": verification["status"],
        "reason_code": verification.get("reason_code"),
        "rule_id": decision.get("rule_id"),
        "policy_version": decision.get("policy_version"),
        "model_id": analysis.get("model_id"),
        "model_version": analysis.get("model_version"),
        "evidence_ids": (rag_result or {}).get("evidence_ids", []),
        "rag_status": (rag_result or {}).get("status"),
        "llm_status": (llm_result or {}).get("status"),
        "payload": {
            "decision": decision,
            "primary": primary,
            "detections": detections,
            "mixed_waste": analysis.get("mixed_waste"),
            "context": analysis.get("context"),
            "rag": rag_result,
            "explanation": llm_result,
            "verification": verification,
        },
    }


# --- Routes ------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    safe = secure_filename(filename)
    if not safe:
        abort(404)
    return send_from_directory(app.config["UPLOAD_FOLDER"], safe)


@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"status": "error", "error": "No image provided."}), 400
    image = request.files["image"]
    if not image or image.filename == "":
        return jsonify({"status": "error", "error": "Empty filename."}), 400
    if not allowed_file(image.filename):
        return jsonify({
            "status": "error",
            "error": "Unsupported file type. Allowed: jpg, jpeg, png.",
        }), 400

    station = (request.form.get("station") or "").strip() or None

    # Save with a unique, secure name (never overwrite; never trust input name).
    ext = image.filename.rsplit(".", 1)[1].lower()
    image_id = uuid.uuid4().hex
    stored_name = f"{image_id}_{secure_filename(image.filename)}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
    image.save(path)

    if not _valid_image(path):
        try:
            os.remove(path)
        except OSError:
            pass
        return jsonify({"status": "error", "error": "File is not a valid image."}), 400

    t_total = time.perf_counter()

    # --- Vision + policy (core; must succeed) --------------------------------
    try:
        visual_context, pipeline = _get_vision()
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": f"Vision stack unavailable: {type(e).__name__}",
        }), 503

    try:
        t0 = time.perf_counter()
        context = visual_context.predict_visual_context(path)
        context_ms = round((time.perf_counter() - t0) * 1000, 1)

        analysis = pipeline.analyze_image(path, context)
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": f"Analysis failed: {type(e).__name__}: {str(e)[:200]}",
        }), 500

    decision = analysis.get("decision") or {}
    primary_item = (analysis.get("primary") or {}).get("item")

    # --- RAG evidence (best-effort) ------------------------------------------
    t0 = time.perf_counter()
    try:
        rag_result = rag_engine.retrieve_evidence(
            primary_item, context, decision, compliance=None, top_k=TOP_K
        )
    except Exception as e:  # never let RAG break analyze
        rag_result = {"status": "UNAVAILABLE", "evidence": [], "evidence_ids": [],
                      "error": f"{type(e).__name__}", "query": None}
    retrieval_ms = round((time.perf_counter() - t0) * 1000, 1)

    # --- LLM explanation (best-effort) ---------------------------------------
    t0 = time.perf_counter()
    try:
        llm_result = llm_client.generate_explanation(
            decision, rag_result.get("evidence", []), context=context,
            rag_status=rag_result.get("status"),
        )
    except Exception as e:
        llm_result = {"status": "UNAVAILABLE", "explanation": None,
                      "why_route": None, "guidance": [], "evidence_ids_used": [],
                      "limitations": f"{type(e).__name__}"}
    llm_ms = round((time.perf_counter() - t0) * 1000, 1)

    # --- Audit event (PENDING verification) ----------------------------------
    audit_event = audit_store.create_event(
        _build_audit_from_analysis(
            analysis, stored_name, image_id, station, rag_result, llm_result
        )
    )

    total_ms = round((time.perf_counter() - t_total) * 1000, 1)
    verification = policy_engine.verify_compliance(decision.get("expected_route"), None)

    return jsonify({
        "status": "ok",
        "event_id": audit_event["event_id"],
        "image_url": f"/uploads/{stored_name}",
        "analysis": {
            "detections": analysis.get("detections"),
            "primary": analysis.get("primary"),
            "decision": decision,
            "context": context,
            "mixed_waste": analysis.get("mixed_waste"),
            "verification": verification,
            "model": {
                "id": analysis.get("model_id"),
                "version": analysis.get("model_version"),
                "ref": analysis.get("model_ref"),
            },
            "valid_routes": policy_engine.valid_routes(),
            "route_meta": _route_meta_map(),
        },
        "rag": rag_result,
        "explanation": llm_result,
        "audit_event": audit_event,
        "timings": {
            "context_ms": context_ms,
            "inference_ms": analysis.get("timings", {}).get("inference_ms"),
            "retrieval_ms": retrieval_ms,
            "llm_ms": llm_ms,
            "total_ms": total_ms,
        },
    })


@app.route("/verify", methods=["POST"])
def verify():
    data = request.get_json(silent=True) or {}
    event_id = data.get("event_id")
    actual_route = (data.get("actual_route") or "").strip().upper() or None
    station = (data.get("station") or "").strip() or None

    if not event_id:
        return jsonify({"status": "error", "error": "event_id is required."}), 400

    event = audit_store.get_event(event_id)
    if not event:
        return jsonify({"status": "error", "error": "Event not found."}), 404

    payload = event.get("payload") or {}
    decision = payload.get("decision") or {}
    context = payload.get("context") or event.get("visual_context") or {}
    expected_route = decision.get("expected_route") or event.get("expected_route")
    primary_item = (payload.get("primary") or {}).get("item") \
        or (event.get("detected_items") or [None])[0]

    verification = policy_engine.verify_compliance(expected_route, actual_route)

    # Refresh evidence + explanation with the compliance context (best-effort).
    rag_result = payload.get("rag") or {"status": "UNAVAILABLE", "evidence": [],
                                        "evidence_ids": []}
    if verification["status"] in ("CORRECT", "VIOLATION"):
        try:
            rag_result = rag_engine.retrieve_evidence(
                primary_item, context, decision, compliance=verification,
                actual_route=actual_route, top_k=TOP_K,
            )
        except Exception:
            pass  # keep prior evidence

    try:
        llm_result = llm_client.generate_explanation(
            decision, rag_result.get("evidence", []),
            context=context, compliance=verification,
            rag_status=rag_result.get("status"),
        )
    except Exception as e:
        llm_result = {"status": "UNAVAILABLE", "explanation": None,
                      "why_route": None, "guidance": [], "evidence_ids_used": [],
                      "limitations": f"{type(e).__name__}"}

    # Persist the verification outcome onto the event.
    new_payload = dict(payload)
    new_payload["verification"] = verification
    new_payload["rag"] = rag_result
    new_payload["explanation"] = llm_result

    updated = audit_store.update_event(
        event_id,
        actual_route=actual_route,
        compliance_status=verification["status"],
        reason_code=verification.get("reason_code"),
        station=station or event.get("station"),
        evidence_ids=rag_result.get("evidence_ids", []),
        rag_status=rag_result.get("status"),
        llm_status=llm_result.get("status"),
        payload=new_payload,
    )

    return jsonify({
        "status": "ok",
        "event_id": event_id,
        "verification": verification,
        "rag": rag_result,
        "explanation": llm_result,
        "audit_event": updated,
    })


@app.route("/events")
def events():
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))
    return jsonify({
        "status": "ok",
        "count": audit_store.count_events(),
        "events": audit_store.list_events(limit=limit, offset=offset),
    })


@app.route("/events/<event_id>")
def event_detail(event_id):
    event = audit_store.get_event(event_id)
    if not event:
        return jsonify({"status": "error", "error": "Event not found."}), 404
    return jsonify({"status": "ok", "event": event})


@app.route("/analytics")
def analytics():
    return jsonify({"status": "ok", "analytics": audit_store.analytics()})


@app.route("/policy")
def policy():
    """Public policy metadata so the UI colour guide and the actual-route
    selector are derived from the single source of truth (no secrets)."""
    return jsonify({
        "status": "ok",
        "policy_version": policy_engine.POLICY_VERSION,
        "facility_profile": policy_engine.FACILITY_PROFILE,
        "accept_threshold": policy_engine.ACCEPT_THRESHOLD,
        "review_floor": policy_engine.REVIEW_FLOOR,
        "valid_routes": policy_engine.valid_routes(),
        "route_meta": _route_meta_map(),
    })


@app.route("/health")
def health():
    """Subsystem readiness — safe to expose (no secrets, no key values)."""
    return jsonify({
        "status": "ok",
        "policy_version": policy_engine.POLICY_VERSION,
        "config": {
            "roboflow_configured": bool(os.getenv("ROBOFLOW_API_KEY")),
            "pinecone_configured": bool(os.getenv("PINECONE_API_KEY")),
            "openrouter_configured": llm_client.is_configured(),
            "model_ref": os.getenv("MODEL_ID"),
            "pinecone_index": os.getenv("PINECONE_INDEX_NAME"),
            "openrouter_model": os.getenv("OPENROUTER_MODEL"),
        },
        "audit_events": audit_store.count_events(),
    })


@app.errorhandler(RequestEntityTooLarge)
def too_large(_e):
    return jsonify({
        "status": "error",
        "error": f"File too large (max {MAX_CONTENT_LENGTH // (1024*1024)} MB).",
    }), 413


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))
