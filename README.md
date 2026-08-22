# MediWaste AI

Visual medical-waste segregation and compliance assistant. A staff member
photographs an item of medical waste; the system detects what it is, decides
the **expected** disposal route from a deterministic policy, lets the operator
confirm the **actual** route the item went into, verifies compliance, explains
the decision with retrieved policy evidence, and records an auditable event.

This MVP is deliberately **image-based**. It does not physically detect the
disposal bin — the operator confirms the actual route. Nothing about the
physical bin is inferred or faked.

## Decision boundary (non-negotiable)

The core guarantee is a strict separation of concerns:

```
VISION observes    ->  raw detections            (Roboflow MedBin)
NORMALIZATION      ->  canonical item            (waste_ontology.py)
RULE ENGINE decides->  waste type, expected route, compliance (policy_engine.py)
RAG provides       ->  supporting evidence only   (pinecone_retriever + rag_engine)
LLM explains       ->  natural-language rationale (llm_client, OpenRouter)
```

`policy_engine.py` is the **single source of truth**. The LLM never decides the
category, the canonical item, the expected route, the actual route, or the
compliance status, and it can never override policy. RAG never overrides
policy. The LLM's chain-of-thought is never requested or surfaced — only the
final structured answer is used. If Pinecone or OpenRouter is unavailable, the
vision → policy → compliance core still returns a complete result.

Unknown or low-confidence detections are **not** silently forced into a
"general waste" default. They become `REVIEW_REQUIRED` with a null expected
route, so an operator escalates rather than trusting a guess.

## Architecture

| File | Responsibility |
|------|----------------|
| `app.py` | Flask API; orchestrates core + best-effort RAG/LLM; writes audit events. |
| `mediwaste_pipeline.py` | Roboflow inference + normalization; asks the policy engine (never decides). |
| `waste_ontology.py` | Maps raw model classes to canonical items; unmapped → `UNKNOWN`. |
| `policy_engine.py` | Deterministic decisions, disposal streams, and Expected-vs-Actual verification. |
| `visual_context.py` | CLIP zero-shot context estimate (used/contaminated/blood/chemical) — an estimate, not ground truth. |
| `pinecone_retriever.py` | Version-tolerant Pinecone client for the existing integrated-embedding index. Inspect + search only. |
| `rag_engine.py` | Builds a deterministic retrieval query and normalizes evidence; never fabricates fields. |
| `llm_client.py` | OpenRouter (`openai/gpt-oss-120b`) explanation layer; returns structured JSON. |
| `audit_store.py` | SQLite audit trail that survives restarts. |
| `templates/`, `static/` | Staff UI: analyze, compliance verification, dashboard, event history. |

## Security

Credentials live only in `.env`, loaded via `python-dotenv`. Keys are never
hard-coded, logged, printed, returned by the API, or shown in the UI. `.env` is
git-ignored; `.env.example` documents the required variable names with
placeholders. The `/health` and `/policy` endpoints expose only booleans and
non-secret metadata (e.g. whether a key is configured, the model reference —
never the key value). Uploaded files are saved under a UUID-prefixed,
`secure_filename`-sanitized name and validated as real images before use.

## Requirements

- Python 3.10 (a conda `ml` environment is recommended for the torch/CLIP stack)
- A populated Pinecone index (`brainchild`) using integrated embedding
  (`llama-text-embed-v2`). This project only reads it — it never creates,
  overwrites, or re-indexes.
- Roboflow, Pinecone, and OpenRouter API keys in `.env`.

## Setup & run

```bash
# 1. Configure secrets
cp .env.example .env          # then edit .env with your real keys

# 2. Install (conda env recommended for torch + transformers)
conda activate ml
pip install -r requirements.txt

# 3. (Optional but recommended) verify live integrations without exposing secrets
python verify_integrations.py

# 4. Run
python app.py                 # serves http://localhost:5000
```

The deterministic core and the offline test suite run **without** torch,
transformers, Roboflow, Pinecone, or OpenRouter installed — heavy and network
dependencies are imported lazily. Live inference requires them.

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/` | Staff UI. |
| POST | `/analyze` | Detect + decide + best-effort evidence/explanation; creates a PENDING audit event. |
| POST | `/verify` | Compare expected vs actual route; update the event with the compliance outcome. |
| GET  | `/events` | Recent audit events. |
| GET  | `/events/<id>` | Single event detail. |
| GET  | `/analytics` | Aggregate compliance analytics for the dashboard. |
| GET  | `/policy` | Disposal streams + valid routes (drives the colour guide and route selector). |
| GET  | `/health` | Subsystem readiness booleans (no secrets). |
| GET  | `/uploads/<file>` | Serve a stored image for the event detail view. |

`/analyze` accepts `multipart/form-data` with an `image` file (jpg/jpeg/png,
≤10 MB) and an optional `station`. `/verify` accepts JSON
`{event_id, actual_route, station?}`.

## Testing

```bash
# Offline, deterministic core (no network, no heavy deps):
python -m pytest tests -q

# Live integration diagnostics (needs .env + network):
python verify_integrations.py
```

## Honest limitations

- The physical disposal bin is **not** detected; the operator confirms the
  actual route. Compliance is Expected (policy) vs Actual (operator-confirmed).
- Visual context (used/contaminated/blood/chemical) is a CLIP **estimate** and
  is labelled as such in the UI; it is an input to context-dependent rules, not
  clinical ground truth.
- Evidence quality depends entirely on the contents of the existing Pinecone
  index; if a field (source/page/section/text) is absent on a record, it is
  shown as null rather than invented.
- If Pinecone or OpenRouter is down, evidence and the natural-language
  explanation degrade gracefully to "unavailable" while the deterministic
  decision and compliance verification still stand.
