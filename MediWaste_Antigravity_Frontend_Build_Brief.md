# MediWaste AI — Antigravity Frontend Build Brief

## Mission

Build the final exhibition-grade **Next.js frontend** for MediWaste AI.

The Flask backend is already implemented and live-validated:

- 94 pytest tests passed
- `validate_live.py` → **BACKEND READY FOR NEXT.JS**
- Roboflow: `medbin_dataset-fqhi7/1`
- Pinecone: `brainchild`
- OpenRouter: `openai/gpt-oss-120b`

**Do not redesign or reimplement backend business logic.** The frontend's job is to make the existing depth immediately visible to a hackathon judge.

The product story is:

```text
SCAN
→ AI DETECTION
→ NORMALIZATION
→ EXPECTED ROUTE
→ ACTUAL ROUTE
→ CORRECT / VIOLATION
→ WHY?
→ EVIDENCE + GROUNDED AI EXPLANATION
→ AUDIT
→ BIN OPERATIONS
→ COLLECTION REQUIRED
→ 5-STEP DISPOSAL WORKFLOW
```

---

# 1. Core UX Principle

There are two audiences.

### Staff

Staff should not need to understand RAG, embeddings, LLMs, or policy internals.

Show:

- what was detected
- which bin to use
- whether the action is correct
- what to do next
- which disposal step is active

Use large labels, bin visuals, progress indicators, check marks, warnings, and short instructions.

### Supervisor / Judge

Expose:

- policy
- evidence
- RAG provenance
- AI explanation
- audit trail
- model/version metadata
- analytics

**Staff sees “What should I do?”; supervisor/judge can open “Why?”**

---

# 2. Navigation

Create:

```text
MediWaste AI

[ Scan ] [ Operations ] [ Dashboard ] [ Events ]
```

Visual direction:

- modern hospital operations / clinical command center
- dark navy background
- blue/cyan primary accent
- green = compliant
- red = violation
- amber = warning/review
- purple = evidence/intelligence
- strong typography
- subtle borders/shadows
- restrained animation

Avoid excessive gradients, glassmorphism, glowing effects, or gaming-style decoration.

---

# 3. Scan Page — Main Hero

Default route should be the Scan/Analyze experience.

Desktop layout:

```text
┌──────────────────────────────────────────────────────────────┐
│ MediWaste AI                              Operations  Events │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ CAMERA / IMAGE                         LIVE DECISION         │
│ ┌──────────────────┐              ┌────────────────────────┐ │
│ │                  │              │ PHARMACEUTICAL         │ │
│ │  Image / Camera  │              │                        │ │
│ │                  │              │ 96% confidence         │ │
│ └──────────────────┘              │                        │ │
│                                   │ REQUIRED ROUTE         │ │
│ [ Capture ] [ Upload ]            │       🟤 BROWN         │ │
│                                   └────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

Use real backend:

`POST /analyze`

Support:

- JPG/PNG upload
- browser camera via `getUserMedia`
- still-image capture
- upload fallback

**Do not implement continuous video inference.**

---

# 4. Detection Result

Show prominently:

```text
DETECTED

PHARMACEUTICAL

Drug Packaging

96.0%

Confidence
━━━━━━━━━━━━━━━━━━━━
```

If multiple predictions exist, show them compactly.

Provide optional “Technical details” expansion rather than overwhelming staff.

---

# 5. Expected Disposal Route

Make this visually dominant:

```text
EXPECTED DISPOSAL ROUTE

        🟤
      BROWN

  PHARMACEUTICAL

Policy: R-PHARMA v1.1.0
```

The route must come from the backend. Do not hardcode route decisions in Next.js.

---

# 6. Actual Route Verification

Prompt:

> **Where was this waste actually placed?**

Show large bin choices:

```text
🟡 YELLOW     Infectious
🔴 RED        Sharps
🟤 BROWN      Pharmaceutical
⚫ BLACK      General
⚪ WHITE      Chemical
☢ RADIOACTIVE
```

Call:

`POST /verify`

The backend is the source of truth.

Do not duplicate compliance logic in frontend code.

---

# 7. Correct State

```text
✓ COMPLIANT DISPOSAL

Expected       Actual
🟤 BROWN       🟤 BROWN

Waste was routed correctly.

[ View Evidence ] [ View Audit ]
```

Use a short professional success animation.

---

# 8. Violation State

Make wrong disposal immediately obvious:

```text
🚨 SEGREGATION VIOLATION

Expected
🟤 BROWN

Actual
🟡 YELLOW

WRONG_WASTE_STREAM

[ Why is this wrong? ]
[ Show Correct Route ]
```

Never use vague messages such as “Something went wrong.”

---

# 9. Review Required

For low confidence or unknown classes:

```text
⚠ REVIEW REQUIRED

The system is not confident enough
to make an automated disposal decision.

Reason: LOW_CONFIDENCE

[ Send for Review ]
```

Never turn uncertainty into a definitive disposal instruction.

---

# 10. Why This Route?

Use a drawer/modal/expandable section.

```text
WHY THIS ROUTE?

Policy
R-PHARMA v1.1.0

PHARMACEUTICAL → BROWN
```

Then show real Pinecone evidence.

Evidence card:

```text
Evidence
────────────────────
Source: hospital_guideline.pdf
Evidence ID: xxxxxxxx
Relevance: 0.82

[ Read passage ]
```

Then:

```text
AI EXPLANATION
Powered by GPT-OSS-120B
```

Respect the backend grounding gate.

If evidence is unavailable:

```text
Evidence-grounded explanation unavailable.

The route shown is determined by the
deterministic policy engine.
```

Never fabricate evidence or explanation.

---

# 11. Audit Event

After analysis/verification:

```text
EVENT RECORDED ✓

Detection
PHARMACEUTICAL

Expected
BROWN

Actual
YELLOW

Decision
VIOLATION

Reason
WRONG_WASTE_STREAM

Event ID
b29f4b5c...
```

Link to Events.

---

# 12. Operations Page — Eye-Catching Feature

This page makes the system look like a real hospital operational platform.

Header:

```text
OPERATIONS CENTER

Ward: ICU-A
```

Bin cards:

```text
┌───────────────────────────────┐
│ 🔴 SHARPS                    │
│                               │
│ 91%                            │
│ ██████████████████░░          │
│                               │
│ ⚠ COLLECTION REQUIRED         │
│                               │
│ [ Start Disposal ]            │
└───────────────────────────────┘
```

Other examples:

```text
🟤 PHARMACEUTICAL
44%
✓ NORMAL

🟡 INFECTIOUS
72%
✓ NORMAL

⚪ CHEMICAL
83%
⚠ NEAR CAPACITY
```

Use real:

- `GET /operations`
- `GET /operations/bins`
- `GET /operations/bins/<bin_id>`

---

# 13. Capacity Honesty

Current exhibition backend uses **simulated capacity**.

The UI MUST NOT claim physical sensors.

Display subtly:

```text
Operational Prototype · Simulated Capacity
```

or:

```text
Capacity source: SIMULATED
```

Never claim:

- live IoT
- sensor measured
- RFID detected
- real-time sensor telemetry

Current backend contract:

```text
data_source = SIMULATED
sensing = none
```

Preserve this honesty.

---

# 14. Bin Detail

Click a bin:

```text
SHARPS
ICU-A

91%
COLLECTION REQUIRED

Waste stream
SHARPS

Status
READY FOR COLLECTION

Capacity source
SIMULATED

[ START DISPOSAL WORKFLOW ]
```

---

# 15. Disposal Workflow

The backend already implements a **5-step sequential state machine**.

Use:

```text
GET /disposal/definition
GET /disposal/<event_id>
POST /disposal/<event_id>/steps/<step_id>/complete
```

Do not recreate state-machine authority in frontend.

UI:

```text
DISPOSAL WORKFLOW

✓ 01  SEGREGATE
       Waste separated into correct stream

● 02  SECURE
       Secure the container

○ 03  SEAL & LABEL
       Seal and identify container

○ 04  AUTHORIZED COLLECTION
       Handover to authorized collection

○ 05  TREATMENT / FINAL DISPOSAL
       Complete approved final route

[ COMPLETE STEP ]
```

Current step is visually dominant.

If backend returns `409 OUT_OF_ORDER`, show:

```text
Complete the current step first.
```

Do not expose raw server errors to staff.

Final state:

```text
✓ DISPOSAL COMPLETED

All 5 required steps completed.

Event recorded in audit trail.

[ View Audit Event ]
[ Back to Operations ]
```

---

# 16. Dashboard

The current dashboard concept contains:

```text
Total Events
Correct
Violations
Review Required
Compliance Rate

Compliance Breakdown
Violations by Waste Type
Violations by Disposal Route
Station / Ward Performance
```

Do not leave empty graph containers.

Use:

`GET /analytics`

## KPI row

```text
TOTAL EVENTS
35

CORRECT
11

VIOLATIONS
5

REVIEW REQUIRED
1

COMPLIANCE RATE
68.8%
```

Values must come from backend, never hardcoded.

## Chart 1 — Compliance Breakdown

Use donut chart:

- Correct
- Violation
- Review / Unknown

Center:

```text
68.8%
Compliance
```

## Chart 2 — Violations by Waste Type

Use horizontal bar chart.

Example:

```text
SHARPS          █████████
INFECTIOUS      ██████
PHARMACEUTICAL  ████
CHEMICAL        ██
```

Use actual analytics data.

## Chart 3 — Violations by Disposal Route

Horizontal bar chart:

```text
YELLOW          ███████
RED             █████
BLACK           ███
BROWN           ██
```

Use actual backend data.

## Chart 4 — Station / Ward Performance

Grouped bar chart or ranked table:

```text
Ward        Compliance

ICU-A       ███████████████  91%
Ward-B      █████████████    84%
Ward-C      ███████████      73%
```

If data is sparse, use a ranked table rather than showing an empty chart.

Add loading skeletons, error states, refresh, and empty states.

Do not invent unsupported filters.

---

# 17. Events Page

Create a clean audit timeline:

```text
EVENTS

09:42
PHARMACEUTICAL
✓ CORRECT
ICU-A

09:47
SHARPS
🚨 VIOLATION
Ward-B

09:53
UNKNOWN
⚠ REVIEW REQUIRED
ICU-A
```

Click event for:

- detection
- normalization
- policy
- expected route
- actual route
- compliance
- evidence IDs
- explanation status
- timestamp
- ward
- model version
- policy version

Use:

`GET /events`

`GET /events/<event_id>`

---

# 18. API Client Architecture

Centralize API calls.

Suggested:

```text
src/
  lib/
    api/
      client.ts
      analyze.ts
      verify.ts
      operations.ts
      disposal.ts
      analytics.ts
      events.ts
```

Use typed response models.

Do not scatter `fetch()` throughout components.

Before creating types, inspect the actual Flask response schemas.

---

# 19. Suggested Next.js Structure

```text
app/
  page.tsx
  scan/
    page.tsx
  operations/
    page.tsx
  dashboard/
    page.tsx
  events/
    page.tsx

components/
  layout/
  scan/
  detection/
  compliance/
  evidence/
  operations/
  disposal/
  dashboard/
  events/
  ui/

lib/
  api/
  types/
  utils/
```

Use TypeScript.

---

# 20. Mobile

Desktop is the primary judging view, but mobile is important for the camera demo.

Mobile flow:

```text
CAMERA
 ↓
CAPTURE
 ↓
DETECTION
 ↓
EXPECTED BIN
 ↓
VERIFY
```

Do not try to squeeze the entire desktop dashboard onto a phone.

Camera:

```text
┌────────────────────────┐
│      MediWaste AI      │
│                        │
│      CAMERA VIEW       │
│                        │
│   ┌──────────────┐     │
│   │ TARGET AREA  │     │
│   └──────────────┘     │
│                        │
│       ● CAPTURE        │
└────────────────────────┘
```

Capture a still image and send it to `/analyze`.

Do not fake camera inference.

---

# 21. Loading / Error UX

Use meaningful loading states:

```text
ANALYZING WASTE
Detecting and normalizing...
```

```text
VERIFYING ROUTE
Checking policy compliance...
```

```text
RETRIEVING EVIDENCE
Finding supporting guidance...
```

Errors:

```text
Unable to analyze this image.
Please try another image.
```

```text
Evidence is temporarily unavailable.
The deterministic policy decision remains available.
```

Never expose stack traces or raw exception details.

---

# 22. Demo Samples

Expose existing bundled sample images in Scan:

```text
DEMO SAMPLES
```

Clicking one should still use the real `/analyze` API.

Do not bypass the backend with mocked results.

---

# 23. Critical Constraints

Never:

- move policy logic into frontend
- hardcode expected routes
- hardcode compliance results
- hardcode analytics
- fabricate evidence
- fabricate sensor readings
- fabricate camera inference
- expose API keys
- call Pinecone from browser
- call OpenRouter from browser
- call Roboflow from browser

All secrets remain server-side in Flask.

Frontend talks to Flask only.

---

# 24. Existing API Contract

Inspect actual source code before implementing TypeScript models.

Known endpoints:

```text
GET  /health

POST /analyze
POST /verify

GET  /events
GET  /events/<event_id>

GET  /analytics

GET  /operations
GET  /operations/bins
GET  /operations/bins/<bin_id>

GET  /disposal/definition
GET  /disposal/<event_id>
POST /disposal/<event_id>/steps/<step_id>/complete
```

`/policy` remains the backend source of truth for route/color policy if needed.

---

# 25. Visual Priority

## Scan

1. detected waste
2. confidence
3. expected bin
4. actual route
5. compliance
6. why/evidence
7. technical details

## Operations

1. bin status
2. capacity
3. collection required
4. disposal workflow

## Dashboard

1. compliance rate
2. violations
3. ward performance
4. waste distribution

## Events

1. status
2. route comparison
3. audit provenance

---

# 26. Animation

Use animation only to communicate state:

- scanning pulse
- progress bar
- success check
- violation alert
- disposal step transition
- chart entrance

Avoid distracting motion and decorative effects.

---

# 27. Exact Judge Demo Flow

The frontend should make this sequence extremely smooth:

### 1. Scan

Use phone camera or a demo image.

### 2. Detect

Show:

```text
PHARMACEUTICAL
96%
EXPECTED → BROWN
```

### 3. Deliberately choose wrong bin

Select:

```text
YELLOW
```

### 4. Immediate violation

```text
🚨 VIOLATION

Expected: BROWN
Actual: YELLOW
```

### 5. Explain

Open:

```text
WHY THIS ROUTE?
```

Show policy + real Pinecone evidence + grounded GPT explanation.

### 6. Audit

Show event recorded.

### 7. Operations

Open:

```text
SHARPS
91%
COLLECTION REQUIRED
```

### 8. Disposal

Start 5-step workflow and complete all steps.

### 9. Finish

```text
✓ DISPOSAL COMPLETED
✓ AUDIT RECORDED
```

This should feel like one coherent product story.

---

# 28. Definition of Done

- [ ] Next.js starts cleanly
- [ ] Flask connection works
- [ ] `/analyze` works from UI
- [ ] real Roboflow result displayed
- [ ] expected route comes from backend
- [ ] `/verify` works
- [ ] correct state works
- [ ] wrong route state works
- [ ] violation alert works
- [ ] real evidence displayed
- [ ] grounded explanation only when backend allows
- [ ] events use real API
- [ ] operations use real API
- [ ] simulated capacity explicitly labelled
- [ ] disposal workflow uses backend state
- [ ] five-step ordering enforced by backend
- [ ] dashboard charts use real analytics
- [ ] mobile camera works where permitted
- [ ] upload fallback works
- [ ] loading/error states polished
- [ ] no secrets in client bundle
- [ ] no duplicated backend business logic
- [ ] no hardcoded analytics
- [ ] no fake sensor claims
- [ ] no fake AI/RAG claims
- [ ] responsive desktop/tablet/mobile
- [ ] production build succeeds

---

# 29. Antigravity / Claude Execution Protocol

Before changing code:

1. Inspect the entire existing Flask backend.
2. Inspect every endpoint and actual JSON response.
3. Inspect any existing frontend/package configuration.
4. Confirm the Next.js project structure.
5. Build incrementally.
6. Do not modify backend behavior unless a genuine integration bug exists.
7. After each major page run typecheck/lint/build.
8. Test against the real local Flask API.
9. Test desktop and mobile layouts.
10. Test the complete judge demo flow.
11. Never replace real APIs with mocks just to make the UI appear complete.

If a field is missing, inspect the backend and report the mismatch instead of inventing it.

---

# 30. Final Quality Bar

The final UI must communicate:

> **This is an operational medical-waste compliance system, not just a waste-image classifier.**

The visible architecture should be:

```text
AI PERCEPTION
      ↓
DETERMINISTIC POLICY
      ↓
COMPLIANCE VERIFICATION
      ↓
GROUNDED EXPLANATION
      ↓
AUDITABILITY
      ↓
OPERATIONAL MONITORING
      ↓
DISPOSAL EXECUTION
```

Priorities:

**Clarity > decoration**

**Real API data > mock data**

**Operator usability > technical jargon**

**Visual storytelling > dense information**

**Reliable demo flow > unnecessary features**
