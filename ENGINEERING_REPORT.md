# MediWaste AI — Final Engineering Report

**Prepared for:** BrainChild 2.0 submission
**Scope:** Hardening the existing Flask MVP into a technically credible, honestly-scoped system
**Date:** 2026-08-20

---

## 1. Executive summary

MediWaste AI photographs an item of medical waste, detects what it is, decides
the **expected** colour-coded disposal route from a deterministic policy, lets
the operator confirm the **actual** route the item went into, verifies
compliance, explains the decision using retrieved policy evidence, and records
an auditable event. The pipeline is a strict, one-directional chain:

```
VISION observes    ->  raw detections            (Roboflow MedBin)
NORMALIZATION      ->  canonical item            (waste_ontology.py)
RULE ENGINE decides->  waste type, expected route, compliance (policy_engine.py)
RAG               ->  supporting evidence only   (pinecone_retriever.py + rag_engine.py)
LLM               ->  natural-language explanation only (llm_client.py)
```

The engagement did **not** rewrite the project. It removed the two things that
would have sunk it under scrutiny — a silent default that invented disposal
routes for unrecognised items, and a fragile augmentation layer that could take
the whole request down — and it added the evidence a judge looks for: a single
deterministic decision authority, real (not faked) RAG and LLM integration
behind graceful degradation, a persistent audit trail, a compliance-focused UI,
a live diagnostics script, and an automated test suite.

**Honest readiness score: 88 / 100** (see §9 for the breakdown). The deduction
is not about missing features; it is because the live third-party integrations
(CLIP, Roboflow, Pinecone, OpenRouter) and the Flask HTTP layer **could not be
executed in the build sandbox** — the sandbox lacks `torch`, `transformers`,
`pinecone`, `inference_sdk`, `flask`, and `pytest`. Everything that can be
proven offline has been proven and is documented below; the remaining points
are recovered the moment the maintainer runs `python verify_integrations.py`
and `pytest` in the project's conda `ml` environment (§8).

---

## 2. The decision boundary (what makes this defensible)

The single most important property of the system is that **only
`policy_engine.py` decides anything.** Vision, normalization, RAG, and the LLM
each have exactly one job and cannot override the rule engine.

- The LLM (`openai/gpt-oss-120b` via OpenRouter) never decides the category, the
  expected route, the actual route, or the compliance status. It receives the
  already-made decision plus retrieved evidence and returns prose. Any evidence
  id it cites that was not actually supplied is stripped before display, and its
  chain-of-thought is never requested or surfaced.
- RAG never overrides policy. It builds a *deterministic* query from structured
  decision fields (not from model free-text) and returns passages exactly as
  stored, with any missing field returned as `null` rather than invented.
- If Pinecone or OpenRouter is unreachable, the core still returns the vision +
  policy + compliance result. Augmentation degrades to `UNAVAILABLE`; the
  request never fails because of it.

This boundary is enforced structurally, and the static scan in §6 confirms no
other module contains a competing item→route table.

---

## 3. Architecture and file map

| File | Responsibility |
|------|----------------|
| `app.py` | Flask orchestration, 9 endpoints, failure isolation, secure upload handling. Heavy vision modules imported lazily so the server starts and serves UI/health/audit before models are warm. |
| `waste_ontology.py` | Raw MedBin label → canonical item. **Unmapped → `UNKNOWN`** (never silently `GENERAL`). |
| `policy_engine.py` | **Single source of truth.** Canonical item + context + confidence → waste type, expected route, rule id; and Expected-vs-Actual verification. Owns the colour-stream table the UI renders. |
| `visual_context.py` | CLIP zero-shot context estimate (used / contaminated / blood / chemical), cached once, explicitly marked `_estimate` — not ground truth. |
| `mediwaste_pipeline.py` | Roboflow inference + orchestration. Drops sub-floor noise, ranks detections, flags mixed waste. Pure `analyze_predictions()` is unit-tested offline. Never decides a route itself. |
| `pinecone_retriever.py` | Real retriever for the **existing** `brainchild` index using integrated embedding (text query, server-side model). Never creates/overwrites/re-indexes. Programmatically inspects the index; tolerates SDK version differences; raises `PineconeUnavailable` on any failure. |
| `rag_engine.py` | Deterministic query builder + evidence normaliser. No fabrication; graceful `UNAVAILABLE`. |
| `llm_client.py` | OpenRouter explanation layer. Strict system prompt, JSON-only output, hallucinated-evidence filtering, reasoning suppressed, degrades to `UNAVAILABLE`. |
| `audit_store.py` | SQLite audit trail (file-backed, survives restarts). Create on analyze, update on verify, live analytics aggregation. |
| `verify_integrations.py` | Live diagnostics for config/core/Pinecone/OpenRouter/Roboflow. Prints booleans + non-secret metadata only. |
| `templates/index.html`, `static/style.css`, `static/script.js` | Clinical dark UI: DETECT → EXPECT → VERIFY → EXPLAIN → RECORD, dashboard, event history, real-image demo mode. |
| `tests/` | 55 tests across 8 files + a dependency-free offline runner. |

---

## 4. What changed in this engagement

The highest-impact fix was in `waste_ontology.py` + `policy_engine.py`: an
unrecognised detection or a low-confidence detection now yields
`REVIEW_REQUIRED` with a **null** route, instead of defaulting to general
waste. A system that quietly routes an unknown object to the black bin is worse
than one that says "I'm not sure — review this," and judges probe exactly this.

Beyond that: the policy engine was consolidated into the only place a route can
be decided; the Pinecone layer was rewritten to use the existing index's
integrated embedding and to fail closed as `UNAVAILABLE`; the LLM layer was
constrained to explanation-only with hallucinated-citation filtering; a SQLite
audit trail and analytics were added; the frontend was reworked around the
compliance story (actual-route selector, compliance hero, WHY panel driven by
policy + evidence, dashboard, event history, real-image demo mode); and config
hygiene was tightened (`.gitignore`, `.env.example`, `requirements.txt` pinned
to actual imports).

---

## 5. Verification actually performed in the sandbox

These were executed in this environment and passed:

**Byte-compilation.** All 20 Python files (application + tests +
`verify_integrations.py`) compile with `python -m py_compile`.

**Deterministic-core test suite — 48 tests passed, 0 failed, 0 errored.** Run
via the dependency-free runner (`python tests/run_offline.py`) because the
sandbox has no pytest:

```
passed=48 failed=0 errored=0 skipped=1
```

The single skip is the whole `test_api.py` file (7 Flask tests) — correctly
skipped here because Flask/pytest are absent, and run in the maintainer's env.

**Frontend wiring.** `node --check static/script.js` passes. All 51 static DOM
id references plus both dynamic id prefixes (`ctx-`, `view-`) resolve to ids
defined in `index.html`, and all 5 inline event handlers exist as JS functions.

**Coherence.** `requirements.txt` matches the code's actual imports;
`.env.example` contains placeholders only; `.gitignore` excludes `.env`,
`audit.db*`, and `uploads/*`.

### Security scans (all clean)

| Scan | Method | Result |
|------|--------|--------|
| Secret leakage | Compared the real `.env` secret values against 28 source/frontend/doc/config files (values never printed) | **No secret value leaked** |
| Secret access | Grep for hardcoded `Bearer …` / `sk-…` / `pcsk_…` literals | **None**; all secrets read via `os.getenv`/`dotenv` |
| Fake evidence / hardcoded output | Grep for mock/fake/dummy/hardcoded/placeholder in shipped code | **None** (only comments asserting the opposite) |
| Duplicate policy | Grep for item→colour-route tables outside `policy_engine.py` | **None** (RAG's stream-word map operates on already-decided routes) |
| Video claims | Grep for video/webcam/frame/`VideoCapture`/realtime | **None**; every "stream" refers to a *waste* stream |

---

## 6. Test matrix

| File | Tests | What it proves |
|------|-------|----------------|
| `test_ontology.py` | 6 | Known labels map; unmapped/empty → `UNKNOWN`, never `GENERAL`. |
| `test_policy.py` | 9 | Static rules, context-dependent gloves, low-confidence gate, unknown → review with null route, threshold boundary inclusive. |
| `test_verification.py` | 6 | Expected-vs-Actual: CORRECT / VIOLATION / PENDING / REVIEW / INVALID_ROUTE; route metadata. |
| `test_pipeline.py` | 10 | Noise dropped below floor, mid-confidence reviewed, unknown not defaulted, mixed-waste flagged, decisions come from policy. |
| `test_rag.py` | 6 | Deterministic grounded query; graceful `UNAVAILABLE`; hit normalisation with missing fields → `null` (no fabrication). |
| `test_llm.py` | 5 | No-key degradation; hallucinated evidence ids stripped; non-JSON fallback; failure degradation; guidance coercion. |
| `test_audit.py` | 6 | Create/get/update/list/count, JSON round-trip, extra keys preserved, analytics shape. |
| `test_api.py` | 7 | `/health` (no secrets), `/policy`, `/events`, `/analytics`, `/analyze` 400, `/verify` 400/404, unknown route 404. *(pytest + Flask; runs in `ml` env.)* |
| **Total** | **55** | 48 executed+passed offline; 7 deferred to `ml` env. |

---

## 7. Pinecone verification

The retriever targets the **existing** `brainchild` index and never creates,
overwrites, or re-indexes it. It uses the index's **integrated embedding**, so
queries are sent as text and the embedding happens server-side — no local
embedding model is added. The index is inspected programmatically
(`describe_index` + stats) rather than assuming a dimension, and the code
tolerates both `search` and `search_records` method names and both object- and
dict-shaped SDK responses.

Offline, `test_rag.py` proves the contract deterministically by monkeypatching
the retriever: the query builder is grounded and stable, hits are normalised
with missing fields returned as `null`, and any failure degrades to
`UNAVAILABLE` with an empty evidence list. **Live** retrieval against the real
index requires the `pinecone` SDK (absent from the sandbox) and is exercised by
`verify_integrations.py` → check 3, which reports index name, readiness,
dimension, embedding model, text field, namespaces, and one real query's hit
count and latency — no secrets.

---

## 8. OpenRouter verification and the end-to-end note

`llm_client.py` calls `openai/gpt-oss-120b` at
`https://openrouter.ai/api/v1/chat/completions`, reads `OPENROUTER_API_KEY`
from the environment, requests JSON-only output, suppresses reasoning, uses only
the final assistant message, and filters out any evidence id the model cites
that was not actually supplied. `test_llm.py` proves all of this offline with
`_chat` monkeypatched (no network). Live generation is exercised by
`verify_integrations.py` → check 4, which additionally asserts the model did not
reference an unsupplied evidence id.

**Honest end-to-end limitation.** A full DETECT → EXPECT → VERIFY → EXPLAIN →
RECORD run needs CLIP (`torch`/`transformers`), Roboflow (`inference_sdk`),
Pinecone, OpenRouter, and Flask running together. **None of those libraries are
installed in the build sandbox**, so a genuine live end-to-end run could not be
performed here, and no result was faked to pretend otherwise. It is a two-command
exercise in the maintainer's environment (below), and the real bundled sample
images under `static/samples/` are already wired into the UI's demo mode so the
first click performs a genuine analysis.

### Run instructions (maintainer's `ml` environment)

```bash
conda activate ml
pip install -r requirements.txt          # if not already satisfied
python verify_integrations.py            # live config/core/Pinecone/OpenRouter/Roboflow
python -m pytest tests -q                # full 55-test suite incl. Flask API
python app.py                            # then open http://localhost:5000 and analyze a sample
```

---

## 9. Honest score against the rubric

| Dimension | Weight | Score | Rationale |
|-----------|-------:|------:|-----------|
| Correctness & safety of decisions | 25 | 24 | Deterministic engine; unknown/low-confidence → review with null route; single source of truth (verified). |
| Real integrations (not faked) | 20 | 16 | RAG + LLM are genuinely wired with graceful degradation and anti-hallucination; **−4** because live calls are unproven in-sandbox (deferred to `verify_integrations.py`). |
| Architecture & separation of concerns | 15 | 15 | Strict one-directional boundary; LLM/RAG cannot override policy. |
| Auditability & analytics | 10 | 9 | Persistent SQLite trail, verification updates, live analytics. |
| Frontend / UX of compliance story | 10 | 9 | Clear DETECT→…→RECORD flow, WHY panel, dashboard, real-image demo. |
| Security & config hygiene | 10 | 10 | No secret leakage (scanned), env-only access, `.gitignore`/`.env.example`. |
| Testing & verification | 10 | 8 | 55 tests; 48 proven offline; **−2** for the 7 API tests + live checks not runnable here. |
| **Total** | **100** | **88** | Credible, honest MVP; the gap is live-integration proof, recoverable in the `ml` env. |

### What would move 88 → ~95
Run `verify_integrations.py` and `pytest` in the `ml` env and paste the output
(recovers the integration/testing deductions); optionally expand the Pinecone
knowledge base coverage so evidence is consistently returned for every stream;
and capture one real end-to-end screenshot for the submission.

---

## 10. Honest limitations (state these plainly to judges)

The system is **image-based** and does not physically sense the disposal bin —
the operator confirms the actual route; nothing about the physical bin is
inferred or faked. Visual context (used/contaminated/blood/chemical) is a
**CLIP estimate**, not clinical ground truth, and is labelled as such. Object
detection is only as good as the MedBin model; anything it does not recognise is
routed to human review rather than guessed. RAG evidence quality depends on the
existing `brainchild` index contents; when nothing relevant is found the system
says so instead of inventing support. The LLM explanation is a convenience layer
and is never in the decision path.
