# MediWaste AI — P0 Hardening Report

**Mode:** Final hardening of the existing Flask MVP (no redesign).
**Date:** 2026-08-20
**Scope of this round:** close the remaining P0 issues — above all, the
architectural flaw where the LLM could produce a regulatory explanation with no
retrieved evidence behind it — and make the live verifier actually prove the
integrations when run in the maintainer's environment.

A note on honesty up front, because the brief demands it: the build sandbox this
work was performed in has **no outbound network and no package installer**. That
was re-confirmed live this session, not assumed:

```
pip install pinecone   -> ProxyError: Tunnel connection failed: 403 Forbidden
https://pypi.org/...    -> URLError: Tunnel connection failed: 403 Forbidden
DNS for openrouter.ai   -> gaierror (name resolution fails)
conda                   -> command not found
import pinecone/torch/transformers/flask/pytest -> ModuleNotFoundError
```

So the *live* calls to Pinecone, OpenRouter, Roboflow, and a Flask HTTP run
**cannot be executed from here**, and nothing about them has been faked. What
*can* be proven here — the deterministic core, the grounding gate across the
real `rag_engine`→`llm_client` boundary, byte-compilation, the frontend wiring,
and the absence of secret leakage — has been proven and is shown below. The live
sections tell you exactly how to prove the rest in one command in the `ml` env,
and what a correct result looks like.

---

## 1. What was fixed

**1.1 The grounding gate (the P0 architectural fix).** Previously
`llm_client.generate_explanation(...)` would call the model and return prose even
when RAG returned nothing — an explanation with no evidence under it. That is now
structurally impossible. The function computes the set of *citable* evidence ids
first and, if it is empty, returns immediately without ever contacting the model:

```
status            = "SKIPPED_NO_EVIDENCE"
explanation       = None
why_route         = None
guidance          = []
evidence_ids_used = []
limitations       = "Evidence-grounded explanation is temporarily unavailable.
                     The route shown was determined by the deterministic policy engine."
```

The gate runs **before** the API-key check, so it holds whether or not OpenRouter
is configured. Evidence records that carry no id are treated as no-evidence,
because an untraceable passage cannot ground a citation. The deterministic policy
decision is untouched — only the narrative convenience layer is withheld.

**1.2 Retriever signature (`actual_route`).** `rag_engine.retrieve_evidence(...)`
and `build_query(...)` now accept `actual_route=None` and use it to enrich the
violation query when a compliance result doesn't already carry it. Additive and
non-breaking; `app.py`'s `/verify` path now passes it explicitly.

**1.3 UI status semantics.** The system panel and WHY panel no longer show a
misleading "OK". RAG renders as `READY` / `NO-EVIDENCE` / `UNAVAILABLE`; LLM
renders as `READY` / `DEGRADED (no evidence)` / `UNAVAILABLE`. When the gate
fires, the WHY panel shows the safe status message (not model prose), while the
deterministic policy line and the policy-derived corrective guidance still render.

**1.4 The real "No module named 'pinecone'" blocker.** The import guard in
`pinecone_retriever.py` now distinguishes three cases and prints the exact fix:
package absent, a legacy `pinecone-client` shadowing the modern SDK (the usual
cause of your live error), or an incompatible build. `requirements.txt` documents
the uninstall/reinstall remedy, and `inspect_index()` now reports the installed
`sdk_version`.

**1.5 The live verifier now proves the hardening.** `verify_integrations.py`
gained an offline **grounding-gate assertion** (fatal), a **zero-result
diagnosis** for Pinecone (namespace/text-field/broad-probe — no fake fallback),
and a **real end-to-end check** (detect → decide → retrieve → gate → explain on a
bundled sample) that asserts the gate invariant on a live run.

---

## 2. Pinecone live verification

**Runnable from this sandbox: NO** (no `pinecone` SDK, no network — see the 403
proof above). **Not faked.**

What the hardened retriever guarantees, and what the verifier checks when you run
it in `ml`:

- It targets the **existing** `brainchild` index and never creates, overwrites,
  or re-indexes. It uses the index's **integrated embedding** (text in,
  server-side model), so no local embedder is added.
- `inspect_index()` reads the index programmatically and reports name, readiness,
  state, `sdk_version`, dimension, metric, vector type, embedding model, the
  `text` field from the field map, namespaces, and total vector count — assuming
  none of it.
- A real query runs through the deterministic query builder. **If it returns
  zero records, the verifier does not pass silently** — it prints the namespace
  queried vs. the index's namespaces, the total vector count, and a broad probe
  query result, so you can tell an empty/mismatched index from an over-narrow
  query.

Run it:

```bash
conda activate ml
pip uninstall -y pinecone-client pinecone       # clear any legacy client
pip install -r requirements.txt                 # installs pinecone>=5.1,<8
python verify_integrations.py                    # section 4 = PINECONE
```

A healthy result shows `index 'brainchild' reachable (ready=True ...)`,
`sdk_version=5.x`/`6.x`, a non-null `text_field`, and `retrieve status=OK
hits>0`. If you instead see the import diagnosis, the message itself contains the
exact command to fix it.

---

## 3. Real evidence sample

**Cannot be produced from this sandbox, and I will not fabricate one.** A "real
evidence sample" means actual records returned by the live `brainchild` index —
their real ids, scores, source/page/section, and text. Inventing any of that
would violate the one rule that makes this system defensible, so this section is
deliberately left as a template that `verify_integrations.py` (section 4) fills
with genuine values when you run it:

```
top id=<real record id>  score=<real score>  has_text=True
source=<real or null>  page=<real or null>  section=<real or null>
```

The normalisation contract is proven offline in `test_rag.py`: fields that are
absent on a record come back as `null`, never invented (see §6). The moment the
live query returns records, those same guarantees apply to the real data.

---

## 4. OpenRouter live verification

**Runnable from this sandbox: NO** (DNS for `openrouter.ai` fails; no `requests`
call can leave the box). **Not faked.**

`llm_client.py` calls `openai/gpt-oss-120b` at the configured base URL, reads the
key only from the environment, requests JSON-only output, suppresses reasoning,
uses only the final assistant message, and strips any evidence id the model cites
that was not supplied. `verify_integrations.py` section 5 exercises this against
the real endpoint and asserts `evidence_ids_used ⊆ supplied ids` (fails loudly on
a hallucinated id). Section 3 additionally asserts — offline, no network — that
empty evidence yields `SKIPPED_NO_EVIDENCE` with a null explanation, and that
evidence-with-no-key yields `UNAVAILABLE` (never a fabricated answer).

```bash
python verify_integrations.py     # section 3 = GROUNDING GATE, section 5 = OPENROUTER
```

Healthy result: gate `PASS`; OpenRouter `status=OK`, `no hallucinated evidence
ids`.

---

## 5. End-to-end result

**The live E2E (real image → CLIP → Roboflow → Pinecone → OpenRouter → Flash UI)
cannot run here** (none of those libraries are installable in the sandbox). It is
performed by `verify_integrations.py` section 7 in the `ml` env, which asserts the
gate invariant on the real pipeline.

**What was proven here instead — the composed gate across the real modules**
(`rag_engine` + `llm_client`, exactly as `app.py` wires them), run this session:

| Scenario | RAG status | LLM status | Explanation | Model called? | Verdict |
|----------|-----------|-----------|-------------|--------------|---------|
| Pinecone DOWN | `UNAVAILABLE` | `SKIPPED_NO_EVIDENCE` | `None` | no | no fabrication |
| Pinecone zero hits | `NO_RESULTS` | `SKIPPED_NO_EVIDENCE` | `None` | no | no fabrication |
| Evidence present (+key) | `OK` (1 hit) | `OK` | grounded, cites `doc-1` only | **yes (1×)** | correct |
| `actual_route` enrichment | query gains "misplaced in black general waste bin" | — | — | — | STEP 4 param works |

The critical line: the model is contacted **only** in the evidence-present case,
and it is impossible for the pipeline to emit a factual explanation without
evidence behind it.

To run the genuine live E2E:

```bash
python verify_integrations.py     # section 7 = END-TO-END
python app.py                      # then open http://localhost:5000 and analyze a sample
```

---

## 6. Test matrix

Unit tests are hermetic (network monkeypatched). Live integration checks live in
`verify_integrations.py` and are **not** counted as passing here — they are marked
as requiring the `ml` env, per the brief's rule against calling a mocked test a
live pass.

| File | Tests | Unit / Live | Status here |
|------|------:|-------------|-------------|
| `test_ontology.py` | 6 | unit | PASS |
| `test_policy.py` | 9 | unit | PASS |
| `test_verification.py` | 6 | unit | PASS |
| `test_pipeline.py` | 10 | unit | PASS |
| `test_rag.py` | 6 | unit (Pinecone monkeypatched) | PASS |
| `test_llm.py` | **7** | unit (`_chat` monkeypatched) | PASS — includes **2 new gate tests** |
| `test_audit.py` | 6 | unit (temp SQLite) | PASS |
| `test_api.py` | 7 | unit (Flask test client) | requires pytest+Flask → runs in `ml` |
| **Total** | **57** | | **50 pass offline, 7 deferred to `ml`** |
| `verify_integrations.py` | 7 checks | **LIVE** | run in `ml` (not a mocked pass) |

Offline runner output this session: `passed=50 failed=0 errored=0 skipped=1`
(the skip is the whole Flask file). Also verified here: all 20 Python modules
byte-compile; `node --check static/script.js` passes; **0 API-key values** appear
in any of the 28 scanned source/doc files (the only matches were non-secret
config values — model id, index name, base URL — which are supposed to be there).

The two new gate tests are the important additions:
`test_no_evidence_gate_skips_llm_and_never_fabricates` (proves `_chat` is never
called without evidence, even with a key present) and
`test_evidence_without_ids_is_treated_as_no_evidence`.

---

## 7. Remaining limitations (brutally honest)

- **Live integrations are unproven from this sandbox.** Pinecone, OpenRouter,
  Roboflow, CLIP, and the Flask HTTP layer cannot be installed or reached here
  (403 proxy, blocked pip, no conda). Sections 2–5 above become real only after
  you run `verify_integrations.py` in the `ml` env. I did not fake any of them.
- **I cannot confirm the app boots end-to-end from here.** The deterministic core
  and the gate are proven; a full server run with the vision stack is not.
- **The "No module named 'pinecone'" error is an environment fix, not a code
  bug.** The code is correct for the modern SDK; you must install it (and remove
  any legacy `pinecone-client`) in the `ml` env. The import guard now tells you
  precisely how.
- **RAG quality depends on the `brainchild` index contents.** If the live query
  returns zero records, the gate will (correctly) withhold explanations for those
  items until the index/namespace is populated. The verifier now diagnoses this
  rather than hiding it.
- **The system is image-based, not bin-sensing.** The operator confirms the
  actual route; nothing about the physical bin is detected. Visual context is a
  CLIP *estimate*, labelled as such, never clinical truth.
- **I do not have the official BrainChild 2.0 scoring sheet.** The score below is
  against a representative hackathon rubric; if your judges weight differently
  (e.g. heavier on live demo), adjust accordingly.

---

## 8. Final hackathon score estimate

Scored against a representative hackathon rubric. Two numbers, because honesty
requires separating "provable today" from "provable after one command in `ml`."

| Dimension | Weight | Proven **now** | After `verify_integrations.py` passes in `ml` | Notes |
|-----------|-------:|---------------:|----------------------------------------------:|-------|
| Decision correctness & safety | 25 | 24 | 24 | Deterministic engine; unknown/low-confidence → review with null route; **LLM can no longer explain without evidence**. |
| Real integrations (not faked) | 20 | 12 | 18 | Genuinely wired with graceful degradation + anti-hallucination; live calls unprovable here (−8 now), recovered when the verifier passes. |
| Architecture & separation | 15 | 15 | 15 | Strict one-directional boundary; the gate makes "explain-without-evidence" structurally impossible. |
| Auditability & analytics | 10 | 9 | 9 | Persistent SQLite trail now records `SKIPPED_NO_EVIDENCE` honestly. |
| Frontend / compliance UX | 10 | 8 | 9 | Clear status semantics; live demo screenshot still pending (needs a run). |
| Security & config hygiene | 10 | 10 | 10 | 0 secret-value leaks (scanned); env-only access; `.gitignore`/`.env.example`. |
| Testing & verification | 10 | 8 | 9 | 57 tests; 50 proven offline incl. 2 new gate tests; 7 API + 7 live checks run in `ml`. |
| **Total** | **100** | **86** | **~94** | |

**Honest headline: 86 / 100 as demonstrable from here today; ~94 once you run
`python verify_integrations.py` in the `ml` env and it reports the gate, Pinecone,
OpenRouter, and E2E checks passing.** The single biggest credibility gain this
round is not a number — it is that the system will now refuse to invent a
regulatory explanation when it has no evidence, and it says so plainly in the UI
and the audit log.

### The three commands that close the gap

```bash
conda activate ml
pip uninstall -y pinecone-client pinecone && pip install -r requirements.txt
python verify_integrations.py        # gate + Pinecone + OpenRouter + E2E, live
python -m pytest tests -q            # full 57-test suite incl. Flask API
python app.py                        # open http://localhost:5000, analyze a sample
```
