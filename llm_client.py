# llm_client.py
"""
OpenRouter explanation layer (model: openai/gpt-oss-120b).

STRICT boundary: the LLM only *explains* a decision that was already made by
the deterministic policy engine and supported by retrieved evidence. It never
decides the waste category, the expected route, the actual route, or the
compliance status, and it must not invent sources or medical procedures.

Only the final assistant message content is used; any chain-of-thought /
reasoning field is ignored and never surfaced. All failures degrade to a
structured "UNAVAILABLE" result so the core pipeline keeps working.
"""

import os
import json
import time
import re

import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b").strip()
OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
).strip().rstrip("/")

_TIMEOUT = float(os.getenv("OPENROUTER_TIMEOUT", "60"))

SYSTEM_PROMPT = (
    "You are MediWaste AI's explanation assistant for hospital staff.\n"
    "Follow these rules strictly:\n"
    "1. The deterministic policy engine is AUTHORITATIVE for the waste "
    "category, the expected disposal route, the actual route, and the "
    "compliance status. Never contradict or override them.\n"
    "2. The retrieved evidence passages are your ONLY source of factual "
    "support. Do not use outside knowledge as if it were policy.\n"
    "3. Never invent sources, citations, document names, page numbers, "
    "regulations, standards, WHO claims, or hospital SOP claims.\n"
    "4. Never invent procedures of any kind — medical, cleaning, "
    "sterilization, reuse, reprocessing, emergency, spill, or disposal "
    "procedures — unless they appear verbatim in the provided evidence.\n"
    "5. Every factual statement in 'explanation', 'why_route', and 'guidance' "
    "must be traceable to a provided evidence passage. If it is not supported "
    "by the evidence, do NOT state it — move the gap to 'limitations'.\n"
    "6. Never change the expected route. Only explain it.\n"
    "7. If the evidence is insufficient to justify a point, say so explicitly "
    "in 'limitations' rather than guessing.\n"
    "8. Keep the explanation concise and practical for busy clinical staff.\n"
    "9. Clearly explain WHY the expected route is required for this item, "
    "grounded in the evidence.\n"
    "10. For a VIOLATION, clearly explain why the actual route is unsafe or "
    "non-compliant, grounded in the evidence.\n"
    "11. 'guidance' must contain only concrete, evidence-supported actions. If "
    "no evidence supports a specific action, return an empty guidance array.\n"
    "Return ONLY a single minified JSON object with keys: explanation "
    "(string), why_route (string), guidance (array of strings), "
    "evidence_ids_used (array of the evidence ids you actually relied on), "
    "limitations (string). Do not include any text outside the JSON. Do not "
    "reveal your reasoning steps."
)

# Returned verbatim when the grounding gate blocks generation because RAG
# retrieved NOTHING at all (Pinecone unavailable / zero hits / no citable ids).
# This is NOT a factual regulatory explanation — it is a safe status message.
NO_EVIDENCE_MESSAGE = (
    "Evidence-grounded explanation is temporarily unavailable. The route shown "
    "was determined by the deterministic policy engine."
)

# Returned verbatim when Pinecone DID return hits but none survived the
# relevance-quality gate (rag.status == "INSUFFICIENT_EVIDENCE"). Distinct from
# NO_EVIDENCE_MESSAGE so the UI can show a visibly different "insufficient" state.
INSUFFICIENT_EVIDENCE_MESSAGE = (
    "Evidence coverage is insufficient for an evidence-grounded explanation. "
    "The route shown was determined by the deterministic facility policy."
)


def is_configured():
    return bool(OPENROUTER_API_KEY)


def _headers():
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "MediWaste AI",
    }


def _chat(messages, temperature=0.2, max_tokens=800):
    """
    Low-level chat call. Returns the final assistant message content string.
    Raises RuntimeError with a safe (no-secret) message on failure.
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured.")

    url = f"{OPENROUTER_BASE_URL}/chat/completions"
    base_body = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # First try with extras that reduce cost/latency and suppress reasoning in
    # the response; retry without them if the endpoint rejects unknown fields.
    bodies = [
        dict(base_body, reasoning={"effort": "low", "exclude": True}),
        base_body,
    ]

    last_err = None
    for body in bodies:
        try:
            resp = requests.post(url, headers=_headers(), json=body, timeout=_TIMEOUT)
        except requests.RequestException as e:
            last_err = f"network error: {type(e).__name__}"
            continue
        if resp.status_code == 200:
            data = resp.json()
            try:
                # Only the final content — never the reasoning field.
                return data["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, TypeError):
                last_err = "malformed response"
                continue
        if resp.status_code == 400:
            last_err = "http 400"
            continue  # maybe the extras were rejected -> try plain body
        # Other status codes: don't echo body (may contain sensitive detail).
        raise RuntimeError(f"OpenRouter HTTP {resp.status_code}")
    raise RuntimeError(f"OpenRouter call failed ({last_err}).")


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json(text):
    """Extract a JSON object from model output, tolerating code fences."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        m = _JSON_RE.search(cleaned)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def _evidence_brief(evidence):
    """Compact, id-tagged evidence list for the prompt (no fabrication)."""
    briefs = []
    for e in evidence or []:
        eid = e.get("evidence_id")
        if not eid:
            continue
        entry = {"evidence_id": eid}
        if e.get("source"):
            entry["source"] = e["source"]
        if e.get("page") is not None:
            entry["page"] = e["page"]
        if e.get("section"):
            entry["section"] = e["section"]
        if e.get("text"):
            entry["text"] = str(e["text"])[:700]
        briefs.append(entry)
    return briefs


def generate_explanation(decision, evidence, context=None, compliance=None,
                         rag_status=None):
    """
    Produce an evidence-grounded explanation of a decision.

    Parameters mirror the deterministic outputs:
        decision   : policy_engine.policy_decision(...) result
        evidence   : list of normalised evidence dicts (from rag_engine) —
                     already relevance-filtered by the caller
        context    : visual-context estimate dict
        compliance : verify_compliance(...) result (optional)
        rag_status : rag_engine.retrieve_evidence(...)["status"] (optional). Used
                     ONLY to choose the correct safe status message when the
                     grounding gate withholds generation — it never enables an
                     ungrounded explanation.

    Returns a structured dict; on any failure returns status "UNAVAILABLE"
    with empty fields so the caller can render "explanation unavailable".
    """
    decision = decision or {}
    compliance = compliance or {}
    context = context or {}
    evidence_brief = _evidence_brief(evidence)
    valid_ids = {e["evidence_id"] for e in evidence_brief}

    # -------------------------------------------------------------------------
    # ARCHITECTURAL GROUNDING GATE (STEP 6 — non-negotiable).
    # The LLM may ONLY produce a factual regulatory explanation when it has
    # retrieved, relevant evidence to ground it in. If RAG returned nothing
    # (Pinecone UNAVAILABLE, NO_RESULTS, or records without citable ids) OR every
    # hit was dropped by the relevance gate (INSUFFICIENT_EVIDENCE), we DO NOT
    # call the model and DO NOT fabricate a regulatory explanation. The
    # deterministic policy decision still stands entirely on its own; only the
    # *narrative* convenience layer is withheld. This runs BEFORE the API-key
    # check so the gate holds whether or not OpenRouter is configured.
    # -------------------------------------------------------------------------
    if not valid_ids:
        limitations = (INSUFFICIENT_EVIDENCE_MESSAGE
                       if rag_status == "INSUFFICIENT_EVIDENCE"
                       else NO_EVIDENCE_MESSAGE)
        return {
            "status": "SKIPPED_NO_EVIDENCE",
            "explanation": None, "why_route": None, "guidance": [],
            "evidence_ids_used": [],
            "limitations": limitations,
            "model": OPENROUTER_MODEL, "latency_ms": 0.0,
        }

    if not OPENROUTER_API_KEY:
        return {
            "status": "UNAVAILABLE",
            "explanation": None, "why_route": None, "guidance": [],
            "evidence_ids_used": [],
            "limitations": "LLM explanation unavailable: OPENROUTER_API_KEY not configured.",
            "model": OPENROUTER_MODEL, "latency_ms": 0.0,
        }

    payload = {
        "canonical_item": decision.get("waste_type") or decision.get("item"),
        "policy_decision": {
            "status": decision.get("status"),
            "waste_type": decision.get("waste_type"),
            "expected_route": decision.get("expected_route"),
            "rule_id": decision.get("rule_id"),
            "reason": decision.get("reason"),
        },
        "visual_context_estimate": context,
        "compliance": {
            "status": compliance.get("status"),
            "expected_route": compliance.get("expected_route"),
            "actual_route": compliance.get("actual_route"),
            "reason_code": compliance.get("reason_code"),
        },
        "evidence": evidence_brief,
        "note": ("Ground every factual claim in the provided evidence. If a "
                 "specific point is not supported by the evidence, put it under "
                 "'limitations' rather than asserting it."),
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

    t0 = time.perf_counter()
    try:
        content = _chat(messages)
    except Exception as e:
        return {
            "status": "UNAVAILABLE",
            "explanation": None, "why_route": None, "guidance": [],
            "evidence_ids_used": [],
            "limitations": f"LLM explanation unavailable: {str(e)[:200]}",
            "model": OPENROUTER_MODEL,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    parsed = _parse_json(content)
    if not isinstance(parsed, dict):
        # Fallback: surface the text as the explanation, flag the parse issue.
        return {
            "status": "OK",
            "explanation": content.strip()[:1500] if content else None,
            "why_route": None,
            "guidance": [],
            "evidence_ids_used": [],
            "limitations": "Model did not return structured JSON; showing raw text.",
            "model": OPENROUTER_MODEL, "latency_ms": latency_ms,
        }

    # Keep only evidence ids that were actually provided (drop hallucinations).
    used = [i for i in (parsed.get("evidence_ids_used") or []) if i in valid_ids]
    guidance = parsed.get("guidance") or []
    if isinstance(guidance, str):
        guidance = [guidance]

    return {
        "status": "OK",
        "explanation": parsed.get("explanation"),
        "why_route": parsed.get("why_route"),
        "guidance": [str(g) for g in guidance][:8],
        "evidence_ids_used": used,
        "limitations": parsed.get("limitations"),
        "model": OPENROUTER_MODEL,
        "latency_ms": latency_ms,
    }
