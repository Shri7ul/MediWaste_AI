/* =====================================================================
   MediWaste AI — frontend controller
   Consumes the real backend schema (/analyze, /verify, /events,
   /analytics, /policy). No results are hard-coded; every panel is driven
   by data returned from the deterministic core + best-effort RAG/LLM.
===================================================================== */

"use strict";

const state = {
  eventId: null,
  decision: null,        // authoritative analysis.decision
  primaryItem: null,
  context: {},           // visual-context estimate (for the context/policy note)
  routeMeta: {},         // code -> {code,label,category,hex,bin_asset,...}
  validRoutes: [],
  charts: {},
  verified: false,
  evidenceAll: [],       // every retrieved record (for the "view all" drawer)
  ragStatus: null,
};

const ROUTE_ORDER = ["YELLOW", "RED", "BLUE", "WHITE", "BROWN", "BLACK", "RADIOACTIVE_STORAGE"];

/* ---------------- tiny helpers ---------------- */
const $ = (id) => document.getElementById(id);

function set(id, value) {
  const el = $(id);
  if (el) el.textContent = (value === null || value === undefined || value === "") ? "-" : value;
}
function showEl(el, disp = "block") { if (el) el.style.display = disp; }
function hideEl(el) { if (el) el.style.display = "none"; }
function pct(x) { return (x === null || x === undefined) ? null : (x * 100).toFixed(1) + "%"; }

function applyChip(el, code) {
  if (!el) return;
  const meta = state.routeMeta[code];
  el.textContent = code ? (meta ? meta.label : code) : "-";
  el.style.setProperty("--chip", meta ? meta.hex : "#64748b");
}
function chipEl(code) {
  const span = document.createElement("span");
  span.className = "route-chip";
  applyChip(span, code);
  return span;
}
function humanize(code) {
  return (code || "").replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}
function fmtTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString();
}

/* ---------------- flow ribbon ---------------- */
function markFlow(map) {
  document.querySelectorAll(".flow-step").forEach((el) => {
    const s = el.dataset.step;
    el.classList.remove("done", "active");
    if (map[s] === "active") el.classList.add("active");
    else if (map[s]) el.classList.add("done");
  });
}
function resetFlow() { markFlow({}); }

/* ---------------- view switching ---------------- */
function switchView(view) {
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  const target = $("view-" + view);
  if (target) target.classList.add("active");
  if (view === "dashboard") loadAnalytics();
  if (view === "events") loadEvents();
}

/* ---------------- loading / error ---------------- */
function showLoading(text) { set("loading-text", text || "Working…"); showEl($("loading"), "flex"); }
function hideLoading() { hideEl($("loading")); }
function showError(msg) { const e = $("error"); if (e) { e.textContent = msg; showEl(e); } }
function clearError() { hideEl($("error")); }

/* =====================================================================
   INIT
===================================================================== */
document.addEventListener("DOMContentLoaded", () => {
  // Tabs
  document.querySelectorAll(".tab").forEach((tab) =>
    tab.addEventListener("click", () => switchView(tab.dataset.view)));

  // File preview
  const input = $("image");
  input.addEventListener("change", function () {
    const f = this.files[0];
    if (f) previewFile(f);
  });

  // Drag & drop + click-to-open
  const box = $("upload-box");
  box.addEventListener("click", (e) => { if (e.target.tagName !== "INPUT") input.click(); });
  ["dragover", "dragenter"].forEach((ev) =>
    box.addEventListener(ev, (e) => { e.preventDefault(); box.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((ev) =>
    box.addEventListener(ev, (e) => { e.preventDefault(); box.classList.remove("dragover"); }));
  box.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files[0];
    if (f) { input.files = e.dataTransfer.files; previewFile(f); }
  });

  loadPolicy();
  loadDemoSamples();
});

function previewFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => { const p = $("preview"); p.src = e.target.result; showEl(p); };
  reader.readAsDataURL(file);
}

/* =====================================================================
   POLICY (colour guide + route selector) — single source of truth
===================================================================== */
async function loadPolicy() {
  try {
    const r = await fetch("/policy");
    const d = await r.json();
    if (d.status !== "ok") return;
    state.routeMeta = d.route_meta || {};
    state.validRoutes = d.valid_routes || [];
    renderColorGuide();
    populateRouteSelect();
  } catch (_e) { /* colour guide simply stays empty */ }
}

function renderColorGuide() {
  const wrap = $("color-guide");
  if (!wrap) return;
  wrap.innerHTML = "";
  const codes = ROUTE_ORDER.filter((c) => state.routeMeta[c]);
  codes.forEach((code) => {
    const m = state.routeMeta[code];
    const cell = document.createElement("div");
    cell.className = "bin-cell";
    cell.style.setProperty("--chip", m.hex);
    let visual;
    if (m.bin_asset) {
      visual = `<img src="/static/assets/${m.bin_asset}" alt="${m.label} bin">`;
    } else {
      visual = `<div class="bin-swatch"><i class="fa-solid fa-radiation"></i></div>`;
    }
    cell.innerHTML = `${visual}<p><b>${m.label}</b>${m.category}</p>`;
    wrap.appendChild(cell);
  });
}

function populateRouteSelect() {
  const sel = $("actual-route");
  if (!sel) return;
  const first = sel.options[0];
  sel.innerHTML = "";
  sel.appendChild(first || new Option("Select actual route…", ""));
  state.validRoutes.forEach((code) => {
    const m = state.routeMeta[code];
    sel.appendChild(new Option(m ? `${m.label} — ${m.category}` : code, code));
  });
}

/* =====================================================================
   DEMO SAMPLES (real images -> real analysis, never fake results)
===================================================================== */
async function loadDemoSamples() {
  const wrap = $("demo-samples");
  if (!wrap) return;
  try {
    const r = await fetch("/static/samples/manifest.json");
    if (!r.ok) throw new Error("no manifest");
    const d = await r.json();
    const samples = d.samples || [];
    if (!samples.length) { hideEl($("demo-samples").parentElement); return; }
    samples.forEach((s) => {
      const img = document.createElement("img");
      img.src = "/static/samples/" + s.file;
      img.className = "demo-thumb";
      img.title = s.label + " — click to analyze";
      img.alt = s.label;
      img.addEventListener("click", () => runDemoSample(s.file, s.label));
      wrap.appendChild(img);
    });
  } catch (_e) {
    hideEl($("demo-samples").parentElement); // no demo assets -> hide the row
  }
}

async function runDemoSample(file, label) {
  try {
    showLoading("Loading sample…");
    const resp = await fetch("/static/samples/" + file);
    const blob = await resp.blob();
    const f = new File([blob], file, { type: blob.type || "image/jpeg" });
    previewFile(f);
    // Reflect the sample in the file input so re-analyze uses the same image.
    const dt = new DataTransfer();
    dt.items.add(f);
    $("image").files = dt.files;
    await analyzeImage();
  } catch (_e) {
    hideLoading();
    showError("Could not load demo sample.");
  }
}

/* =====================================================================
   ANALYZE
===================================================================== */
async function analyzeImage() {
  const file = $("image").files[0];
  if (!file) { showError("Please select an image first."); return; }
  clearError();
  showLoading("Analyzing waste image…");

  const form = new FormData();
  form.append("image", file);
  const station = ($("station").value || "").trim();
  if (station) form.append("station", station);

  try {
    const resp = await fetch("/analyze", { method: "POST", body: form });
    const data = await resp.json();
    hideLoading();
    if (data.status !== "ok") { showError(data.error || "Analysis failed."); return; }
    renderAnalyze(data);
  } catch (_e) {
    hideLoading();
    showError("Backend connection failed.");
  }
}

function renderAnalyze(data) {
  const a = data.analysis || {};
  state.eventId = data.event_id;
  state.decision = a.decision || {};
  state.primaryItem = (a.primary || {}).item || null;
  state.context = a.context || {};
  state.verified = false;
  if (a.route_meta) state.routeMeta = a.route_meta;
  if (a.valid_routes) { state.validRoutes = a.valid_routes; populateRouteSelect(); }

  if (data.image_url) { const p = $("preview"); p.src = data.image_url; showEl(p); }

  renderContext(a.context || {});
  renderDetection(a);
  renderPolicy(a.decision || {}, a.context || {});
  renderMixed(a.mixed_waste || {});
  renderEventBadge(data.event_id);

  // Enable operator verification.
  const sel = $("actual-route"); const btn = $("verify-btn");
  sel.disabled = false; btn.disabled = false; sel.value = "";

  // Compliance is pending until the operator selects the actual route.
  renderHero(a.verification || { status: "PENDING_VERIFICATION",
    expected_route: (a.decision || {}).expected_route, actual_route: null });

  renderExplanation(data.rag, data.explanation, a.decision || {}, a.verification || null);
  renderSystem(data);

  markFlow({ detect: true, expect: true, explain: true, record: true, verify: "active" });
  $("compliance-hero").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderContext(ctx) {
  ["Used", "Contaminated", "Blood", "Chemical"].forEach((k) => {
    const el = $("ctx-" + k);
    if (!el) return;
    const v = ctx[k];
    const conf = ctx[k + "_confidence"];
    el.textContent = v ? (conf !== undefined ? `${v} (${conf})` : v) : "-";
    el.classList.toggle("yes", v === "YES");
    el.classList.toggle("no", v === "NO");
  });
}

function renderDetection(a) {
  const p = a.primary || {};
  set("raw-object", p.raw_class || "-");
  set("item", p.item || "-");
  const c = p.confidence !== undefined && p.confidence !== null ? p.confidence : null;
  set("confidence", c !== null ? pct(c) : "-");
  $("confidence-bar").style.width = c !== null ? (c * 100).toFixed(1) + "%" : "0%";

  const chips = $("all-detections");
  chips.innerHTML = "";
  (a.detections || []).forEach((d) => {
    const el = document.createElement("div");
    el.className = "det-chip";
    el.innerHTML = `<b>${d.item}</b> · ${d.raw_class} · ${pct(d.confidence)}`;
    chips.appendChild(el);
  });
  if (!(a.detections || []).length) {
    chips.innerHTML = `<div class="det-chip">No objects above the review floor.</div>`;
  }
}

function renderMixed(mixed) {
  const el = $("mixed-warning");
  if (mixed && mixed.is_mixed) {
    el.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <b>Mixed waste scene:</b> ` +
      `${(mixed.waste_types || []).join(", ")} across streams ${(mixed.streams || []).join(", ")}. ` +
      `Segregate before disposal.`;
    showEl(el);
  } else { hideEl(el); }
}

function renderPolicy(dec, ctx) {
  ctx = ctx || {};
  const card = $("policy-card");
  const review = dec.status === "REVIEW_REQUIRED";
  card.classList.toggle("review", review);

  set("waste-type", review ? "Manual Review" : (dec.waste_type || "-"));
  applyChip($("expected-chip"), dec.expected_route);

  const status = $("decision-status");
  status.textContent = review ? `Review Required — ${humanize(dec.reason || "")}` : "Route Assigned";
  status.classList.toggle("review", review);

  set("rule-id", dec.rule_id || "-");
  set("policy-version", dec.policy_version ? "policy v" + dec.policy_version : "-");

  const bin = $("bin-image");
  const meta = state.routeMeta[dec.expected_route];
  if (meta && meta.bin_asset) {
    bin.src = "/static/assets/" + meta.bin_asset;
    bin.classList.remove("hidden");
  } else {
    bin.classList.add("hidden");
  }

  // Context/policy consistency note: visual context was asserted but the policy
  // engine derived the route from the canonical waste class (context did not
  // override policy). We never invent a new medical policy from context.
  const applied = dec.context_applied && Object.keys(dec.context_applied).length > 0;
  const ctxAsserted = ["Contaminated", "Blood", "Chemical"].some((k) => ctx[k] === "YES");
  const note = $("context-note");
  if (note) (ctxAsserted && !applied && !review) ? showEl(note) : hideEl(note);
}

function renderEventBadge(eventId) {
  const badge = $("event-badge");
  if (!badge) return;
  if (eventId) {
    badge.textContent = "Event " + String(eventId).slice(0, 8).toUpperCase();
    showEl(badge, "inline-block");
  } else {
    hideEl(badge);
  }
}

/* ---------------- compliance hero ---------------- */
// Titles are uppercased for hero dominance; the coloured icon carries the
// ✓ / 🔴 / ? signal. We NEVER surface the raw "DECIDED" engine state here —
// the hero always shows a real compliance verdict.
const HERO = {
  CORRECT: { cls: "correct", icon: "fa-circle-check", title: "COMPLIANT DISPOSAL" },
  VIOLATION: { cls: "violation", icon: "fa-triangle-exclamation", title: "SEGREGATION VIOLATION" },
  REVIEW_REQUIRED: { cls: "review", icon: "fa-circle-question", title: "REVIEW REQUIRED" },
  PENDING_VERIFICATION: { cls: "pending", icon: "fa-clock", title: "PENDING VERIFICATION" },
  INVALID_ROUTE: { cls: "violation", icon: "fa-ban", title: "INVALID ROUTE SELECTED" },
};

function renderHero(v) {
  const hero = $("compliance-hero");
  const spec = HERO[v.status] || HERO.PENDING_VERIFICATION;
  hero.className = "card hero " + spec.cls;
  $("hero-icon").innerHTML = `<i class="fa-solid ${spec.icon}"></i>`;
  set("hero-title", spec.title);
  applyChip($("hero-expected"), v.expected_route);
  applyChip($("hero-actual"), v.actual_route);

  // Reason line: for a REVIEW, the decision's own reason (LOW_CONFIDENCE /
  // UNKNOWN_CLASS) is more meaningful to the operator than the verification's
  // NO_EXPECTED_ROUTE. Always show the engine's REAL code — never invent one.
  let reasonCode = v.reason_code;
  if (v.status === "REVIEW_REQUIRED") reasonCode = (state.decision || {}).reason || v.reason_code;
  const reason = $("hero-reason");
  reason.textContent = reasonCode ? "reason: " + reasonCode : "";
  showEl(hero, "flex");
}

/* ---------------- WHY panel + guidance ---------------- */
const EVIDENCE_MAX = 3;   // strongest N retained records shown on the main screen

function renderExplanation(rag, explanation, decision, compliance) {
  rag = rag || {}; explanation = explanation || {}; decision = decision || {};
  showEl($("why-card")); showEl($("guidance-card"));
  state.evidenceAll = rag.evidence_all || [];
  state.ragStatus = rag.status;

  const review = decision.status === "REVIEW_REQUIRED";

  // Deterministic policy + decision lines (authoritative — never from the LLM).
  set("why-policy-line",
    `${decision.rule_id || "—"} · policy v${decision.policy_version || "?"}`);
  set("why-decision-line", review
    ? `Manual review — ${humanize(decision.reason || "flagged")}`
    : `${decision.waste_type || "item"} → ${routeLabel(decision.expected_route)}`);

  // Evidence (from Pinecone; never fabricated). Only the strongest 2–3 retained.
  set("rag-tag", "Pinecone: " + ragLabel(rag.status));
  renderEvidence(rag, explanation.evidence_ids_used || []);

  // Evidence-grounded narrative. The backend grounding gate returns
  // SKIPPED_NO_EVIDENCE (never "OK") when no relevant evidence was retrieved, so
  // no factual prose can ever appear without support.
  const llmStatus = explanation.status;
  const llmOk = llmStatus === "OK" && explanation.explanation;
  let llmTag, text;
  if (llmOk) {
    llmTag = explanation.model || "GPT-OSS";
    text = explanation.explanation;
    if (explanation.why_route) text += "\n\nWhy this route: " + explanation.why_route;
  } else if (llmStatus === "SKIPPED_NO_EVIDENCE") {
    llmTag = rag.status === "INSUFFICIENT_EVIDENCE" ? "insufficient evidence" : "no evidence — withheld";
    text = explanation.limitations ||
      "Evidence coverage is insufficient for an evidence-grounded explanation. The route shown was determined by the deterministic facility policy.";
  } else {
    llmTag = "unavailable";
    text = "LLM explanation unavailable — the deterministic decision above still stands.";
  }
  set("llm-tag", llmTag);
  $("why-explanation-text").textContent = text;

  // Evidence IDs the model actually relied on (only when grounded).
  const ids = explanation.evidence_ids_used || [];
  const idsWrap = $("why-ids");
  if (llmOk && ids.length) {
    set("why-ids-list", ids.join(", "));
    showEl(idsWrap, "flex");
  } else {
    hideEl(idsWrap);
  }

  // Limitations (only add the model's own caveats when it actually ran).
  const lim = $("why-limitations");
  const parts = [];
  if (llmOk && explanation.limitations) parts.push(explanation.limitations);
  if (rag.status === "UNAVAILABLE" && rag.error) parts.push("Evidence retrieval unavailable: " + rag.error);
  lim.textContent = parts.join(" ");

  renderGuidance(explanation, decision, compliance);
}

// Build one evidence card. Primary cards hide the raw score (moved to the
// details drawer); the drawer passes showScore=true. Source/page/section are
// only ever rendered when the record actually carries them (never invented).
function evidenceCard(e, usedSet, showScore) {
  const item = document.createElement("div");
  item.className = "evidence-item" + (e.relevance ? " rel-" + e.relevance.toLowerCase() : "");
  const bits = [];
  if (e.source) bits.push(e.source);
  if (e.page !== null && e.page !== undefined) bits.push("p." + e.page);
  if (e.section) bits.push(e.section);

  const head = document.createElement("div");
  head.className = "ev-head";
  const idSpan = document.createElement("span");
  idSpan.className = "ev-id";
  idSpan.textContent = ((usedSet && usedSet.has(e.evidence_id)) ? "★ " : "") +
    (e.evidence_id || "—") + (bits.length ? "  ·  " + bits.join(" · ") : "");
  head.appendChild(idSpan);

  const tags = document.createElement("span");
  tags.className = "ev-tags";
  if (e.relevance) {
    const rb = document.createElement("span");
    rb.className = "rel-badge " + e.relevance.toLowerCase();
    rb.textContent = e.relevance;
    tags.appendChild(rb);
  }
  if (showScore && e.score !== null && e.score !== undefined) {
    const s = document.createElement("span");
    s.className = "ev-score";
    s.textContent = "score " + e.score;
    tags.appendChild(s);
  }
  head.appendChild(tags);

  const body = document.createElement("p");
  body.textContent = e.text || "(no text field on this record)";
  item.appendChild(head);
  item.appendChild(body);
  return item;
}

function renderEvidence(rag, usedIds) {
  const list = $("evidence-list");
  const viewAll = $("view-all-evidence");
  list.innerHTML = "";
  const ev = rag.evidence || [];
  const all = rag.evidence_all || [];

  // Distinct empty states — the "INSUFFICIENT" case is visibly different.
  if (!ev.length) {
    let cls = "evidence-empty", msg;
    if (rag.status === "INSUFFICIENT_EVIDENCE") {
      cls += " insufficient";
      const n = rag.retrieved_count != null ? rag.retrieved_count : all.length;
      msg = `<b>Evidence: INSUFFICIENT</b><br>${n} passage(s) retrieved, none sufficiently ` +
        `relevant to this item. The route was set by the deterministic policy engine.`;
    } else if (rag.status === "UNAVAILABLE") {
      msg = "Evidence store unavailable — decision is based on deterministic policy only.";
    } else {
      msg = "No approved evidence passages retrieved for this item.";
    }
    list.innerHTML = `<div class="${cls}">${msg}</div>`;
    // Still let judges inspect any dropped hits.
    if (all.length) {
      showEl(viewAll, "inline-block");
      viewAll.textContent = `View all retrieved evidence (${all.length})`;
    } else {
      hideEl(viewAll);
    }
    return;
  }

  const used = new Set(usedIds || []);
  ev.slice(0, EVIDENCE_MAX).forEach((e) => list.appendChild(evidenceCard(e, used, false)));

  // Offer the full set when we retrieved more than we showed.
  if (all.length > Math.min(ev.length, EVIDENCE_MAX)) {
    showEl(viewAll, "inline-block");
    viewAll.textContent = `View all retrieved evidence (${all.length})`;
  } else {
    hideEl(viewAll);
  }
}

function openEvidenceModal() {
  const all = state.evidenceAll || [];
  const body = $("evidence-modal-body");
  body.innerHTML = "";
  $("evidence-modal-sub").textContent = all.length
    ? `${all.length} record(s) retrieved from Pinecone. Relevance labels and similarity scores are shown for transparency; only RELEVANT/UNCERTAIN records appear on the main screen and are sent to the explanation model.`
    : "No records were retrieved.";
  if (!all.length) {
    body.innerHTML = `<div class="evidence-empty">No retrieved records.</div>`;
  } else {
    const used = new Set();
    all.forEach((e) => body.appendChild(evidenceCard(e, used, true)));
  }
  showEl($("evidence-modal"), "flex");
}
function closeEvidenceModal() { hideEl($("evidence-modal")); }

function renderGuidance(explanation, decision, compliance) {
  const card = $("guidance-card");
  const list = $("guidance-list");
  const note = $("guidance-note");
  list.innerHTML = "";
  note.textContent = "";
  hideEl(note);

  const status = (compliance && compliance.status) || null;
  const review = decision.status === "REVIEW_REQUIRED" || status === "REVIEW_REQUIRED";
  card.classList.toggle("violation", status === "VIOLATION");
  card.classList.toggle("review", review);

  const llmGuidance = (explanation && explanation.status === "OK" && (explanation.guidance || [])) || [];

  // 1) Review needed -> safe, deterministic escalation action (not a fabricated
  //    medical instruction).
  if (review) {
    set("guidance-title", "What should I do?");
    showEl($("guidance-list"));
    appendGuidance(list, ["Set the item aside and escalate to trained staff for manual classification."]);
    return;
  }

  // 2) Evidence-supported guidance from the model.
  if (llmGuidance.length) {
    set("guidance-title", "✅ What should I do?");
    showEl($("guidance-list"));
    appendGuidance(list, llmGuidance);
    return;
  }

  // 3) A route was assigned but no evidence supports extra handling steps.
  //    Show the evidence-limited notice VERBATIM — never invent generic medical
  //    waste instructions.
  hideEl($("guidance-list"));
  set("guidance-title", "Evidence-limited guidance");
  showEl(note);
  note.textContent =
    "The disposal route was determined by the approved facility policy engine. " +
    "No sufficient supporting evidence was retrieved for additional handling " +
    "instructions. Follow the applicable facility SOP.";
}

function appendGuidance(list, items) {
  items.forEach((g) => { const li = document.createElement("li"); li.textContent = g; list.appendChild(li); });
}

/* ---------------- system / performance ---------------- */
// Status label maps so the UI never shows a misleading "OK".
// RAG: READY (grounded) / NO-EVIDENCE (index returned nothing) / UNAVAILABLE.
// RAG: READY (grounded) / INSUFFICIENT (hits retrieved but none on-topic) /
// NO-EVIDENCE (index returned nothing) / UNAVAILABLE.
function ragLabel(s) {
  return ({
    OK: "READY",
    INSUFFICIENT_EVIDENCE: "INSUFFICIENT",
    NO_RESULTS: "NO-EVIDENCE",
    UNAVAILABLE: "UNAVAILABLE",
  })[s] || s || "-";
}
// LLM: READY only when it ran WITH evidence; DEGRADED when the grounding gate
// withheld it (no evidence) or the model returned unstructured text; else UNAVAILABLE.
function llmLabel(s) {
  return ({
    OK: "READY",
    SKIPPED_NO_EVIDENCE: "DEGRADED (no evidence)",
    UNAVAILABLE: "UNAVAILABLE",
  })[s] || s || "-";
}

function renderSystem(data) {
  const a = data.analysis || {}; const t = data.timings || {};
  const m = a.model || {}; const rag = data.rag || {};
  const retained = rag.retained_count != null ? rag.retained_count : (rag.evidence || []).length;
  const retrieved = rag.retrieved_count != null ? rag.retrieved_count : "-";
  const sys = $("sys-grid"); sys.innerHTML = "";
  const rows = [
    ["Model", m.id || "-"], ["Model ver.", m.version || "-"],
    ["Objects", (a.detections || []).length],
    ["RAG", ragLabel(rag.status)],
    ["Evidence", `${retained} / ${retrieved}`],
    ["LLM", llmLabel((data.explanation || {}).status)],
    ["Namespace", rag.namespace || "-"],
    ["Policy", (a.decision || {}).policy_version || "-"],
    ["Event", (data.event_id || "").slice(0, 8) || "-"],
  ];
  rows.forEach(([k, v]) => sys.appendChild(sysItem(k, v)));

  const tg = $("timing-grid"); tg.innerHTML = "";
  [["Context", t.context_ms], ["Inference", t.inference_ms], ["Retrieval", t.retrieval_ms],
   ["LLM", t.llm_ms], ["Total", t.total_ms]].forEach(([k, v]) =>
    tg.appendChild(sysItem(k, v !== null && v !== undefined ? v + " ms" : "-")));
}
function sysItem(k, v) {
  const d = document.createElement("div");
  d.className = "sys-item";
  d.innerHTML = `<span>${k}</span><b>${v}</b>`;
  return d;
}
function toggleSystem() {
  const body = $("system-body");
  const open = body.style.display !== "none" && body.style.display !== "";
  body.style.display = open ? "none" : "block";
  const h = document.querySelector(".system h2");
  if (h) h.classList.toggle("open", !open);
}

/* =====================================================================
   VERIFY
===================================================================== */
async function verifyCompliance() {
  if (!state.eventId) { showError("Analyze an image before verifying."); return; }
  const actual = $("actual-route").value;
  if (!actual) { showError("Select the actual disposal route first."); return; }
  clearError();
  showLoading("Verifying compliance…");

  try {
    const resp = await fetch("/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_id: state.eventId,
        actual_route: actual,
        station: ($("station").value || "").trim() || null,
      }),
    });
    const data = await resp.json();
    hideLoading();
    if (data.status !== "ok") { showError(data.error || "Verification failed."); return; }
    state.verified = true;
    renderHero(data.verification || {});
    renderExplanation(data.rag, data.explanation, state.decision || {}, data.verification || null);
    markFlow({ detect: true, expect: true, verify: true, explain: true, record: true });
    $("compliance-hero").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (_e) {
    hideLoading();
    showError("Backend connection failed during verification.");
  }
}

/* =====================================================================
   DASHBOARD
===================================================================== */
async function loadAnalytics() {
  try {
    const r = await fetch("/analytics");
    const d = await r.json();
    if (d.status !== "ok") return;
    renderAnalytics(d.analytics || {});
  } catch (_e) { /* ignore */ }
}

function renderAnalytics(an) {
  set("stat-total", an.total_events || 0);
  set("stat-correct", an.correct || 0);
  set("stat-violations", an.violations || 0);
  set("stat-review", an.review_required || 0);
  set("stat-rate", an.compliance_rate === null || an.compliance_rate === undefined ? "—" : an.compliance_rate + "%");

  drawDoughnut("chart-compliance",
    ["Correct", "Violations", "Review", "Pending"],
    [an.correct || 0, an.violations || 0, an.review_required || 0, an.pending_verification || 0],
    ["#22c55e", "#ef4444", "#f59e0b", "#64748b"]);

  drawBar("chart-type", an.violations_by_waste_type || {}, "#ef4444");
  drawBar("chart-route", labelRoutes(an.violations_by_route || {}), "#f59e0b");
  drawStation(an);
}

function labelRoutes(obj) {
  const out = {};
  Object.keys(obj).forEach((k) => { const m = state.routeMeta[k]; out[m ? m.label : k] = obj[k]; });
  return out;
}

function baseOpts(extra) {
  return Object.assign({
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: "#cbd5e1" } } },
    scales: { x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,.05)" } },
              y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,.05)" }, beginAtZero: true } },
  }, extra || {});
}
function destroyChart(id) { if (state.charts[id]) { state.charts[id].destroy(); delete state.charts[id]; } }

function drawDoughnut(id, labels, data, colors) {
  destroyChart(id);
  const ctx = $(id); if (!ctx) return;
  if (!data.some((x) => x > 0)) { emptyChart(ctx); return; }
  state.charts[id] = new Chart(ctx, {
    type: "doughnut",
    data: { labels, datasets: [{ data, backgroundColor: colors, borderColor: "#0b1424", borderWidth: 2 }] },
    options: baseOpts({ scales: {}, cutout: "62%" }),
  });
}
function drawBar(id, obj, color) {
  destroyChart(id);
  const ctx = $(id); if (!ctx) return;
  const labels = Object.keys(obj);
  if (!labels.length) { emptyChart(ctx); return; }
  state.charts[id] = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ label: "Violations", data: labels.map((k) => obj[k]), backgroundColor: color }] },
    options: baseOpts({ plugins: { legend: { display: false } } }),
  });
}
function drawStation(an) {
  const id = "chart-station";
  destroyChart(id);
  const ctx = $(id); if (!ctx) return;
  const perf = an.station_performance || {};
  const stations = Object.keys(perf);
  const empty = $("station-empty");
  if (!an.has_station_data || !stations.length) { emptyChart(ctx); showEl(empty); return; }
  hideEl(empty);
  state.charts[id] = new Chart(ctx, {
    type: "bar",
    data: {
      labels: stations,
      datasets: [
        { label: "Correct", data: stations.map((s) => perf[s].correct || 0), backgroundColor: "#22c55e" },
        { label: "Violations", data: stations.map((s) => perf[s].violations || 0), backgroundColor: "#ef4444" },
      ],
    },
    options: baseOpts({ scales: { x: { stacked: true, ticks: { color: "#94a3b8" }, grid: { display: false } },
                                  y: { stacked: true, beginAtZero: true, ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,.05)" } } } }),
  });
}
function emptyChart(ctx) {
  const c = ctx.getContext("2d");
  c.clearRect(0, 0, ctx.width, ctx.height);
  c.fillStyle = "#64748b"; c.font = "14px Segoe UI"; c.textAlign = "center";
  c.fillText("No data yet", ctx.width / 2, ctx.height / 2);
}

/* =====================================================================
   EVENTS
===================================================================== */
async function loadEvents() {
  const body = $("events-body");
  try {
    const r = await fetch("/events?limit=100");
    const d = await r.json();
    if (d.status !== "ok") return;
    const events = d.events || [];
    body.innerHTML = "";
    if (!events.length) {
      body.innerHTML = `<tr><td colspan="7" class="muted-note">No events yet. Analyze an image to create one.</td></tr>`;
      return;
    }
    events.forEach((ev) => body.appendChild(eventRow(ev)));
  } catch (_e) {
    body.innerHTML = `<tr><td colspan="7" class="muted-note">Could not load events.</td></tr>`;
  }
}

function eventRow(ev) {
  const tr = document.createElement("tr");
  tr.addEventListener("click", () => openEvent(ev.event_id));
  const status = ev.compliance_status || "PENDING_VERIFICATION";
  const expLabel = routeLabel(ev.expected_route);
  const actLabel = routeLabel(ev.actual_route);
  const conf = ev.confidence !== null && ev.confidence !== undefined ? pct(ev.confidence) : "-";
  tr.innerHTML =
    `<td class="mono">${(ev.event_id || "").slice(0, 8)}</td>` +
    `<td>${fmtTime(ev.created_at)}</td>` +
    `<td>${ev.canonical_category || "-"}</td>` +
    `<td>${expLabel}</td>` +
    `<td>${actLabel}</td>` +
    `<td><span class="pill ${status}">${humanize(status)}</span></td>` +
    `<td>${conf}</td>`;
  return tr;
}
function routeLabel(code) {
  if (!code) return "-";
  const m = state.routeMeta[code];
  return m ? m.label : code;
}

async function openEvent(id) {
  showLoading("Loading event…");
  try {
    const r = await fetch("/events/" + id);
    const d = await r.json();
    hideLoading();
    if (d.status !== "ok") { showError("Event not found."); return; }
    renderEventModal(d.event);
  } catch (_e) { hideLoading(); showError("Could not load event."); }
}

function renderEventModal(ev) {
  const p = ev.payload || {};
  const dec = p.decision || {};
  const ver = p.verification || {};
  const rag = p.rag || {};
  const exp = p.explanation || {};
  const body = $("modal-body");
  const status = ev.compliance_status || "PENDING_VERIFICATION";

  const kv = [
    ["Event ID", ev.event_id],
    ["Time", fmtTime(ev.created_at)],
    ["Station", ev.station || "—"],
    ["Canonical item", (p.primary || {}).item || (ev.detected_items || [])[0] || "—"],
    ["Waste type", ev.canonical_category || "—"],
    ["Expected route", routeLabel(ev.expected_route)],
    ["Actual route", routeLabel(ev.actual_route)],
    ["Result", humanize(status)],
    ["Reason", ev.reason_code || "—"],
    ["Rule", ev.rule_id || dec.rule_id || "—"],
    ["Confidence", ev.confidence !== null && ev.confidence !== undefined ? pct(ev.confidence) : "—"],
    ["Model", (ev.model_id || "—") + (ev.model_version ? " / " + ev.model_version : "")],
    ["RAG", rag.status || ev.rag_status || "—"],
    ["LLM", exp.status || ev.llm_status || "—"],
  ];

  let html = `<h3>Audit Event <span class="pill ${status}">${humanize(status)}</span></h3>`;
  if (ev.image_filename) html += `<img src="/uploads/${ev.image_filename}" alt="event image">`;
  html += `<div class="modal-kv">`;
  kv.forEach(([k, v]) => { html += `<span>${k}</span><b>${escapeHtml(String(v))}</b>`; });
  html += `</div>`;

  if (exp.explanation) html += `<h4 style="color:#cbd5e1;margin:10px 0 6px">Explanation</h4>
    <p style="color:#cbd5e1;line-height:1.6">${escapeHtml(exp.explanation)}</p>`;

  const ev_list = rag.evidence || [];
  if (ev_list.length) {
    html += `<h4 style="color:#cbd5e1;margin:14px 0 6px">Evidence (${ev_list.length})</h4>`;
    ev_list.forEach((e) => {
      const bits = [e.source, e.page !== null && e.page !== undefined ? "p." + e.page : null, e.section].filter(Boolean);
      const rel = e.relevance ? `<span class="rel-badge ${e.relevance.toLowerCase()}">${e.relevance}</span>` : "";
      const score = e.score !== null && e.score !== undefined ? `<span class="ev-score">score ${e.score}</span>` : "";
      html += `<div class="evidence-item"><div class="ev-head"><span class="ev-id">${escapeHtml(e.evidence_id || "—")}${bits.length ? " · " + escapeHtml(bits.join(" · ")) : ""}</span>` +
        `<span class="ev-tags">${rel}${score}</span></div>` +
        `<p>${escapeHtml(e.text || "(no text field)")}</p></div>`;
    });
  }

  body.innerHTML = html;
  showEl($("event-modal"), "flex");
}
function closeModal() { hideEl($("event-modal")); }

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Close modals on backdrop click.
document.addEventListener("click", (e) => {
  if (e.target && e.target.id === "event-modal") closeModal();
  if (e.target && e.target.id === "evidence-modal") closeEvidenceModal();
});
