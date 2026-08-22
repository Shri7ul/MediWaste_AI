# tests/test_rag.py
"""RAG builds a DETERMINISTIC query from structured policy fields and NEVER
fabricates evidence. Pinecone calls are monkeypatched so these tests are
hermetic (no network) and behave identically whether or not the SDK is
installed."""

import rag_engine
import pinecone_retriever
from pinecone_retriever import PineconeUnavailable


def _patch(retrieve_fn, inspect_fn=None):
    """Swap in fakes for the two pinecone_retriever entry points RAG uses."""
    saved = (pinecone_retriever.retrieve, pinecone_retriever.inspect_index)
    pinecone_retriever.retrieve = retrieve_fn
    pinecone_retriever.inspect_index = inspect_fn or (lambda *a, **k: {})
    return saved


def _restore(saved):
    pinecone_retriever.retrieve, pinecone_retriever.inspect_index = saved


def test_build_query_is_deterministic_and_grounded():
    policy = {"waste_type": "SHARPS", "expected_route": "RED"}
    q1 = rag_engine.build_query("SHARPS", {}, policy)
    q2 = rag_engine.build_query("SHARPS", {}, policy)
    assert q1 == q2  # deterministic
    assert "medical waste" in q1
    assert "red sharps container" in q1  # human words, not a bare colour code
    assert "hospital policy guideline" in q1


def test_build_query_includes_context_only_when_asserted():
    policy = {"waste_type": "INFECTIOUS", "expected_route": "YELLOW"}
    q = rag_engine.build_query(
        "GLOVES", {"Used": "YES", "Contaminated": "YES"}, policy
    )
    assert "contaminated with blood body fluid" in q
    assert "used after patient treatment" in q
    # Without the context flags, those phrases must be absent.
    q2 = rag_engine.build_query("GLOVES", {}, policy)
    assert "contaminated with blood body fluid" not in q2


def test_build_query_violation_mentions_misplacement():
    policy = {"waste_type": "SHARPS", "expected_route": "RED"}
    compliance = {"status": "VIOLATION", "actual_route": "BLACK"}
    q = rag_engine.build_query("SHARPS", {}, policy, compliance)
    assert "incorrect segregation wrong disposal" in q
    assert "black general waste bin" in q


def test_retrieve_evidence_degrades_when_pinecone_unavailable():
    def boom(*a, **k):
        raise PineconeUnavailable("simulated: pinecone not installed")
    saved = _patch(boom)
    try:
        res = rag_engine.retrieve_evidence(
            "SHARPS", {}, {"waste_type": "SHARPS", "expected_route": "RED"}
        )
        assert res["status"] == "UNAVAILABLE"
        assert res["evidence"] == []       # never fabricated
        assert res["evidence_ids"] == []
        assert res["query"]                # the query is still reported
        assert isinstance(res["error"], str)
    finally:
        _restore(saved)


def test_retrieve_evidence_normalises_hits_without_fabrication():
    def fake(query, top_k=8, rerank=False, **k):
        return [
            {"id": "doc-1", "score": 0.87654,
             "fields": {"text": "Needles go in the red sharps bin.",
                        "source": "WHO_guide.pdf", "page": 12}},
            {"id": "doc-2", "score": 0.5,
             "fields": {"chunk_text": "Segregate at point of generation."}},
        ]
    saved = _patch(fake, inspect_fn=lambda *a, **k: {"text_field": "text"})
    try:
        res = rag_engine.retrieve_evidence(
            "SHARPS", {}, {"waste_type": "SHARPS", "expected_route": "RED"}
        )
        assert res["status"] == "OK"
        assert res["evidence_ids"] == ["doc-1", "doc-2"]
        e0 = res["evidence"][0]
        assert e0["evidence_id"] == "doc-1"
        assert abs(e0["score"] - 0.8765) < 1e-6  # rounded to 4 dp
        assert e0["text"] == "Needles go in the red sharps bin."
        assert e0["source"] == "WHO_guide.pdf"
        assert e0["page"] == 12
        # doc-2 has no source/page/section -> reported as None, never invented.
        e1 = res["evidence"][1]
        assert e1["text"] == "Segregate at point of generation."
        assert e1["source"] is None
        assert e1["page"] is None
        assert e1["section"] is None
    finally:
        _restore(saved)


def test_retrieve_evidence_no_results_status():
    saved = _patch(lambda *a, **k: [])
    try:
        res = rag_engine.retrieve_evidence(
            "SHARPS", {}, {"waste_type": "SHARPS", "expected_route": "RED"}
        )
        assert res["status"] == "NO_RESULTS"
        assert res["evidence"] == []
    finally:
        _restore(saved)


# ---------------------------------------------------------------------------
# RELEVANCE-QUALITY GATE (runs AFTER retrieval; never edits text / invents data)
# ---------------------------------------------------------------------------
def test_relevance_gate_drops_clearly_offtopic_chunk():
    """A top-k hit with no waste/policy/route/disposal signal is removed from the
    user-facing pack but preserved (labelled IRRELEVANT) in evidence_all."""
    def fake(query, top_k=8, rerank=False, **k):
        return [
            {"id": "good", "score": 0.19, "fields": {
                "text": "Needles and syringes must go in the red sharps container.",
                "source": "WHO.pdf", "page": 3}},
            {"id": "junk", "score": 0.18, "fields": {
                "text": "The quarterly budget meeting is on Tuesday in room B."}},
        ]
    saved = _patch(fake)
    try:
        res = rag_engine.retrieve_evidence(
            "SHARPS", {}, {"waste_type": "SHARPS", "expected_route": "RED"}
        )
        assert res["status"] == "OK"
        assert res["evidence_ids"] == ["good"]        # junk dropped
        assert res["retrieved_count"] == 2 and res["retained_count"] == 1
        # evidence_all still carries every hit, so nothing is silently discarded.
        ids_all = {e["evidence_id"] for e in res["evidence_all"]}
        assert ids_all == {"good", "junk"}
        junk = next(e for e in res["evidence_all"] if e["evidence_id"] == "junk")
        assert junk["relevance"] == "IRRELEVANT"
        # The retained chunk's text is returned verbatim (never modified).
        assert res["evidence"][0]["text"] == \
            "Needles and syringes must go in the red sharps container."
        assert res["evidence"][0]["relevance"] == "RELEVANT"
    finally:
        _restore(saved)


def test_relevance_gate_insufficient_when_all_offtopic():
    """Hits present but NONE relevant -> INSUFFICIENT_EVIDENCE (not NO_RESULTS,
    not a fabricated pass)."""
    def fake(query, top_k=8, rerank=False, **k):
        return [
            {"id": "j1", "score": 0.15, "fields": {"text": "Cafeteria menu changes on Friday."}},
            {"id": "j2", "score": 0.14, "fields": {"text": "Parking permits renew annually."}},
        ]
    saved = _patch(fake)
    try:
        res = rag_engine.retrieve_evidence(
            "PHARMACEUTICAL", {}, {"waste_type": "PHARMACEUTICAL", "expected_route": "BROWN"}
        )
        assert res["status"] == "INSUFFICIENT_EVIDENCE"
        assert res["evidence"] == [] and res["evidence_ids"] == []
        assert res["retrieved_count"] == 2 and res["retained_count"] == 0
        assert len(res["evidence_all"]) == 2   # dropped hits still inspectable
    finally:
        _restore(saved)


def test_relevance_gate_keeps_ondomain_as_uncertain():
    """On-domain-but-not-clearly-on-point evidence is KEPT and marked UNCERTAIN
    (the brief forbids over-filtering)."""
    def fake(query, top_k=8, rerank=False, **k):
        return [{"id": "d2", "score": 0.16, "fields": {
            "text": "Segregate waste at the point of generation."}}]
    saved = _patch(fake)
    try:
        res = rag_engine.retrieve_evidence(
            "SHARPS", {}, {"waste_type": "SHARPS", "expected_route": "RED"}
        )
        assert res["status"] == "OK"
        assert res["evidence_ids"] == ["d2"]
        assert res["evidence"][0]["relevance"] == "UNCERTAIN"
    finally:
        _restore(saved)


def test_relevance_gate_orders_relevant_before_uncertain():
    """Retained evidence is ordered RELEVANT-first so the UI's top 2-3 cards are
    the strongest, regardless of raw Pinecone order."""
    def fake(query, top_k=8, rerank=False, **k):
        return [
            {"id": "weak", "score": 0.20, "fields": {"text": "Segregate at the point of generation."}},
            {"id": "strong", "score": 0.10, "fields": {"text": "Sharps such as needles belong in the red puncture-proof container."}},
        ]
    saved = _patch(fake)
    try:
        res = rag_engine.retrieve_evidence(
            "SHARPS", {}, {"waste_type": "SHARPS", "expected_route": "RED"}
        )
        # 'strong' is RELEVANT and must lead even though 'weak' had a higher score.
        assert res["evidence_ids"] == ["strong", "weak"]
        assert res["evidence"][0]["relevance"] == "RELEVANT"
        assert res["evidence"][1]["relevance"] == "UNCERTAIN"
    finally:
        _restore(saved)
