# rag_engine.py
"""
Retrieval-Augmented evidence layer.

Given a *deterministic* policy decision (never the LLM's opinion), build a
structured retrieval query and pull supporting passages from the existing
Pinecone 'brainchild' index. Evidence is normalised into a stable schema and
NEVER fabricated: if a field (source/page/section/text) is not present in the
retrieved record, it is returned as null. If Pinecone is unreachable, the layer
degrades to status "UNAVAILABLE" with an empty evidence list so the core
compliance pipeline keeps working.
"""

import time

import pinecone_retriever
from pinecone_retriever import PineconeUnavailable

# Colour streams -> human words that are likely to appear in guideline text.
_STREAM_WORDS = {
    "YELLOW": "yellow infectious bin",
    "RED": "red sharps container",
    "BLUE": "blue recyclable bin",
    "WHITE": "white chemical container",
    "BROWN": "brown pharmaceutical bin",
    "BLACK": "black general waste bin",
    "RADIOACTIVE_STORAGE": "radioactive shielded storage",
}

# Which record fields we map onto each normalised evidence field, in priority
# order. Only the first field that is actually present is used.
_TEXT_FIELDS = ("text", "chunk_text", "content", "page_content", "chunk", "body")
_SOURCE_FIELDS = ("source", "file", "filename", "document", "doc", "url")
_PAGE_FIELDS = ("page", "page_number", "page_no")
_SECTION_FIELDS = ("section", "heading", "chapter", "title")


# ---------------------------------------------------------------------------
# RELEVANCE-QUALITY GATE (runs AFTER retrieval; never fabricates or edits text)
# ---------------------------------------------------------------------------
# Pinecone still decides what is *retrieved*. This gate only decides what is
# worth *showing to the operator and feeding the LLM* — a top-k hit whose text
# has no bearing on this waste category / disposal / route / policy is dropped
# from the user-facing pack rather than presented as "evidence". The gate is
# deliberately LENIENT: only passages with zero on-domain signal are excluded;
# anything plausibly related is kept and, if not clearly on-point, marked
# UNCERTAIN (still retained). Absolute cosine scores on this index are small
# (~0.15), so the score is used only *relatively* (normalised within a batch),
# never as an absolute pass/fail threshold.

# General biomedical-waste vocabulary — signals a chunk is on-topic at all.
_DOMAIN_TERMS = (
    "medical waste", "biomedical", "bio-medical", "clinical waste",
    "healthcare waste", "health-care waste", "hospital waste", "infectious",
    "hazardous", "biohazard", "waste management", "waste category",
    "waste stream", "waste segregation",
)

# Disposal / segregation / handling vocabulary.
_DISPOSAL_TERMS = (
    "dispose", "disposal", "segregat", "separat", "discard", "bin",
    "container", "bag", "collect", "storage", "store", "handling",
    "sort", "colour code", "color code", "colour-coded", "color-coded",
    "puncture-proof", "puncture proof",
)

# Policy / regulatory vocabulary.
_POLICY_TERMS = (
    "policy", "guideline", "regulation", "standard", "protocol",
    "procedure", "requirement", "compliance", "must ", "should ", "shall ",
)

# Violation-specific vocabulary — only meaningful for a VIOLATION result.
_VIOLATION_TERMS = (
    "incorrect", "wrong", "improper", "misplac", "violation", "non-compliant",
    "noncompliant", "must not", "should not", "risk", "injury", "exposure",
)

# Category-specific vocabulary keyed by canonical waste_type AND raw item, so an
# item (e.g. GLOVES) that policy mapped to a generic stream still matches on its
# own name. Fragments (e.g. "segregat") match inflections without regex.
_CATEGORY_TERMS = {
    "SHARPS": ("sharp", "needle", "syringe", "scalpel", "blade", "lancet",
               "puncture", "cannula"),
    "INFECTIOUS": ("infectious", "biohazard", "contaminat", "blood",
                   "body fluid", "soiled", "dressing", "gauze", "swab",
                   "pathological", "tissue"),
    "PHARMACEUTICAL": ("pharmaceutic", "medicine", "medication", "drug",
                       "pill", "capsule", "tablet", "expired", "cytotoxic",
                       "vial", "ampoule"),
    "CHEMICAL": ("chemical", "reagent", "disinfectant", "solvent", "toxic",
                 "corrosive", "iodine"),
    "RADIOACTIVE": ("radioactive", "radiation", "radionuclide", "isotope",
                    "shielded", "decay"),
    "RECYCLABLE": ("recycl", "plastic", "glass", "bottle", "uncontaminated",
                   "non-contaminated"),
    "GENERAL": ("general waste", "non-hazardous", "nonhazardous", "municipal",
                "domestic", "non-infectious", "offensive waste"),
    # item-level keys (canonical items that differ from waste_type)
    "GLOVES": ("glove", "ppe", "personal protective"),
    "PPE": ("ppe", "personal protective", "mask", "gown", "apron", "respirator",
            "glove"),
    "PLASTIC": ("plastic", "recycl", "bottle", "bag"),
    "GLASS": ("glass", "bottle", "recycl"),
}

# Route colour code -> the human colour word likely to appear in guideline text.
_ROUTE_COLOR = {
    "YELLOW": "yellow", "RED": "red", "BLUE": "blue", "WHITE": "white",
    "BROWN": "brown", "BLACK": "black", "RADIOACTIVE_STORAGE": "radioactive",
}


def _readable(item):
    return str(item or "").replace("_", " ").strip().lower()


def build_query(item, context, policy, compliance=None, actual_route=None):
    """
    Construct a deterministic retrieval query from structured fields.
    The LLM never writes this query.

    ``actual_route`` is an optional explicit hint for the route the operator
    actually used; it is only used to enrich the query when a compliance result
    does not already carry it (e.g. a pre-verification violation preview).
    """
    policy = policy or {}
    compliance = compliance or {}

    waste_type = policy.get("waste_type")
    expected = policy.get("expected_route") or policy.get("required_stream")

    parts = ["medical waste", "biomedical waste segregation disposal"]
    if waste_type:
        parts.append(_readable(waste_type))
    if item and str(item).upper() not in ("UNKNOWN", ""):
        parts.append(_readable(item))

    if expected:
        parts.append("dispose in " + _STREAM_WORDS.get(expected, _readable(expected)))
    parts.append("hospital policy guideline")

    # Context cues (only when asserted).
    if context:
        if context.get("Contaminated") == "YES":
            parts.append("contaminated with blood body fluid")
        if context.get("Used") == "YES":
            parts.append("used after patient treatment")

    status = compliance.get("status")
    # Prefer the compliance-carried actual route; fall back to the explicit arg.
    actual = compliance.get("actual_route") or actual_route
    if status == "VIOLATION":
        parts.append("incorrect segregation wrong disposal")
        if actual:
            parts.append("misplaced in " + _STREAM_WORDS.get(actual, _readable(actual)))
    elif not expected:  # review / uncertain
        parts.append("classification requirements handling unknown item")

    return " ".join(p for p in parts if p)


def _first(fields, names):
    for n in names:
        if n in fields and fields[n] not in (None, ""):
            return fields[n]
    return None


def _normalise_hit(hit):
    fields = hit.get("fields") or {}
    return {
        "evidence_id": hit.get("id"),
        "score": round(float(hit["score"]), 4) if hit.get("score") is not None else None,
        "text": _first(fields, _TEXT_FIELDS),
        "source": _first(fields, _SOURCE_FIELDS),
        "page": _first(fields, _PAGE_FIELDS),
        "section": _first(fields, _SECTION_FIELDS),
        "metadata": fields or {},
    }


def _has_any(haystack, terms):
    """True if any term (a plain substring, not a regex) is present."""
    return any(t in haystack for t in terms)


def assess_relevance(text, item, waste_type, expected_route,
                     compliance_status, score, batch_max):
    """
    Classify ONE retrieved passage's relevance to *this* deterministic decision.

    Returns ``(label, relevance_score)`` where label is one of
    ``"RELEVANT"`` | ``"UNCERTAIN"`` | ``"IRRELEVANT"``.

    The passage text is NEVER modified. The rule is intentionally lenient (the
    brief forbids over-filtering): a passage is only IRRELEVANT when it carries
    *no* waste-category, domain, disposal, policy, or route signal at all; an
    on-domain-but-not-clearly-on-point passage is UNCERTAIN and still retained.
    """
    hay = " " + str(text or "").lower() + " "

    # Category terms for BOTH the canonical waste_type and the raw item.
    cat_terms = set()
    for key in (waste_type, item):
        k = str(key or "").upper().strip()
        if k in _CATEGORY_TERMS:
            cat_terms.update(_CATEGORY_TERMS[k])

    has_category = _has_any(hay, cat_terms) if cat_terms else False
    has_domain = _has_any(hay, _DOMAIN_TERMS)
    has_disposal = _has_any(hay, _DISPOSAL_TERMS)
    has_policy = _has_any(hay, _POLICY_TERMS)

    route_word = _ROUTE_COLOR.get(str(expected_route or "").upper())
    has_route = bool(route_word) and route_word in hay

    has_violation = False
    if compliance_status == "VIOLATION":
        has_violation = _has_any(hay, _VIOLATION_TERMS)

    # Retrieval score used only RELATIVELY (normalised within the batch), since
    # absolute cosine values on this index are small and not a usable threshold.
    norm_score = 0.0
    if score is not None and batch_max:
        try:
            norm_score = max(0.0, min(1.0, float(score) / float(batch_max)))
        except (TypeError, ValueError, ZeroDivisionError):
            norm_score = 0.0

    relevance_score = round(min(1.0,
        0.45 * has_category + 0.15 * has_route + 0.15 * has_disposal +
        0.10 * has_policy + 0.08 * has_domain + 0.05 * has_violation +
        0.12 * norm_score), 4)

    # No waste/policy/category/route/disposal vocabulary whatsoever -> unrelated.
    if not (has_category or has_domain or has_disposal or has_policy or has_route):
        return "IRRELEVANT", relevance_score

    strongly_relevant = (
        (has_category and (has_domain or has_disposal or has_policy or has_route))
        or (has_route and has_disposal)
    )
    return ("RELEVANT" if strongly_relevant else "UNCERTAIN"), relevance_score


def retrieve_evidence(item, context, policy, compliance=None, actual_route=None,
                      top_k=8, rerank=False):
    """
    Retrieve supporting evidence for a decision.

    ``actual_route`` optionally names the route the operator actually used, so a
    violation query can be enriched even before a full compliance result exists.

    Returns:
        {
          "status": "OK" | "INSUFFICIENT_EVIDENCE" | "NO_RESULTS" | "UNAVAILABLE",
          "query": "...",
          "namespace": "...",
          "text_field": "...",
          "evidence": [ retained {..., relevance, relevance_score}, ... ],
          "evidence_all": [ every hit incl. dropped ones, for a details drawer ],
          "evidence_ids": [ ids of RETAINED evidence only ],
          "retrieved_count": int,   # raw hits before the relevance gate
          "retained_count": int,    # hits kept after the relevance gate
          "latency_ms": float,
          "error": str | None,       # safe message, never secrets
        }

    Status semantics:
        OK                    -> at least one passage passed the relevance gate
        INSUFFICIENT_EVIDENCE -> Pinecone returned hits but NONE were relevant
        NO_RESULTS            -> Pinecone returned zero hits
        UNAVAILABLE           -> Pinecone could not be reached
    """
    policy = policy or {}
    compliance = compliance or {}
    query = build_query(item, context, policy, compliance, actual_route)
    t0 = time.perf_counter()

    meta = {}
    try:
        meta = pinecone_retriever.inspect_index()
    except Exception:
        meta = {}

    try:
        hits = pinecone_retriever.retrieve(query, top_k=top_k, rerank=rerank)
    except PineconeUnavailable as e:
        return {
            "status": "UNAVAILABLE",
            "query": query,
            "namespace": pinecone_retriever.NAMESPACE,
            "text_field": meta.get("text_field"),
            "evidence": [],
            "evidence_all": [],
            "evidence_ids": [],
            "retrieved_count": 0,
            "retained_count": 0,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "error": str(e)[:300],
        }

    normalised = [_normalise_hit(h) for h in hits]

    # --- RELEVANCE-QUALITY GATE (after retrieval; text never modified) --------
    waste_type = policy.get("waste_type")
    expected_route = policy.get("expected_route") or policy.get("required_stream")
    compliance_status = compliance.get("status")
    scores = [e["score"] for e in normalised if e.get("score") is not None]
    batch_max = max(scores) if scores else None

    for e in normalised:
        label, rel = assess_relevance(
            e.get("text"), item, waste_type, expected_route,
            compliance_status, e.get("score"), batch_max,
        )
        e["relevance"] = label
        e["relevance_score"] = rel

    # Retained = RELEVANT + UNCERTAIN (RELEVANT first, then by relevance score).
    _rank = {"RELEVANT": 0, "UNCERTAIN": 1, "IRRELEVANT": 2}
    retained = [e for e in normalised if e["relevance"] in ("RELEVANT", "UNCERTAIN")]
    retained.sort(key=lambda e: (_rank[e["relevance"]], -(e.get("relevance_score") or 0.0)))
    evidence_all = sorted(normalised, key=lambda e: -(e.get("score") or 0.0))

    if not normalised:
        status = "NO_RESULTS"
    elif not retained:
        status = "INSUFFICIENT_EVIDENCE"
    else:
        status = "OK"

    return {
        "status": status,
        "query": query,
        "namespace": pinecone_retriever.NAMESPACE,
        "text_field": meta.get("text_field"),
        "evidence": retained,
        "evidence_all": evidence_all,
        "evidence_ids": [e["evidence_id"] for e in retained if e["evidence_id"]],
        "retrieved_count": len(normalised),
        "retained_count": len(retained),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        "error": None,
    }
