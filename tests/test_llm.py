# tests/test_llm.py
"""The LLM only EXPLAINS a decision that was already made. It never decides, and
any hallucinated evidence ids it returns are stripped. The network is never
touched here — llm_client._chat is monkeypatched in every test."""

import llm_client

_DECISION = {"status": "DECIDED", "waste_type": "SHARPS",
             "expected_route": "RED", "rule_id": "R-SHARPS",
             "policy_version": "1.1.0", "reason": None}
_EVIDENCE = [{"evidence_id": "e1", "text": "Sharps go in the red container.",
              "source": "guide.pdf", "page": 3, "section": "Sharps"}]


def test_no_api_key_degrades_to_unavailable():
    saved = llm_client.OPENROUTER_API_KEY
    try:
        llm_client.OPENROUTER_API_KEY = None
        out = llm_client.generate_explanation(_DECISION, _EVIDENCE, context={})
        assert out["status"] == "UNAVAILABLE"
        assert out["guidance"] == []
        assert out["evidence_ids_used"] == []
        assert "not configured" in (out["limitations"] or "").lower()
    finally:
        llm_client.OPENROUTER_API_KEY = saved


def test_hallucinated_evidence_ids_are_stripped():
    saved_key, saved_chat = llm_client.OPENROUTER_API_KEY, llm_client._chat
    try:
        llm_client.OPENROUTER_API_KEY = "test-key"  # bypass the no-key guard
        llm_client._chat = lambda messages, **k: (
            '{"explanation":"Use the red bin.",'
            '"why_route":"Sharps injure handlers.",'
            '"guidance":["Seal the container"],'
            '"evidence_ids_used":["e1","GHOST-999"],'
            '"limitations":"none"}'
        )
        out = llm_client.generate_explanation(_DECISION, _EVIDENCE, context={})
        assert out["status"] == "OK"
        assert out["evidence_ids_used"] == ["e1"]      # GHOST-999 dropped
        assert "GHOST-999" not in out["evidence_ids_used"]
        assert out["why_route"]
        assert out["guidance"] == ["Seal the container"]
    finally:
        llm_client.OPENROUTER_API_KEY, llm_client._chat = saved_key, saved_chat


def test_non_json_output_falls_back_to_raw_text():
    saved_key, saved_chat = llm_client.OPENROUTER_API_KEY, llm_client._chat
    try:
        llm_client.OPENROUTER_API_KEY = "test-key"
        llm_client._chat = lambda messages, **k: "Just put it in the red bin."
        out = llm_client.generate_explanation(_DECISION, _EVIDENCE, context={})
        assert out["status"] == "OK"
        assert "red bin" in out["explanation"]
        assert out["evidence_ids_used"] == []
        assert "JSON" in (out["limitations"] or "")
    finally:
        llm_client.OPENROUTER_API_KEY, llm_client._chat = saved_key, saved_chat


def test_chat_failure_degrades_to_unavailable():
    saved_key, saved_chat = llm_client.OPENROUTER_API_KEY, llm_client._chat
    try:
        llm_client.OPENROUTER_API_KEY = "test-key"

        def boom(messages, **k):
            raise RuntimeError("OpenRouter HTTP 500")
        llm_client._chat = boom
        out = llm_client.generate_explanation(_DECISION, _EVIDENCE, context={})
        assert out["status"] == "UNAVAILABLE"
        assert "500" in out["limitations"]
        assert out["guidance"] == []
    finally:
        llm_client.OPENROUTER_API_KEY, llm_client._chat = saved_key, saved_chat


def test_llm_cannot_override_the_decided_route():
    """Even if the model's JSON asserts a DIFFERENT bin, the explanation layer
    exposes no route-bearing field — the deterministic route is an INPUT, never
    an output the LLM can rewrite."""
    saved_key, saved_chat = llm_client.OPENROUTER_API_KEY, llm_client._chat
    try:
        llm_client.OPENROUTER_API_KEY = "test-key"
        llm_client._chat = lambda messages, **k: (
            '{"explanation":"Actually use the BLACK bin.",'
            '"why_route":"model opinion",'
            '"guidance":["put in black"],'
            '"expected_route":"BLACK","waste_type":"GENERAL",'
            '"evidence_ids_used":["e1"],"limitations":"none"}'
        )
        out = llm_client.generate_explanation(_DECISION, _EVIDENCE, context={})
        assert out["status"] == "OK"
        # No decision-authority fields leak out of the explanation layer.
        assert "expected_route" not in out
        assert "waste_type" not in out
        # The caller's deterministic decision object is untouched.
        assert _DECISION["expected_route"] == "RED"
    finally:
        llm_client.OPENROUTER_API_KEY, llm_client._chat = saved_key, saved_chat


def test_guidance_string_is_coerced_to_list():
    saved_key, saved_chat = llm_client.OPENROUTER_API_KEY, llm_client._chat
    try:
        llm_client.OPENROUTER_API_KEY = "test-key"
        llm_client._chat = lambda messages, **k: (
            '{"explanation":"x","why_route":"y",'
            '"guidance":"single action","evidence_ids_used":[],'
            '"limitations":""}'
        )
        out = llm_client.generate_explanation(_DECISION, _EVIDENCE, context={})
        assert out["guidance"] == ["single action"]
    finally:
        llm_client.OPENROUTER_API_KEY, llm_client._chat = saved_key, saved_chat


def test_no_evidence_gate_skips_llm_and_never_fabricates():
    """GROUNDING GATE (STEP 6): with NO evidence the model must NOT run and must
    NOT invent a factual explanation — even when an API key IS configured."""
    saved_key, saved_chat = llm_client.OPENROUTER_API_KEY, llm_client._chat
    called = {"chat": False}
    try:
        llm_client.OPENROUTER_API_KEY = "test-key"  # key present on purpose

        def _must_not_run(messages, **k):
            called["chat"] = True
            raise AssertionError("_chat must NOT be called without evidence")
        llm_client._chat = _must_not_run

        out = llm_client.generate_explanation(_DECISION, [], context={})
        assert out["status"] == "SKIPPED_NO_EVIDENCE"
        assert out["explanation"] is None
        assert out["why_route"] is None
        assert out["guidance"] == []
        assert out["evidence_ids_used"] == []
        assert called["chat"] is False  # the model was never contacted
        # A safe status message — NOT a regulatory explanation.
        assert "deterministic policy engine" in (out["limitations"] or "")
    finally:
        llm_client.OPENROUTER_API_KEY, llm_client._chat = saved_key, saved_chat


def test_evidence_without_ids_is_treated_as_no_evidence():
    """Evidence that carries no citable id cannot be traced back to a source, so
    the gate treats it as no-evidence rather than letting the model cite
    untraceable support."""
    saved_key, saved_chat = llm_client.OPENROUTER_API_KEY, llm_client._chat
    try:
        llm_client.OPENROUTER_API_KEY = "test-key"
        # If the gate failed, this stub would fabricate an explanation.
        llm_client._chat = lambda messages, **k: '{"explanation":"fabricated"}'
        out = llm_client.generate_explanation(
            _DECISION, [{"text": "sharps go in the red bin", "source": "d"}],
            context={},
        )
        assert out["status"] == "SKIPPED_NO_EVIDENCE"
        assert out["explanation"] is None
    finally:
        llm_client.OPENROUTER_API_KEY, llm_client._chat = saved_key, saved_chat


def test_insufficient_evidence_status_yields_distinct_message():
    """When RAG retrieved hits but the relevance gate kept none
    (rag_status='INSUFFICIENT_EVIDENCE'), the gate must still withhold the model
    AND surface the distinct 'insufficient' message (not the generic no-evidence
    one), so the UI can render a visibly different state."""
    saved_key, saved_chat = llm_client.OPENROUTER_API_KEY, llm_client._chat
    called = {"chat": False}
    try:
        llm_client.OPENROUTER_API_KEY = "test-key"

        def _must_not_run(messages, **k):
            called["chat"] = True
            raise AssertionError("_chat must NOT run on insufficient evidence")
        llm_client._chat = _must_not_run

        out = llm_client.generate_explanation(
            _DECISION, [], context={}, rag_status="INSUFFICIENT_EVIDENCE"
        )
        assert out["status"] == "SKIPPED_NO_EVIDENCE"
        assert out["explanation"] is None
        assert called["chat"] is False
        assert "insufficient" in (out["limitations"] or "").lower()
        assert "deterministic facility policy" in (out["limitations"] or "").lower()
    finally:
        llm_client.OPENROUTER_API_KEY, llm_client._chat = saved_key, saved_chat
