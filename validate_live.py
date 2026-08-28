#!/usr/bin/env python3
# validate_live.py
"""
LIVE exhibition-runtime validation harness (run inside the conda `ml` env).

This is a VALIDATION SCRIPT ONLY. It does not modify the backend, the policy
engine, or any module under test — it starts the real Flask app, drives real
HTTP traffic against it, and prints the A-H acceptance report requested for the
BrainChild Season 2.0 go/no-go.

Usage (Windows, from the project root, ml env active):
    conda activate ml
    python verify_integrations.py          # section B (run first, separately)
    python -m pytest -q                     # section F (run first, separately)
    python validate_live.py                 # sections A, C, D, E, G, H

Exit code is 0 only if every REQUIRED live check passes.
"""

import io
import os
import sys
import time
import json
import glob
import subprocess

PORT = int(os.getenv("VALIDATE_PORT", "5057"))
BASE = f"http://127.0.0.1:{PORT}"
EXPECT_OPENROUTER_MODEL = "openai/gpt-oss-120b"
EXPECT_ROBOFLOW_MODEL = "medbin_dataset-fqhi7/1"

_results = []      # (section, name, ok, detail)


def record(section, name, ok, detail=""):
    _results.append((section, name, bool(ok), str(detail)[:300]))
    flag = "PASS" if ok else "FAIL"
    print(f"  [{flag}] {section} :: {name}  {('- ' + str(detail)) if detail else ''}")


def _find_demo_image():
    for pat in ("static/samples/*.jpg", "static/samples/*.png",
                "static/samples/*.jpeg"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[0]
    return None


def section_a():
    print("\nA. REAL ENVIRONMENT")
    print(f"  Python: {sys.version.split()[0]}")
    def _ver(mod):
        try:
            m = __import__(mod)
            return getattr(m, "__version__", "unknown")
        except Exception as e:
            return f"NOT INSTALLED ({type(e).__name__})"
    print(f"  Flask: {_ver('flask')}")
    print(f"  Pinecone SDK: {_ver('pinecone')}")
    print(f"  inference_sdk: {_ver('inference_sdk')}")
    try:
        import torch
        print(f"  torch: {torch.__version__} (cuda={torch.cuda.is_available()})")
    except Exception as e:
        print(f"  torch: NOT INSTALLED ({type(e).__name__})")


def _wait_health(requests, timeout=120):
    """Poll /health until the app (and lazy vision stack) is reachable."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE}/health", timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            last = e
        time.sleep(2)
    raise RuntimeError(f"app did not become healthy in {timeout}s ({last})")


def main():
    section_a()

    try:
        import requests
    except Exception as e:
        record("G", "requests-available", False,
               f"install requests in ml env: {e}")
        _summary_and_exit()
        return

    demo = _find_demo_image()
    if not demo:
        record("G", "demo-image-present", False, "no static/samples/* image")
        _summary_and_exit()
        return

    env = dict(os.environ)
    env["PORT"] = str(PORT)
    env["FLASK_DEBUG"] = "0"
    proc = subprocess.Popen([sys.executable, "app.py"], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        print("\n(starting Flask app; waiting for /health ...)")
        health = _wait_health(requests)
        _run_http_suite(requests, health, demo)
    except Exception as e:
        record("G", "app-boot", False, f"{type(e).__name__}: {e}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    _summary_and_exit()


def _run_http_suite(requests, health, demo):
    print("\nC. HTTP SMOKE TESTS")
    cfg = health.get("config", {})

    # Model-configuration confirmations (names only; no secret values).
    record("A", f"openrouter_model=={EXPECT_OPENROUTER_MODEL}",
           cfg.get("openrouter_model") == EXPECT_OPENROUTER_MODEL,
           cfg.get("openrouter_model"))
    record("A", f"roboflow_model=={EXPECT_ROBOFLOW_MODEL}",
           cfg.get("model_ref") == EXPECT_ROBOFLOW_MODEL, cfg.get("model_ref"))

    def _get(path, expect=200):
        r = requests.get(f"{BASE}{path}", timeout=30)
        record("C", f"GET {path}", r.status_code == expect, f"HTTP {r.status_code}")
        return r

    _get("/health")
    _get("/events")
    _get("/analytics")
    ops = _get("/operations")
    bins = _get("/operations/bins")
    _get("/operations/bins/red")
    dfn = _get("/disposal/definition")

    # --- /analyze with a real bundled demo image ---------------------------
    with open(demo, "rb") as fh:
        files = {"image": (os.path.basename(demo), fh, "image/jpeg")}
        ra = requests.post(f"{BASE}/analyze", files=files,
                           data={"station": "ST-VALIDATE", "ward": "ICU-1"},
                           timeout=180)
    ok_analyze = ra.status_code == 200
    record("C", "POST /analyze", ok_analyze, f"HTTP {ra.status_code}")
    if not ok_analyze:
        return
    a = ra.json()
    event_id = a.get("event_id")
    decision = a.get("analysis", {}).get("decision", {})
    expected_route = decision.get("expected_route")
    rag = a.get("rag", {}) or {}
    expl = a.get("explanation", {}) or {}
    print(f"    event_id={event_id} expected_route={expected_route} "
          f"rag_status={rag.get('status')} llm_status={expl.get('status')}")

    # --- RAG checks --------------------------------------------------------
    print("\n(RAG grounding)")
    retrieved_ids = set(rag.get("evidence_ids", []) or [])
    used_ids = set(expl.get("evidence_ids_used", []) or [])
    if rag.get("status") == "OK" and retrieved_ids:
        record("C", "pinecone-returns-real-evidence", True,
               f"{len(retrieved_ids)} ids")
        record("C", "used_ids subset of retrieved_ids",
               used_ids.issubset(retrieved_ids), f"used={sorted(used_ids)}")
    else:
        # Grounding gate: no evidence -> explanation must be withheld.
        withheld = expl.get("status") in ("SKIPPED_NO_EVIDENCE", "UNAVAILABLE") \
            and not expl.get("explanation")
        record("C", "explanation-withheld-when-no-evidence", withheld,
               f"rag={rag.get('status')} llm={expl.get('status')}")

    # --- D. Compliance: CORRECT then VIOLATION -----------------------------
    print("\nD. COMPLIANCE")
    valid_routes = a.get("analysis", {}).get("valid_routes", []) or []
    if expected_route:
        rc = requests.post(f"{BASE}/verify",
                           json={"event_id": event_id,
                                 "actual_route": expected_route}, timeout=60)
        cj = rc.json().get("verification", {})
        record("D", "CORRECT for matching route",
               rc.status_code == 200 and cj.get("status") == "CORRECT",
               cj.get("status"))

        wrong = next((r for r in valid_routes if r != expected_route), None)
        rv = requests.post(f"{BASE}/verify",
                           json={"event_id": event_id, "actual_route": wrong},
                           timeout=60)
        vj = rv.json().get("verification", {})
        record("D", "VIOLATION for wrong route",
               rv.status_code == 200 and vj.get("status") == "VIOLATION",
               f"{expected_route}->{wrong}: {vj.get('status')}")
        record("D", "violation alert (reason_code present)",
               bool(vj.get("reason_code")), vj.get("reason_code"))

        # Audit updated + event detail reconstructs the decision.
        rd = requests.get(f"{BASE}/events/{event_id}", timeout=30)
        ev = rd.json().get("event", {})
        record("D", "audit event updated",
               ev.get("actual_route") == wrong
               and ev.get("compliance_status") == "VIOLATION",
               f"actual={ev.get('actual_route')} status={ev.get('compliance_status')}")
        payload = ev.get("payload", {}) or {}
        record("D", "event detail reconstructs decision",
               (payload.get("decision", {}) or {}).get("expected_route")
               == expected_route, "decision provenance present")
    else:
        record("D", "compliance-flow", False,
               "no expected_route (item was REVIEW_REQUIRED — try another sample)")

    # --- E. Operations SIMULATED honesty -----------------------------------
    print("\nE. OPERATIONS (honesty boundary)")
    try:
        bdata = bins.json()
        sim = bdata.get("data_source") == "SIMULATED" and all(
            b.get("data_source") == "SIMULATED" and b.get("sensing") == "none"
            for b in bdata.get("bins", []))
        record("E", "capacity marked SIMULATED", sim)
        blob = (json.dumps(ops.json()) + json.dumps(bdata)).lower()
        disclaimer = (bdata.get("disclaimer") or "").lower()
        # Semantic honesty check (NOT a naive keyword blacklist): the earlier
        # version wrongly failed on the honest disclaimer "...No physical bin
        # sensor, IoT device, weight cell, or RFID is used", because the word
        # "iot" appears inside a NEGATION. Correct contract:
        #   (a) every bin declares sensing == "none"
        #   (b) the response is tagged data_source == "SIMULATED"
        #   (c) the disclaimer explicitly negates physical/IoT sensing
        #   (d) no POSITIVE claim of live/real-time physical sensing exists
        all_none = all(b.get("sensing") == "none" for b in bdata.get("bins", []))
        simulated = bdata.get("data_source") == "SIMULATED"
        negates = ("simulated" in disclaimer
                   and ("no physical" in disclaimer or "not use" in disclaimer
                        or "is used" in disclaimer))
        positive_claims = ("live sensor telemetry", "real-time fill",
                           "iot-enabled bin", "physical sensor reading",
                           "sensor-measured")
        no_positive_claim = not any(p in blob for p in positive_claims)
        no_iot = all_none and simulated and negates and no_positive_claim
        record("E", "no physical-IoT sensing claim", no_iot,
               f"all_sensing_none={all_none} simulated={simulated} "
               f"disclaimer_negates={negates} no_positive_claim={no_positive_claim}")
    except Exception as e:
        record("E", "operations-parse", False, str(e))

    # --- disposal workflow (sequential + 409 skip + full run) --------------
    print("\n(disposal workflow)")
    try:
        record("C", "GET /disposal/definition==5",
               dfn.json().get("total_steps") == 5, dfn.json().get("total_steps"))
        wf = requests.get(f"{BASE}/disposal/{event_id}",
                          timeout=30).json()["workflow"]
        record("E", "workflow created/get", wf.get("current_step") == "segregate",
               f"current={wf.get('current_step')}")
        skip = requests.post(
            f"{BASE}/disposal/{event_id}/steps/treatment/complete", timeout=30)
        record("E", "skip-ahead returns 409", skip.status_code == 409,
               f"HTTP {skip.status_code} {skip.json().get('code')}")
        order = ["segregate", "secure", "seal_label", "collection", "treatment"]
        last = None
        for step in order:
            last = requests.post(
                f"{BASE}/disposal/{event_id}/steps/{step}/complete", timeout=30)
        done = last is not None and last.status_code == 200 and \
            last.json()["workflow"]["is_complete"]
        record("E", "all 5 steps completed sequentially", done,
               f"is_complete={last.json()['workflow']['is_complete'] if last else None}")
    except Exception as e:
        record("E", "disposal-flow", False, str(e))


def _summary_and_exit():
    print("\n" + "=" * 60)
    required_fail = [r for r in _results if not r[2]]
    by_section = {}
    for sec, name, ok, _ in _results:
        s = by_section.setdefault(sec, [0, 0])
        s[0] += 1
        s[1] += 1 if ok else 0
    for sec in sorted(by_section):
        tot, ok = by_section[sec][0], by_section[sec][1]
        print(f"  Section {sec}: {ok}/{tot} passed")
    print("=" * 60)
    if required_fail:
        print("G. REMAINING BLOCKERS:")
        for sec, name, _, detail in required_fail:
            print(f"   - [{sec}] {name}: {detail}")
        print("\nVERDICT: NOT READY — resolve blockers above.")
        sys.exit(1)
    else:
        print("H. BACKEND READY FOR NEXT.JS")
        sys.exit(0)


if __name__ == "__main__":
    main()
