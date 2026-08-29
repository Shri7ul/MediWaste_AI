# MediWaste AI

**Visual medical-waste segregation & compliance auditing for hospitals.**
Point a camera at an item of medical waste, get the *correct* colour-coded
disposal stream, confirm which bin was actually used, and leave behind a
tamper-evident audit trail — plus a guided, route-specific disposal workflow
and a collection-cycle tracker for the housekeeping round.

Built for BrainChild 2.0. Flask backend + Next.js 14 frontend, deterministic
rule engine at the centre, retrieval and LLM strictly on the outside.

---

## 0. Read this before you demo anything

This project is deliberately honest about where the intelligence stops. If you
present it, present it this way:

* **Physical bins are NOT detected.** The camera sees the *waste item*. It does
  not see, recognise, or verify the bin.
* **The actual route is operator-confirmed.** A human presses the colour they
  actually used. That confirmation — not the model — is what the audit trail
  records as reality.
* **`policy_engine.py` is the decision authority.** The expected disposal route
  is produced by explicit, versioned rules. Nothing else may override it.
* **RAG supplies supporting evidence only.** Retrieved guideline passages
  explain a decision that was already made. They never change it, and they are
  never fabricated — missing fields come back as `null`.
* **The LLM supplies explanation only.** Natural-language wording for humans.
  It has no vote.
* **CLIP visual context is an estimate.** It is contextual signal, not ground
  truth, and it is labelled as such in the UI.
* **Bin capacity is SIMULATED.** There is no IoT device, no weight cell, no
  fill sensor, no RFID. The UI carries an
  *"Exhibition mode · Simulated capacity"* disclaimer and it must stay there.
* **Unknown or low-confidence detections become `REVIEW_REQUIRED`.** The system
  escalates to a human instead of guessing.

If a judge asks "is the bin fill level real?" the answer is **no, it is
simulated for the exhibition** — and that answer is already on screen.

---

## 1. The decision boundary

```
CAMERA IMAGE
    │
    ▼
VISION            Roboflow hosted detection (inference-sdk)
    │             + CLIP visual context  ── estimate only, never authoritative
    ▼
NORMALIZATION     waste_ontology.py  → canonical waste category
    │
    ▼
RULE ENGINE       policy_engine.py   → EXPECTED ROUTE  ◄── the only authority
    │                                  (versioned rule id + policy version)
    ├─────────────► RAG      rag_engine.py / pinecone_retriever.py
    │                        supporting guideline passages, or UNAVAILABLE
    ├─────────────► LLM      llm_client.py
    │                        human-readable explanation, or UNAVAILABLE
    ▼
OPERATOR CONFIRMS actual route  (POST /verify)
    │
    ▼
COMPLIANCE VERDICT  CORRECT / VIOLATION / REVIEW_REQUIRED / INVALID_ROUTE
    │
    ▼
AUDIT TRAIL       audit_store.py → SQLite (audit.db)
    │
    ├─► DISPOSAL WORKFLOW    disposal.py   (route-specific, ordered steps)
    ├─► COLLECTION CYCLE     collection.py (multi-event housekeeping round)
    └─► ANALYTICS            audit_store.analytics() → dashboard
```

Both RAG and the LLM can be completely down and the compliance decision is
still produced, still correct, and still auditable.

---

## 2. Repository map

Backend (repository root):

| Path | Role |
| --- | --- |
| `app.py` | Flask application. All HTTP routes, upload validation, CORS allowlist, error envelope. |
| `mediwaste_pipeline.py` | Orchestrates vision → normalization → policy → RAG → LLM for one image. |
| `visual_context.py` | CLIP-based visual context. Estimate only. Lazily imported. |
| `waste_ontology.py` | Maps raw detection labels onto canonical waste categories. |
| `policy_engine.py` | **Decision authority.** Streams, static rules, thresholds, `verify_compliance()`. |
| `rag_engine.py` | Normalises retrieved evidence, applies a relevance-quality gate, degrades to `UNAVAILABLE`. |
| `pinecone_retriever.py` | Queries the pre-existing Pinecone index (server-side embedding). Read-only. |
| `llm_client.py` | OpenRouter explanation call. Degrades to `UNAVAILABLE`. |
| `audit_store.py` | SQLite audit trail + `analytics()` aggregations. |
| `facility.py` | Ward configuration and ward normalisation. |
| `operations.py` | Bin overview and **simulated** capacity model. |
| `disposal.py` | Route-specific disposal workflow definitions and step completion. |
| `collection.py` | Collection jobs: snapshot eligibility, resume, completion. |
| `templates/`, `static/` | Legacy server-rendered staff page served at Flask `/`, plus demo sample images. |
| `tests/` | 15 test modules + `run_offline.py`, a stdlib-only runner. |
| `verify_integrations.py` | Read-only integration probe (config / core / grounding gate / Pinecone / OpenRouter / Roboflow). |
| `validate_live.py` | Spawns the real app on a spare port and runs an A–H live validation report. |
| `data/hospital_guideline.pdf` | Source guideline document for reference. The Pinecone index already exists; this repo contains no ingestion script. |

Frontend (`frontend/`):

| Path | Role |
| --- | --- |
| `src/app/page.tsx` | Redirects to `/scan`. |
| `src/app/scan/page.tsx` | Capture → analyze → confirm route → result. The main demo screen. |
| `src/app/operations/page.tsx` | Bin overview, simulated capacity, start/continue a collection job. |
| `src/app/disposal/[eventId]/page.tsx` | Per-event disposal workflow. |
| `src/app/disposal/job/[jobId]/page.tsx` | Collection-job workflow across many events. |
| `src/app/events/page.tsx` | Audit event list + detail. |
| `src/app/dashboard/page.tsx` | Compliance performance analytics. |
| `src/lib/api/client.ts` | Single API client. Resolves the backend base URL at runtime. |
| `next.config.mjs` | Same-origin `/backend/:path*` rewrite to `BACKEND_ORIGIN`. |
| `certs/` | Local TLS material for LAN HTTPS. **Gitignored. Never commit.** |

---

## 3. Prerequisites — and what this repository actually enforces

Be careful here, because most of these are *not* pinned by the repo:

| Thing | What the repository enforces | Practical advice |
| --- | --- | --- |
| Python version | **Nothing.** There is no `pyproject.toml`, `setup.py`, `setup.cfg`, `runtime.txt`, or `Dockerfile` in this repository, so no Python version is enforced anywhere. | The pinned dependency set (`torch 2.4.0`, `numpy 1.26.4`, `transformers 4.44.2`) installs cleanly on CPython 3.10–3.11 on Windows x64. The offline test suite was executed on Python 3.10 during development. |
| Node version | **Nothing.** `frontend/package.json` has no `engines` field. | Next.js 14.2.5 requires a modern Node LTS. Node 18.17+ or 20.x LTS is the safe choice. |
| Package manager | `frontend/package-lock.json` exists → npm. | Use `npm ci` for a reproducible install, `npm install` if you need to add anything. |
| Python deps | `requirements.txt`, fully pinned except `pinecone>=5.1,<8`. | See §4 for the one dependency conflict you may actually hit. |
| GPU | Nothing. `torch 2.4.0` is the default CPU wheel unless you install otherwise. | CPU is fine. CLIP visual context is the only local model and it is lazily imported. |
| API keys | Nothing at import time. Missing keys degrade features, they do not crash the server. | See §5. |

You also need, on a fresh Windows laptop:

* **Git** — to clone.
* **PowerShell** — every command in this README is written for PowerShell, not bash.
* **Chrome or Edge** on the laptop; **Chrome** on the phone for the mobile demo.
* Optionally **mkcert** for the HTTPS phone-camera demo (§12–§13). It is *not*
  needed for the laptop-only demo.

There is no Docker setup in this repository. Do not look for one.

---

## 4. Zero to running backend (PowerShell)

```powershell
# 1. Get the code
git clone <your-repo-url> MediWaste_AI
cd MediWaste_AI

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell refuses to run the activation script, allow signed local scripts
for your user only (this is the least-privilege option):

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

```powershell
# 3. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`torch 2.4.0` is a large download. Expect this step to take a while on a fresh
laptop.

**The one dependency conflict you may hit.** The Pinecone SDK was renamed, and
having both the old and new distributions installed breaks imports. If you see
Pinecone import errors, run exactly what `requirements.txt` documents:

```powershell
pip uninstall -y pinecone-client pinecone
pip install "pinecone>=5.1,<8"
```

```powershell
# 4. Create your local secrets file from the template
Copy-Item .env.example .env
notepad .env
```

`.env` is gitignored. Never commit it, never paste its contents into a chat,
an issue, a slide, or a screenshot.

---

## 5. Environment variables (backend)

Every variable below was read out of the source. Nothing here is invented.
`.env.example` documents the first group; the second group is **real but not
yet in `.env.example`** — you can add any of them to `.env` and they will be
picked up.

### Documented in `.env.example`

| Variable | Default in code | Effect |
| --- | --- | --- |
| `ROBOFLOW_API_KEY` | none | Hosted detection. Missing → `/analyze` returns `503 VISION_UNAVAILABLE`. |
| `MODEL_ID` | `medbin_dataset-fqhi7/1` | Roboflow model reference, echoed by `/health` as `model_ref`. |
| `ROBOFLOW_API_URL` | `https://serverless.roboflow.com` | Override only for a self-hosted inference server. |
| `PINECONE_API_KEY` | none | Guideline retrieval. Missing → RAG reports `UNAVAILABLE`. |
| `PINECONE_INDEX_NAME` | `brainchild` | Existing index. This repo never creates or re-indexes it. |
| `PINECONE_NAMESPACE` | `__default__` | Records-API namespace. |
| `OPENROUTER_API_KEY` | none | Explanation text. Missing → explanation `UNAVAILABLE`. |
| `OPENROUTER_MODEL` | `openai/gpt-oss-120b` | Explanation model. |
| `OPENROUTER_BASE_URL` | OpenRouter default | Override for a proxy. |
| `POLICY_ACCEPT_THRESHOLD` | `0.40` | At or above → decision accepted. |
| `POLICY_REVIEW_FLOOR` | `0.20` | Between floor and accept → `REVIEW_REQUIRED`. |
| `RAG_TOP_K` | `8` | Passages retrieved per query. |
| `MAX_UPLOAD_MB` | `10` | Upload cap. Over it → `413`. |
| `PORT` | `5000` | Port used by `python app.py`. |

### Real, in the code, not in `.env.example`

| Variable | Default in code | Effect |
| --- | --- | --- |
| `CORS_ALLOW_ORIGINS` | empty (CORS off) | Comma-separated **exact** origins (`scheme://host:port`). No wildcards, no prefix matching. Only needed if you are *not* using the `/backend` proxy (§7). |
| `FACILITY_WARDS` | 7 built-in wards | `ER:Emergency,ICU-1:Intensive Care 1,LAB` — `CODE:Label`, or just `CODE`. |
| `FACILITY_PROFILE` | `default` | Reported in facility context. |
| `AUDIT_DB_PATH` | `audit.db` next to `app.py` | Move the SQLite audit database. |
| `FLASK_DEBUG` | `0` | `1`/`true` enables debug when launched via `python app.py`. |
| `OPENROUTER_TIMEOUT` | `60` | Seconds before the explanation call gives up. |
| `RAG_RERANK_MODEL` | `bge-reranker-v2-m3` | Pinecone server-side reranker model. |
| `VALIDATE_PORT` | `5057` | Port `validate_live.py` spawns the app on. |

### Frontend (`frontend/.env.local`)

| Variable | Value in `frontend/.env.example` | Effect |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `/backend` | Explicit API base. Wins over everything. `/backend` keeps API calls same-origin. |
| `BACKEND_ORIGIN` | `http://127.0.0.1:5000` | Server-side rewrite target for `/backend/:path*`. Not exposed to the browser. |
| `NEXT_PUBLIC_API_PORT` | commented, `5000` | Only used when `NEXT_PUBLIC_API_BASE_URL` is unset. |

Every `NEXT_PUBLIC_*` value is inlined into the browser bundle at build time.
Never put a secret in one.

---

## 6. Run it locally (laptop only)

Two terminals. Terminal 1 — backend:

```powershell
cd MediWaste_AI
.\.venv\Scripts\Activate.ps1
python app.py
```

That binds **loopback only** (`app.run()` is called without a `host=`
argument), on `PORT`, default `5000`. Sanity check in a browser or a third
terminal:

```powershell
curl.exe http://127.0.0.1:5000/health
```

Terminal 2 — frontend:

```powershell
cd MediWaste_AI\frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Open **http://localhost:3000** — `/` redirects to `/scan`.

Flask also serves a legacy server-rendered staff page at
**http://127.0.0.1:5000/** (`templates/index.html`). The Next.js app at port
3000 is the one to demo.

---

## 7. How the frontend finds the backend

`frontend/src/lib/api/client.ts` resolves the base URL in this order:

1. `NEXT_PUBLIC_API_BASE_URL`, if set. Always wins.
2. Otherwise, the origin the page was served from, with `NEXT_PUBLIC_API_PORT`
   (default `5000`) substituted — so a phone loading the app from
   `http://<laptop-ip>:3000` calls Flask on `<laptop-ip>`, not on its own
   loopback. No laptop IP is ever hardcoded.
3. During server rendering, where there is no browser origin:
   `http://127.0.0.1:5000`.

The shipped default is option 1 with the value `/backend`. `next.config.mjs`
rewrites `/backend/:path*` to `BACKEND_ORIGIN` **server-side**, which means:

* API calls are **same-origin**, so an `https://` page never triggers a mixed-
  content block when talking to a plain-HTTP Flask (§12).
* The browser never performs a cross-origin request, so `CORS_ALLOW_ORIGINS`
  is not needed at all in this mode.

If you deliberately bypass the proxy by pointing
`NEXT_PUBLIC_API_BASE_URL` straight at `http://<laptop-ip>:5000`, then you
*do* need Flask reachable on the LAN and you *do* need the exact origin in
`CORS_ALLOW_ORIGINS`.

---

## 8. API reference

Every route below exists in `app.py`. All JSON responses carry a `status`
field; errors are `{"error": "...", "code": "..."}` with a machine-readable
code.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Legacy server-rendered staff page. |
| GET | `/uploads/<filename>` | Serves a stored capture. |
| POST | `/analyze` | `multipart/form-data`: `image` (required), `station`, `ward`. Runs the full pipeline, writes an audit event. |
| POST | `/verify` | JSON `{event_id, actual_route, station?, ward?}`. Operator confirmation → compliance verdict. |
| GET | `/events?limit=&offset=` | Audit event list, newest first. |
| GET | `/events/<event_id>` | One audit event. |
| GET | `/analytics` | Aggregations for the dashboard. |
| GET | `/facility/wards` | Configured wards. **The single source of truth for the ward selector.** |
| GET | `/operations` | Bin overview + simulated capacity + active collection job summary. |
| GET | `/operations/bins` | Bins only. |
| GET | `/operations/bins/<bin_id>` | One bin. |
| GET | `/disposal/definition?route=` | Workflow *definition* for a route. Step counts vary — always read them from here. |
| POST | `/disposal/jobs` | JSON `{bin_id}`. Starts, or resumes, a collection job. |
| GET | `/disposal/jobs` | Collection jobs. |
| GET | `/disposal/jobs/<job_id>` | One collection job with its step state. |
| GET | `/disposal/jobs/<job_id>/events` | The frozen event snapshot for that job. Read-only. |
| POST | `/disposal/jobs/<job_id>/steps/<step_id>/complete` | Advance a collection job. |
| GET | `/disposal/<event_id>` | Per-event disposal workflow state. |
| POST | `/disposal/<event_id>/steps/<step_id>/complete` | Advance a per-event workflow. |
| GET | `/policy` | Policy version, streams, thresholds, rules. |
| GET | `/health` | Liveness + capability booleans + feature metadata + audit event count. |

### Error codes you will actually see

`/analyze` — `400 NO_IMAGE`, `400 EMPTY_FILENAME`, `415 UNSUPPORTED_TYPE`
(only `.jpg`, `.jpeg`, `.png`), `400 INVALID_IMAGE`, `400 INVALID_WARD`,
`503 VISION_UNAVAILABLE`, `500 ANALYSIS_FAILED`, and `413` when the upload
exceeds `MAX_UPLOAD_MB`.

`/verify` — `400 MISSING_EVENT_ID`, `400 INVALID_WARD`, `404 EVENT_NOT_FOUND`.

Workflows — `404 UNKNOWN_STEP`, `409 ALREADY_COMPLETE`, `409 OUT_OF_ORDER`.

Collection jobs — `409 NO_ELIGIBLE_EVENTS` (and in that case **nothing is
created**). Starting a job for a bin that already has one in progress returns
`200` with `resumed: true`; a genuinely new job returns `201` with
`resumed: false`.

`/health` never reveals secret values. It reports booleans only:
`roboflow_configured`, `pinecone_configured`, `openrouter_configured`, plus
non-secret identifiers (`model_ref`, `pinecone_index`, `openrouter_model`),
`cors_enabled`, `features.disposal_workflow_steps`,
`features.operations_bins: "SIMULATED"`, and `audit_events`.

---

## 9. Policy: streams, statuses, thresholds

`policy_engine.py` — `POLICY_VERSION = "1.1.0"`.

| Stream code | Waste class |
| --- | --- |
| `YELLOW` | Infectious |
| `RED` | Sharps |
| `BLUE` | Recyclable |
| `WHITE` | Chemical |
| `BROWN` | Pharmaceutical |
| `BLACK` | General |
| `RADIOACTIVE_STORAGE` | Radioactive |

Static rules: `R-SHARPS`, `R-INFECTIOUS`, `R-RADIOACTIVE`, `R-PHARMA`,
`R-CHEMICAL`, `R-RECYCLABLE`, `R-GENERAL`. Every decision carries the rule id
and the policy version, and the events UI shows
*"Decided by policy `<rule_id>` · v`<policy_version>`"*.

Confidence handling: at or above `POLICY_ACCEPT_THRESHOLD` (0.40) the route is
accepted; between `POLICY_REVIEW_FLOOR` (0.20) and the accept threshold the
event becomes `REVIEW_REQUIRED`; below the floor there is no expected route.
Gloves/PPE are treated as *context* items, not as the waste subject.

Compliance verdicts from `verify_compliance()`:

* `PENDING_VERIFICATION` — analysed, operator has not confirmed yet.
* `CORRECT` — confirmed route matches the expected route.
* `VIOLATION` — confirmed route differs from the expected route.
* `REVIEW_REQUIRED` — no expected route to compare against
  (`NO_EXPECTED_ROUTE`). Escalate to a human.
* `INVALID_ROUTE` — the submitted route is not a known stream
  (`UNKNOWN_ROUTE`).

Wards come from `facility.py`. Defaults: `ER`, `ICU-1`, `ICU-2`, `OT-1`,
`WARD-A`, `LAB`, `OPD`. An absent ward is allowed; an *unconfigured* ward is
rejected with `400 INVALID_WARD`. There is no default ward.

---

## 10. Disposal workflows — read from the backend, not invented

`disposal.py`, `WORKFLOW_VERSION = "2.0.0"`. The declared provenance is:
*"Facility workflow definition (exhibition prototype). Route-specific steps are
derived from the stream handling descriptions in `policy_engine.STREAMS`; no
external regulation is cited or invented."* Say that out loud if a judge asks
which standard it implements.

Step lists differ per route. **The frontend never hardcodes a step count** —
it reads `/disposal/definition?route=...`.

| Route | Steps | Count |
| --- | --- | --- |
| Generic (`YELLOW`, `BLUE`, `WHITE`, `BLACK`) | segregate → secure → seal_label → collection → treatment | 5 |
| `RED` (sharps) | segregate → secure → **puncture_proof** → seal_label → collection → treatment | 6 |
| `BROWN` (pharmaceutical) | segregate → secure → **quarantine** → seal_label → collection → treatment | 6 |
| `RADIOACTIVE_STORAGE` | segregate → secure → seal_label → **shielded_storage** → **decay_release** | 5, and there is no treatment step |

Steps must be completed in order: out of sequence → `409 OUT_OF_ORDER`,
already done → `409 ALREADY_COMPLETE`, unknown id → `404 UNKNOWN_STEP`.

### Collection jobs (`collection.py`)

A collection job models one housekeeping round over a *bin*, not one item.

* On start, eligibility is **snapshotted**: audit events matching that bin's
  route that are not already attached to any job. That snapshot is frozen for
  the life of the job.
* No eligible events → `409 NO_ELIGIBLE_EVENTS`, and no job is created.
* A bin with a job already `IN_PROGRESS` resumes it (`200`, `resumed: true`)
  rather than creating a duplicate.
* Completing the final step sets `status: COMPLETED` and `completed_at`.
* `/disposal/jobs/<job_id>/events` is read-only. Collection never mutates a
  compliance verdict.

### Bin capacity is simulated (`operations.py`)

`DATA_SOURCE = "SIMULATED"`, `sensing: "none"`, nominal capacity `100`,
`capacity_basis: "pending_collection_count"`. Fill is derived **only** from how
many events are pending collection, and it is exactly `0%` when nothing is
pending. Status bands: `CRITICAL` ≥ 90, `HIGH` ≥ 75, `MODERATE` ≥ 40, else
`OK`. Bin states: `EMPTY` ("No items pending collection"),
`PENDING_COLLECTION` ("Awaiting collection"), `IN_PROGRESS` ("Collection in
progress"), `AWAITING_NEXT_CYCLE` ("Collected · awaiting next cycle").

The backend ships the disclaimer verbatim: *"Bin fill levels are SIMULATED for
the exhibition. No physical bin sensor, IoT device, weight cell, or RFID is
used."* Keep it on screen.

---

## 11. Phone on the same Wi-Fi (plain HTTP) — and why it isn't enough

Find the laptop's LAN address:

```powershell
ipconfig
```

Use the IPv4 address of the adapter that is actually on the Wi-Fi the phone is
joined to. Then serve the frontend on all interfaces:

```powershell
cd MediWaste_AI\frontend
npm run dev:lan
```

Allow Node through the Windows firewall when prompted (Private networks). The
phone can now open `http://<laptop-ip>:3000` and the whole app works —
navigation, operations, workflows, events, dashboard — because API traffic goes
through the same-origin `/backend` proxy (§7).

**But the camera will not open.** Browsers only expose `getUserMedia()` in a
*secure context*: HTTPS, or `localhost`. `http://192.168.x.x:3000` is neither.
That is a browser rule, not a bug in this app, and the scan screen falls back
to file upload so the demo still functions.

Do **not** work around this by disabling browser security flags. To get a real
phone camera you need HTTPS on the LAN — §12 and §13.

If instead you bypass the proxy and point the phone directly at Flask, remember
that `python app.py` is loopback-only. Exposing Flask on the LAN needs the
Flask CLI:

```powershell
flask --app app run --host=0.0.0.0 --port=5000
```

…and the phone's exact origin added to `CORS_ALLOW_ORIGINS`. The proxy route is
simpler and is the supported path.

---

## 12. mkcert on Windows — the section that actually goes wrong

**This section is critical.** Read it before you start, not after it fails.

### 12.1 Install

```powershell
winget install FiloSottile.mkcert
```

### 12.2 Do NOT assume mkcert is available after WinGet says it installed

This is the failure everyone hits. WinGet reports success — or reports that the
package is *already installed* — and then:

```
mkcert : The term 'mkcert' is not recognized as the name of a cmdlet, function,
script file, or operable program.
```

WinGet installed the binary but your current PowerShell session's `PATH` does
not contain it. **First, open a brand-new PowerShell window** — `PATH` changes
do not apply to already-open sessions. Then check:

```powershell
where.exe mkcert
```

If that prints a path, you are done; use `mkcert` directly. If it prints
nothing, find the executable:

```powershell
Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter "mkcert.exe" -Recurse -ErrorAction SilentlyContinue
```

`$env:LOCALAPPDATA` is used deliberately so this works for any Windows user —
**never hardcode a username, and never hardcode a version-specific WinGet
package directory**, because the folder name contains a version hash that
changes between releases.

### 12.3 Running it from the full path: the `&` call operator

PowerShell will not execute a quoted string as a command. `"C:\...\mkcert.exe"`
on its own is just text. `&` (the call operator) tells PowerShell to *invoke*
it, which is what makes paths containing spaces work:

```powershell
$mkcert = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter "mkcert.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
& $mkcert -version
```

### 12.4 Optional: make it permanent for your user only

If you would rather type `mkcert` than `& $mkcert`, append its directory to your
*user* `PATH` (not the machine `PATH`, and without wiping what is already
there):

```powershell
$dir = Split-Path $mkcert -Parent
$current = [Environment]::GetEnvironmentVariable("Path", "User")
if ($current -notlike "*$dir*") {
  [Environment]::SetEnvironmentVariable("Path", "$current;$dir", "User")
}
```

Then **close and reopen PowerShell**. Verify with `where.exe mkcert`.

### 12.5 Trust the local CA and generate the certificate

```powershell
& $mkcert -install
```

Now generate a certificate for the exact hostnames the browser will be typing.
Substitute your real LAN IPv4 from `ipconfig`:

```powershell
cd MediWaste_AI\frontend
New-Item -ItemType Directory -Force -Path .\certs | Out-Null
cd .\certs
& $mkcert -key-file lan-key.pem -cert-file lan-cert.pem 192.168.1.14 localhost 127.0.0.1 ::1
```

Rules for this command:

* Replace `192.168.1.14` with **your** address. It is an example, not a
  constant.
* **Never put `0.0.0.0` in the certificate.** It is a bind-all wildcard for
  the server socket, not a hostname a browser ever connects to, and including
  it does nothing useful.
* If the laptop's IP changes — different Wi-Fi, DHCP lease — the certificate no
  longer matches and you must regenerate it. Do this *before* you walk into the
  exhibition hall, on the network you will actually use.
* The filenames matter: `npm run dev:https` looks for
  `./certs/lan-key.pem` and `./certs/lan-cert.pem` exactly.

**`lan-key.pem` is a private key. It must never be committed.** Both the root
`.gitignore` and `frontend/.gitignore` already exclude `*.pem`, `*.key`,
`*.crt`, `*.cer`, `*.pfx`, `*.p12` and `frontend/certs/*` while keeping
`frontend/certs/README.md`. Do not weaken those rules, and never commit `.env`,
a private key, or a certificate.

### 12.6 Serve the frontend over HTTPS

```powershell
cd MediWaste_AI\frontend
npm run dev:https
```

That runs Next's built-in dev TLS:
`next dev -H 0.0.0.0 -p 3000 --experimental-https --experimental-https-key ./certs/lan-key.pem --experimental-https-cert ./certs/lan-cert.pem`

Open `https://<laptop-ip>:3000` on the phone.

**Important limitation:** this is a *dev-server* feature. `next start` has no
HTTPS support, so `npm run start` / `npm run start:lan` serve plain HTTP only.
For the exhibition, run the HTTPS dev server. That is a deliberate, documented
trade-off, not an oversight.

---

## 13. Being honest about phone trust

`mkcert -install` trusts the local CA **on the laptop**. It does **not**
automatically make every phone trust that CA. Expect the phone to show a
certificate warning the first time.

What actually works, in order of reliability:

1. **Demo on the laptop.** `http://localhost:3000` is a secure context, so the
   laptop webcam works with no certificates at all. This is the most reliable
   demo and it should be your fallback.
2. **Phone over HTTPS with the mkcert root CA installed on the phone.** Export
   the mkcert root CA (`& $mkcert -CAROOT` shows the folder containing
   `rootCA.pem`), transfer it to the phone, and install it as a user
   certificate. This works, but Android's handling of user-installed CAs is
   inconsistent across OEMs, Android versions, and browsers — some builds trust
   it in Chrome, some do not, some require the CA to be installed under a
   specific settings path. Test on the actual phone before the exhibition.
3. **Phone over plain HTTP.** Everything works except the camera; the scan
   screen falls back to file upload. Acceptable as a navigation demo.

Rules that do not bend:

* **Never disable browser security** to get past a certificate warning. Not
  `--ignore-certificate-errors`, not `chrome://flags` unsafe-origin overrides,
  not clock changes.
* **Never present an untrusted HTTP camera setup as a reliable final
  solution.** If the phone camera is not working through a trusted HTTPS
  origin, say so and demo on the laptop instead.

The scan screen shows a QR code for LAN handoff on desktop viewports only, and
it suppresses that QR when the page is being served from loopback — a QR
pointing at `localhost` would be useless on a phone. The QR target is derived
from the browser's own `window.location`, so it always matches however you are
actually serving the app.

---

## 14. The exhibition run-through (judge-friendly, ~4 minutes)

Have both terminals already running before anyone walks up.

**1. Scan (`/scan`) — 60 s.**
Pick a ward from the selector (populated from `/facility/wards`, never
hardcoded). Capture or upload an item. The screen walks visibly through the
analysis pipeline, so the judge sees *stages*, not a spinner. Say: "the model
identifies the waste item — it never looks at a bin."

If you have no physical waste to hand, the repo ships demo images at
`static/samples/sample1.jpg` … `sample5.jpg`, reachable while Flask is running
at `http://127.0.0.1:5000/static/samples/sample1.jpg`.

**2. Result + "Why this route?" — 60 s.**
The result shows the expected stream and its colour. Open **Why this route?**:
the rule id and policy version, the retrieved guideline evidence, and the
handling guidance. Say: "the decision came from the rule engine. The retrieved
passages justify it; the language model only phrases it."

**3. Confirm the actual bin — 30 s.**
Press the colour the operator *actually* used. A confirmation beep fires after
the verification call returns. Deliberately press the wrong colour once — that
is how you demonstrate a `VIOLATION` being recorded honestly.

**4. Operations (`/operations`) — 45 s.**
Bins, states, and simulated capacity. Point at the *"Exhibition mode ·
Simulated capacity"* disclaimer yourself before anyone asks. Press **Start
disposal** on a bin that has pending items to open the collection job.

**5. Disposal workflow — 45 s.**
Step through the ordered checklist. Note that sharps (`RED`) has a
puncture-proof step and pharmaceutical (`BROWN`) has a quarantine step, so
the workflow length is route-specific and comes from the backend.

**6. Events (`/events`) and Dashboard (`/dashboard`) — 45 s.**
The audit trail per event: ward, station, detected category, confidence,
expected route, bin actually used, model reference, RAG status, explanation
status, reason code, and the deciding rule. Then the dashboard: compliance
performance, violations by waste type, violations by route, ward performance.
Close with: "every number on this dashboard traces back to a specific audit
event."

---

## 15. Tests and validation

Four distinct tools, with different requirements. Only run what you need.

**Offline suite — no network, no pytest needed.**

```powershell
python tests\run_offline.py
```

A stdlib-only runner over the 15 test modules in `tests/`. It resets the audit
database between tests and *skips* tests that require pytest fixtures, printing
the reason. This was executed during development and reported
`passed=116 failed=0 errored=0 skipped=1` on Python 3.10.

**Full suite — needs pytest installed.**

```powershell
pip install pytest
python -m pytest -q
```

`pytest` is not in `requirements.txt`, so install it explicitly if you want the
fixture-based tests too.

**Integration probe — needs real API keys and outbound network.**

```powershell
python verify_integrations.py
```

Read-only. Checks config, core pipeline, the grounding gate, Pinecone,
OpenRouter and Roboflow. It prints booleans and never prints secret values. It
exits `0` only when the core pipeline and the grounding gate are healthy, so a
degraded Pinecone or OpenRouter does not by itself fail the run.

**Live end-to-end — spawns the real server.**

```powershell
python validate_live.py
```

Starts `app.py` on `VALIDATE_PORT` (default `5057`) and prints an A–H report.
Exits `0` only if every required live check passes. Needs keys and network.

**Frontend checks.**

```powershell
cd MediWaste_AI\frontend
npx tsc --noEmit
npm run lint
npm run build
```

---

## 16. Graceful degradation — what breaks what

| Missing / down | What happens | Does the compliance decision survive? |
| --- | --- | --- |
| `PINECONE_API_KEY` or Pinecone unreachable | RAG reports `UNAVAILABLE` with an empty evidence list. No passage is ever fabricated; absent fields are `null`. | **Yes.** |
| `OPENROUTER_API_KEY` or OpenRouter unreachable / timeout | Explanation reports `UNAVAILABLE`. | **Yes.** |
| CLIP / torch unavailable | Visual context is absent. It was only ever an estimate. | **Yes.** |
| `ROBOFLOW_API_KEY` missing | `/analyze` returns `503 VISION_UNAVAILABLE`. There is nothing to decide about. | No image, no decision. |
| Detection confidence below the review floor | Event becomes `REVIEW_REQUIRED`. | Yes — the system escalates rather than guessing. |

The point worth making to a judge: **RAG or LLM degradation does not invalidate
the deterministic decision.** The rule engine produced the route before either
of them ran. When evidence is unavailable you lose the *citation* and the
*prose*, not the correctness or the audit trail. The UI surfaces RAG status and
explanation status per event precisely so degradation is visible instead of
silently papered over.

---

## 17. Troubleshooting

**`mkcert` not recognised** → §12.2. New shell, `where.exe mkcert`, then the
recursive `Get-ChildItem` search and the `&` call operator.

**Phone camera does not open** → you are on plain HTTP. Only a secure context
gets `getUserMedia()`. Use `npm run dev:https` (§12.6) or demo on the laptop.
Do not disable browser security.

**Certificate warning on the phone** → expected; the phone does not trust the
laptop's local CA. §13.

**Phone cannot reach the laptop at all** → check both devices are on the same
Wi-Fi (guest/AP-isolated networks block this entirely), that you used
`npm run dev:lan` or `npm run dev:https` rather than `npm run dev`, and that
Windows Firewall allowed Node on Private networks.

**Blocked mixed-content or CORS errors in the console** → confirm
`NEXT_PUBLIC_API_BASE_URL=/backend` and `BACKEND_ORIGIN` are set in
`frontend/.env.local`, and restart the dev server — Next reads env files at
startup. If you deliberately bypassed the proxy, add the exact browser origin
to `CORS_ALLOW_ORIGINS`; it is an exact `scheme://host:port` match, with no
wildcards.

**Pinecone import errors** → §4, the uninstall/reinstall pair.

**`413` on upload** → the image exceeds `MAX_UPLOAD_MB` (default 10). **`415`**
→ only `.jpg`, `.jpeg`, `.png` are accepted. **`400 INVALID_WARD`** → the ward
is not in the configured list; check `/facility/wards`.

**Port already in use** → change `PORT` for Flask, or run
`npm run dev -- -p 3001` for the frontend.

---

## 18. Resetting local demo state (destructive — read first)

These paths were checked against the repository. The audit database lives at
`audit.db` beside `app.py`, unless you overrode `AUDIT_DB_PATH` — in which case
delete *that* file instead. SQLite also leaves `audit.db-wal` and `audit.db-shm`
alongside it.

> **Warning.** Deleting the audit database **permanently removes all local demo
> history**: every scanned event, every compliance verdict, every collection
> job, and therefore everything the dashboard and events pages display. There is
> no undo and no backup. Do not do this in front of judges, and do not do it if
> you still need the history you built up.

Stop the Flask server first, then:

```powershell
cd MediWaste_AI
Remove-Item .\audit.db, .\audit.db-wal, .\audit.db-shm -ErrorAction SilentlyContinue
```

Stored captures (referenced by audit events — removing them leaves events with
broken image links):

```powershell
Remove-Item .\uploads\* -Exclude .gitkeep -ErrorAction SilentlyContinue
```

Frontend build cache, if Next starts behaving strangely:

```powershell
cd MediWaste_AI\frontend
Remove-Item -Recurse -Force .\.next -ErrorAction SilentlyContinue
```

Certificates, if the laptop's IP changed (then regenerate per §12.5):

```powershell
Remove-Item .\certs\lan-key.pem, .\certs\lan-cert.pem -ErrorAction SilentlyContinue
```

Never edit `audit.db` by hand, never delete individual audit events, and never
change an event's `compliance_status` outside the `/verify` flow. The audit
trail's only value is that it is not editable to taste.

---

## 19. Security rules

* `.env` is gitignored. **Never commit it.** Never paste secret values into
  chats, issues, slides, screenshots, or logs.
* `lan-key.pem` is a private key. **Never commit it.** `*.pem`, `*.key`,
  `*.crt`, `*.cer`, `*.pfx`, `*.p12` and `frontend/certs/*` are already
  excluded in `.gitignore`; leave those rules alone.
* `/health` reports capability **booleans** and non-secret identifiers only. Do
  not extend it to echo key material.
* CORS is opt-in and exact-match. There is no wildcard mode; do not add one.
* Uploads are constrained by extension (`.jpg`, `.jpeg`, `.png`), decoded to
  validate, and size-capped by `MAX_UPLOAD_MB`.
* There is **no authentication** in this prototype. Do not expose it beyond a
  trusted LAN, and do not put real patient data through it.
* Never disable browser security to make a demo work.

---

## 20. Known limitations

Stated plainly, because a prototype that knows its own edges is worth more than
one that pretends:

* No bin detection. The camera classifies the waste item; the bin is operator
  input.
* No authentication, no user accounts, no role separation.
* Bin capacity is simulated from pending-collection counts. No sensors of any
  kind — no IoT, no weight cells, no fill sensors, no RFID.
* No continuous video inference; one still image per decision.
* No ERP, HIS, or waste-contractor integration.
* Workflow definitions are an exhibition prototype derived from the stream
  handling descriptions in `policy_engine.STREAMS`. They cite no external
  regulation.
* The RAG corpus is a single guideline document already indexed in Pinecone.
  This repository contains no ingestion or re-indexing script and never writes
  to the index.
* HTTPS is available through the Next **dev** server only; `next start` cannot
  serve TLS.
* Single-node SQLite. Fine for a demo, not a multi-site deployment.
* The audit trail is tamper-*evident* by convention and discipline, not
  cryptographically sealed.

---

## 21. Command reference

Every command below exists in this repository. Nothing else is claimed.

Backend, from the repository root with the venv active:

| Command | What it does |
| --- | --- |
| `python app.py` | Run Flask on `PORT` (default 5000), loopback only. |
| `flask --app app run --host=0.0.0.0 --port=5000` | Run Flask reachable on the LAN. Needs `CORS_ALLOW_ORIGINS` if you bypass the `/backend` proxy. |
| `python tests\run_offline.py` | Stdlib-only offline test suite. |
| `python -m pytest -q` | Full suite. Requires `pip install pytest`. |
| `python verify_integrations.py` | Read-only integration probe. Needs keys + network. |
| `python validate_live.py` | Spawns the app on `VALIDATE_PORT` and runs A–H live checks. |

Frontend, from `frontend/`:

| Command | Underlying script |
| --- | --- |
| `npm ci` | Reproducible install from `package-lock.json`. |
| `npm run dev` | `next dev` — laptop only, `http://localhost:3000`. |
| `npm run dev:lan` | `next dev -H 0.0.0.0 -p 3000` — LAN over HTTP, no phone camera. |
| `npm run dev:https` | LAN over HTTPS using `./certs/lan-key.pem` + `./certs/lan-cert.pem`. Phone camera works if the phone trusts the CA. |
| `npm run build` | `next build`. |
| `npm run start` | `next start` — HTTP only. |
| `npm run start:lan` | `next start -H 0.0.0.0 -p 3000` — HTTP only. |
| `npm run lint` | `next lint`. |
| `npx tsc --noEmit` | Type check. |

---

## 22. Further reading in this repository

`ENGINEERING_REPORT.md`, `P0_HARDENING_REPORT.md`,
`FINAL_DEMO_HARDENING_REPORT.md` and
`MediWaste_AI_Final_Report_BrainChild_Season_2.pdf` record the engineering
history and the hardening decisions. `pitch.md` is the narrative pitch.
`frontend/README.md` covers frontend-specific notes and `frontend/certs/README.md`
covers the certificate directory.

Built for BrainChild 2.0 — a deterministic compliance engine with AI on the
outside, and an audit trail that means what it says.


















