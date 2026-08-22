#!/usr/bin/env python3
# verify_integrations.py
"""
Live integration diagnostics for MediWaste AI.

Runs OUTSIDE the request path so an operator can confirm that Roboflow,
Pinecone, and OpenRouter are reachable and correctly configured before a demo.

Security: this script never prints, logs, or returns secret values. It reports
only booleans ("configured": true/false) and non-secret metadata (index
dimension, embedding model, namespaces, HTTP status, latency). Every check is
isolated in try/except so one failing subsystem cannot mask the others.

Usage:
    python verify_integrations.py
Exit code is 0 if the deterministic core is healthy (integrations may still be
reported as unavailable); it is non-zero only if the core itself fails.
"""

import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

LINE = "-" * 66


def _ok(msg):   print(f"  ✓ {msg}")
def _bad(msg):  print(f"  ✗ {msg}")
def _info(msg): print(f"    {msg}")
def _head(msg): print(f"\n{LINE}\n{msg}\n{LINE}")


def check_config():
    _head("1. CONFIG (booleans only — no secret values printed)")
    flags = {
        "ROBOFLOW_API_KEY": bool(os.getenv("ROBOFLOW_API_KEY")),
        "MODEL_ID": bool(os.getenv("MODEL_ID")),
        "PINECONE_API_KEY": bool(os.getenv("PINECONE_API_KEY")),
        "PINECONE_INDEX_NAME": bool(os.getenv("PINECONE_INDEX_NAME")),
        "OPENROUTER_API_KEY": bool(os.getenv("OPENROUTER_API_KEY")),
        "OPENROUTER_MODEL": bool(os.getenv("OPENROUTER_MODEL")),
    }
    for k, v in flags.items():
        (_ok if v else _bad)(f"{k}: {'configured' if v else 'MISSING'}")
    # Non-secret references are safe to echo.
    _info(f"model_ref = {os.getenv('MODEL_ID')}")
    _info(f"pinecone_index = {os.getenv('PINECONE_INDEX_NAME')}")
    _info(f"openrouter_model = {os.getenv('OPENROUTER_MODEL')}")
    return all(flags.values())


def check_core():
    _head("2. DETERMINISTIC CORE (offline; must always pass)")
    try:
        import policy_engine
        from waste_ontology import normalize_class

        # Known item -> route.
        d1 = policy_engine.policy_decision("SHARPS", {}, 0.95)
        assert d1["status"] == "DECIDED" and d1["expected_route"] == "RED", d1
        _ok(f"SHARPS -> {d1['expected_route']} ({d1['rule_id']})")

        # Unknown item -> review, null route.
        d2 = policy_engine.policy_decision(normalize_class("zzz-not-a-class"), {}, 0.99)
        assert d2["status"] == "REVIEW_REQUIRED" and d2["expected_route"] is None, d2
        _ok(f"unknown class -> REVIEW_REQUIRED ({d2['reason']})")

        # Low confidence -> review.
        d3 = policy_engine.policy_decision("SHARPS", {}, 0.10)
        assert d3["status"] == "REVIEW_REQUIRED", d3
        _ok(f"low confidence -> REVIEW_REQUIRED ({d3['reason']})")

        # Verification.
        v_ok = policy_engine.verify_compliance("RED", "RED")
        v_bad = policy_engine.verify_compliance("RED", "BLACK")
        assert v_ok["status"] == "CORRECT" and v_bad["status"] == "VIOLATION"
        _ok(f"verify CORRECT / VIOLATION ({v_bad['reason_code']})")
        return True
    except Exception as e:
        _bad(f"core check failed: {type(e).__name__}: {str(e)[:160]}")
        return False


def check_grounding_gate():
    _head("3. GROUNDING GATE (LLM must NOT explain without evidence — offline)")
    try:
        import llm_client
        decision = {"status": "DECIDED", "waste_type": "SHARPS",
                    "expected_route": "RED", "rule_id": "R-SHARPS",
                    "policy_version": "1.1.0"}
        # Empty evidence must be refused BEFORE any network call, and must hold
        # whether or not OPENROUTER_API_KEY is configured.
        out = llm_client.generate_explanation(decision, [], context={})
        assert out["status"] == "SKIPPED_NO_EVIDENCE", \
            f"expected SKIPPED_NO_EVIDENCE, got {out.get('status')}"
        assert out["explanation"] is None, "explanation must be null with no evidence"
        assert out["guidance"] == [] and out["evidence_ids_used"] == [], out
        _ok("no evidence -> status=SKIPPED_NO_EVIDENCE, explanation=null (no fabrication)")
        # Sanity: WITH evidence + no key it degrades to UNAVAILABLE, not a fake.
        ev = [{"evidence_id": "x1", "text": "sharps -> red container", "source": "d"}]
        saved = llm_client.OPENROUTER_API_KEY
        try:
            llm_client.OPENROUTER_API_KEY = None
            out2 = llm_client.generate_explanation(decision, ev, context={})
            assert out2["status"] == "UNAVAILABLE", out2.get("status")
        finally:
            llm_client.OPENROUTER_API_KEY = saved
        _ok("with evidence but no key -> UNAVAILABLE (still no fabrication)")
        return True
    except AssertionError as e:
        _bad(f"GATE NOT ENFORCED: {e}")
        return False
    except Exception as e:
        _bad(f"gate check failed: {type(e).__name__}: {str(e)[:160]}")
        return False


def check_pinecone():
    _head("4. PINECONE (inspect existing index + one real query)")
    if not os.getenv("PINECONE_API_KEY"):
        _bad("PINECONE_API_KEY not configured — skipping (RAG will degrade).")
        return None
    try:
        import pinecone_retriever
        import rag_engine
    except Exception as e:
        _bad(f"import failed: {type(e).__name__}: {str(e)[:160]}")
        return False
    try:
        meta = pinecone_retriever.inspect_index(refresh=True)
        _ok(f"index '{meta.get('name')}' reachable (ready={meta.get('ready')}, "
            f"state={meta.get('state')})")
        _info(f"sdk_version={meta.get('sdk_version')} "
              f"dimension={meta.get('dimension')} metric={meta.get('metric')} "
              f"vector_type={meta.get('vector_type')}")
        _info(f"embed_model={meta.get('embed_model')} text_field={meta.get('text_field')}")
        _info(f"namespaces={meta.get('namespaces')} "
              f"total_vectors={meta.get('total_vector_count')}")
    except Exception as e:
        _bad(f"inspect_index failed: {type(e).__name__}: {str(e)[:160]}")
        return False

    # One real retrieval through the deterministic query builder.
    try:
        decision = {"waste_type": "SHARPS", "expected_route": "RED"}
        res = rag_engine.retrieve_evidence("SHARPS", {}, decision, top_k=5)
        _ok(f"retrieve status={res['status']} "
            f"retrieved={res.get('retrieved_count')} "
            f"retained={len(res['evidence'])} latency={res['latency_ms']}ms")
        if res["evidence"]:
            e0 = res["evidence"][0]
            _info(f"top id={e0.get('evidence_id')} score={e0.get('score')} "
                  f"relevance={e0.get('relevance')} has_text={bool(e0.get('text'))}")
            return True
        if res["status"] == "INSUFFICIENT_EVIDENCE":
            # Pinecone IS reachable and returned hits; the relevance gate simply
            # found none on-topic for SHARPS. Not a connectivity failure.
            _info(f"Pinecone reachable: {res.get('retrieved_count')} hit(s) "
                  "retrieved but none passed the relevance gate for SHARPS "
                  "(status=INSUFFICIENT_EVIDENCE; no fabricated evidence).")
            return True
        # ZERO results: do NOT fake a fallback. Diagnose honestly so the
        # operator can tell an empty/mismatched index from an over-narrow query.
        _bad("retrieval returned ZERO records — diagnosing (no fabricated evidence):")
        _info(f"namespace queried = '{pinecone_retriever.NAMESPACE}'  "
              f"index namespaces = {meta.get('namespaces')}")
        _info(f"total_vectors in index = {meta.get('total_vector_count')}")
        try:
            probe = pinecone_retriever.retrieve("biomedical waste disposal", top_k=3)
            _info(f"broad probe query hits = {len(probe)} "
                  f"(if 0 with vectors present -> namespace/text-field mismatch)")
        except Exception as pe:
            _info(f"broad probe failed: {type(pe).__name__}: {str(pe)[:120]}")
        _info("ACTION: confirm PINECONE_NAMESPACE matches where records were "
              "upserted, and that the index actually contains vectors.")
        return False
    except Exception as e:
        _bad(f"retrieve failed: {type(e).__name__}: {str(e)[:160]}")
        return False


def check_openrouter():
    _head("5. OPENROUTER (explanation layer — final content only)")
    try:
        import llm_client
    except Exception as e:
        _bad(f"import failed: {type(e).__name__}: {str(e)[:160]}")
        return False
    if not llm_client.is_configured():
        _bad("OPENROUTER_API_KEY not configured — skipping (explanations degrade).")
        return None
    try:
        decision = {"status": "DECIDED", "waste_type": "SHARPS",
                    "expected_route": "RED", "rule_id": "R-SHARPS",
                    "policy_version": "1.1.0"}
        evidence = [{"evidence_id": "demo-1",
                     "text": "Sharps such as needles must be placed in a "
                             "puncture-proof red sharps container.",
                     "source": "diagnostic", "page": 1, "section": "Sharps"}]
        t0 = time.perf_counter()
        out = llm_client.generate_explanation(decision, evidence, context={})
        dt = round((time.perf_counter() - t0) * 1000, 1)
        _ok(f"status={out['status']} model={out.get('model')} latency={dt}ms")
        if out["status"] == "OK":
            _info(f"explanation present={bool(out.get('explanation'))} "
                  f"why_route present={bool(out.get('why_route'))} "
                  f"guidance={len(out.get('guidance') or [])}")
            _info(f"evidence_ids_used={out.get('evidence_ids_used')} "
                  "(must be a subset of provided ids)")
            assert set(out.get("evidence_ids_used") or []).issubset({"demo-1"}), \
                "LLM referenced an evidence id that was never provided!"
            _ok("no hallucinated evidence ids")
        else:
            _info(f"limitations: {str(out.get('limitations'))[:160]}")
        return out["status"] == "OK"
    except Exception as e:
        _bad(f"generate_explanation failed: {type(e).__name__}: {str(e)[:160]}")
        return False


def _first_sample():
    for cand in ("static/samples/sample1.jpg", "static/samples/sample2.jpg",
                 "static/samples/sample3.jpg"):
        if os.path.exists(cand):
            return cand
    return None


def check_roboflow():
    _head("6. ROBOFLOW (optional live inference on a bundled sample)")
    if not os.getenv("ROBOFLOW_API_KEY"):
        _bad("ROBOFLOW_API_KEY not configured — skipping.")
        return None
    sample = _first_sample()
    if not sample:
        _info("no bundled sample image found — skipping live inference.")
        return None
    try:
        import mediwaste_pipeline as mp
        preds = mp.detect(sample)
        _ok(f"inference OK on {sample}: {len(preds)} raw prediction(s)")
        analysis = mp.analyze_predictions(preds, {})
        _info(f"objects_detected={analysis['objects_detected']} "
              f"primary_item={(analysis.get('primary') or {}).get('item')} "
              f"decision={analysis['decision']['status']}")
        return True
    except Exception as e:
        _bad(f"inference failed: {type(e).__name__}: {str(e)[:160]}")
        return False


def check_end_to_end():
    _head("7. END-TO-END (real sample: detect -> decide -> retrieve -> gate -> explain)")
    sample = _first_sample()
    if not sample:
        _info("no bundled sample image — skipping E2E.")
        return None
    try:
        import visual_context
        import mediwaste_pipeline as mp
        import rag_engine
        import llm_client
    except Exception as e:
        _bad(f"vision stack not importable here: {type(e).__name__}: "
             f"{str(e)[:120]} — run this in the conda 'ml' env.")
        return None
    try:
        ctx = visual_context.predict_visual_context(sample)
        analysis = mp.analyze_image(sample, ctx)
        decision = analysis.get("decision") or {}
        item = (analysis.get("primary") or {}).get("item")
        _ok(f"detect+decide: item={item} status={decision.get('status')} "
            f"route={decision.get('expected_route')}")
        rag = rag_engine.retrieve_evidence(item, ctx, decision, top_k=5)
        _ok(f"retrieve: status={rag['status']} "
            f"retrieved={rag.get('retrieved_count')} "
            f"retained={len(rag['evidence'])}")
        exp = llm_client.generate_explanation(
            decision, rag.get("evidence", []), context=ctx,
            rag_status=rag.get("status"),
        )
        # The critical invariant, verified on a REAL end-to-end run:
        if not rag.get("evidence"):
            assert exp["status"] == "SKIPPED_NO_EVIDENCE" and not exp["explanation"], \
                f"GATE VIOLATION: prose produced without evidence (status={exp['status']})"
            _ok(f"grounding gate HELD live: no relevant evidence -> LLM "
                f"{exp['status']} (no prose)")
        else:
            assert set(exp.get("evidence_ids_used") or []).issubset(
                set(rag.get("evidence_ids") or [])), "LLM cited an unsupplied id"
            _ok(f"explain: status={exp['status']} grounded_ids={exp.get('evidence_ids_used')}")
        return True
    except AssertionError as e:
        _bad(f"E2E invariant failed: {e}")
        return False
    except Exception as e:
        _bad(f"E2E failed: {type(e).__name__}: {str(e)[:160]}")
        return False


def main():
    print("MediWaste AI — integration diagnostics")
    print("(secrets are never printed; only booleans + non-secret metadata)")
    check_config()
    core = check_core()
    gate = check_grounding_gate()
    results = {
        "pinecone": check_pinecone(),
        "openrouter": check_openrouter(),
        "roboflow": check_roboflow(),
        "end_to_end": check_end_to_end(),
    }

    _head("SUMMARY")
    _info(f"core: {'PASS' if core else 'FAIL'}")
    _info(f"grounding_gate: {'PASS' if gate else 'FAIL'}")
    for name, r in results.items():
        label = "PASS" if r is True else ("SKIP/UNAVAILABLE" if r is None else "FAIL")
        _info(f"{name}: {label}")
    print()
    print("Note: Pinecone/OpenRouter/Roboflow reporting SKIP or FAIL does NOT "
          "break the app — the deterministic core degrades gracefully. The "
          "deterministic core AND the grounding gate, however, must both PASS.")
    # The core and the architectural grounding gate are the only fatal checks.
    sys.exit(0 if (core and gate) else 1)


if __name__ == "__main__":
    main()
