# mediwaste_pipeline.py
"""
Vision + normalization + policy orchestration.

Responsibilities:
    1. Run Roboflow MedBin object detection on an image.
    2. Normalize raw classes to canonical items (waste_ontology).
    3. Ask the deterministic policy_engine for the expected route.
    4. Surface uncertainty (low confidence / unknown class) as REVIEW_REQUIRED.
    5. Flag mixed-waste scenes.

This module NEVER decides a route itself — every decision comes from
policy_engine.policy_decision(). The Roboflow client is created lazily and
cached, so importing this module does not require the inference SDK or a
network connection (this keeps the deterministic core unit-testable offline).
"""

import os
import time

from dotenv import load_dotenv

from waste_ontology import normalize_class
import policy_engine

load_dotenv()

# --- Model configuration -----------------------------------------------------
MODEL_REF = os.getenv("MODEL_ID", "medbin_dataset-fqhi7/1").strip()
ROBOFLOW_API_URL = os.getenv("ROBOFLOW_API_URL", "https://serverless.roboflow.com")

if "/" in MODEL_REF:
    MODEL_ID, MODEL_VERSION = MODEL_REF.rsplit("/", 1)
else:
    MODEL_ID, MODEL_VERSION = MODEL_REF, ""

# Detections below this floor are treated as noise and dropped entirely.
REVIEW_FLOOR = policy_engine.REVIEW_FLOOR

# --- Lazy, cached Roboflow client -------------------------------------------
_client = None


def get_client():
    """Create (once) and return the Roboflow inference client."""
    global _client
    if _client is None:
        from inference_sdk import InferenceHTTPClient  # lazy import
        api_key = os.getenv("ROBOFLOW_API_KEY")
        if not api_key:
            raise RuntimeError("ROBOFLOW_API_KEY is not configured.")
        _client = InferenceHTTPClient(api_url=ROBOFLOW_API_URL, api_key=api_key)
    return _client


def detect(image_path):
    """Run MedBin inference and return the raw prediction list."""
    response = get_client().infer(image_path, model_id=MODEL_REF)
    if isinstance(response, dict):
        return response.get("predictions", []) or []
    return []


# --- Pure analysis core (no network; unit-testable) --------------------------
def _bbox(pred):
    keys = ("x", "y", "width", "height")
    if all(k in pred for k in keys):
        return {k: pred[k] for k in keys}
    return None


def analyze_predictions(predictions, context=None):
    """
    Turn raw Roboflow predictions into a structured analysis using the
    deterministic policy engine. Pure function — safe to unit test.
    """
    context = context or {}
    detections = []

    for pred in predictions or []:
        confidence = float(pred.get("confidence", 0) or 0)
        if confidence < REVIEW_FLOOR:
            continue  # noise
        raw_class = pred.get("class", "") or ""
        item = normalize_class(raw_class)
        decision = policy_engine.policy_decision(item, context, confidence)
        detections.append({
            "raw_class": raw_class,
            "item": item,
            "confidence": round(confidence, 3),
            "bbox": _bbox(pred),
            "decision": decision,
        })

    # Rank by confidence (highest first).
    detections.sort(key=lambda d: d["confidence"], reverse=True)

    # Primary = highest-confidence DECIDED detection; else highest overall;
    # else a synthetic NO_DETECTION review.
    primary = None
    for d in detections:
        if d["decision"]["status"] == "DECIDED":
            primary = d
            break
    if primary is None and detections:
        primary = detections[0]

    if primary is not None:
        overall_decision = primary["decision"]
    else:
        overall_decision = policy_engine.review("NO_DETECTION")

    # Mixed-waste detection: >1 distinct DECIDED waste stream in the scene.
    decided_streams = {
        d["decision"]["required_stream"]
        for d in detections
        if d["decision"]["status"] == "DECIDED"
    }
    decided_types = sorted({
        d["decision"]["waste_type"]
        for d in detections
        if d["decision"]["status"] == "DECIDED"
    })
    mixed = {
        "is_mixed": len(decided_streams) > 1,
        "waste_types": decided_types,
        "streams": sorted(s for s in decided_streams if s),
    }

    return {
        "model_ref": MODEL_REF,
        "model_id": MODEL_ID,
        "model_version": MODEL_VERSION,
        "raw_prediction_count": len(predictions or []),
        "objects_detected": len(detections),
        "detections": detections,
        "primary": primary,
        "decision": overall_decision,
        "mixed_waste": mixed,
        "context": context,
    }


def analyze_image(image_path, context=None):
    """
    Full pipeline for one image: Roboflow inference + deterministic analysis.
    Returns the structured analysis plus an inference latency measurement.
    """
    t0 = time.perf_counter()
    predictions = detect(image_path)
    inference_ms = round((time.perf_counter() - t0) * 1000, 1)

    analysis = analyze_predictions(predictions, context)
    analysis["timings"] = {"inference_ms": inference_ms}
    return analysis
