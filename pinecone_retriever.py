# pinecone_retriever.py
"""
Real Pinecone retriever for the existing 'brainchild' index.

The index uses Pinecone INTEGRATED EMBEDDING (server-side model, e.g.
llama-text-embed-v2), so we query with *text* — no local embedding model is
added. We never create, overwrite, or re-index anything here; this module only
inspects and searches.

The Pinecone Python SDK surface has changed across versions, so this module is
deliberately defensive: it tolerates both object- and dict-shaped responses and
both the ``search`` and ``search_records`` method names. All failures raise
``PineconeUnavailable`` so the RAG layer can degrade gracefully without ever
fabricating evidence.
"""

import os
import threading

from dotenv import load_dotenv

load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "brainchild").strip()
# Pinecone's default namespace for the records API is "__default__".
NAMESPACE = (os.getenv("PINECONE_NAMESPACE") or "__default__").strip()

_lock = threading.Lock()
_pc = None
_index = None
_index_meta = None  # cached inspect_index() result


class PineconeUnavailable(RuntimeError):
    """Raised when Pinecone cannot be reached or is not configured/installed."""


# ---------------------------------------------------------------------------
# Client / index handles (lazy, cached)
# ---------------------------------------------------------------------------
def get_client():
    global _pc
    if _pc is None:
        with _lock:
            if _pc is None:
                if not PINECONE_API_KEY:
                    raise PineconeUnavailable("PINECONE_API_KEY is not configured.")
                Pinecone = _import_pinecone_class()
                try:
                    _pc = Pinecone(api_key=PINECONE_API_KEY)
                except Exception as e:
                    raise PineconeUnavailable(f"Pinecone client init failed: {e}")
    return _pc


def _import_pinecone_class():
    """
    Import the modern Pinecone SDK class with an ACTIONABLE diagnosis on failure.

    The single most common live failure ("No module named 'pinecone'" or a
    missing ``Pinecone`` class) is almost always an install problem: either the
    package is absent, or a *legacy* ``pinecone-client`` (pinecone < 3, which
    exposed ``pinecone.init`` instead of the ``Pinecone`` class) is shadowing the
    modern SDK. We detect each case and return the exact command to fix it,
    rather than raising a generic error.
    """
    try:
        import pinecone as _mod
    except ImportError as e:
        raise PineconeUnavailable(
            "pinecone SDK not installed. Install the modern SDK in this "
            'environment:  pip install "pinecone>=5.1,<8"  '
            f"(import error: {e})"
        )
    Pinecone = getattr(_mod, "Pinecone", None)
    if Pinecone is None:
        legacy = hasattr(_mod, "init")  # pinecone<3 / pinecone-client signature
        reason = ("a legacy 'pinecone-client' is installed and shadows the "
                  "modern SDK" if legacy else "an incompatible pinecone build "
                  "is installed")
        ver = getattr(_mod, "__version__", "unknown")
        raise PineconeUnavailable(
            f"pinecone SDK unusable ({reason}; version={ver}). Fix with:  "
            'pip uninstall -y pinecone-client pinecone && '
            'pip install "pinecone>=5.1,<8"'
        )
    return Pinecone


def _to_dict(obj):
    """Best-effort convert an SDK model/response into a plain dict."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    for attr in ("to_dict", "dict", "model_dump"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    try:
        return dict(obj)
    except Exception:
        return {k: getattr(obj, k) for k in dir(obj)
                if not k.startswith("_") and not callable(getattr(obj, k))}


def inspect_index(refresh=False):
    """
    Programmatically inspect the live index and return a diagnostics dict.
    Never raises for individual missing fields; raises PineconeUnavailable only
    if the index cannot be described at all.
    """
    global _index_meta
    if _index_meta is not None and not refresh:
        return _index_meta

    pc = get_client()
    try:
        desc = pc.describe_index(INDEX_NAME)
    except Exception as e:
        raise PineconeUnavailable(f"describe_index('{INDEX_NAME}') failed: {e}")

    try:
        import pinecone as _mod
        sdk_version = getattr(_mod, "__version__", "unknown")
    except Exception:
        sdk_version = "unknown"

    d = _to_dict(desc)
    status = _to_dict(d.get("status"))
    spec = _to_dict(d.get("spec"))
    serverless = _to_dict(spec.get("serverless"))
    embed = _to_dict(d.get("embed"))
    field_map = _to_dict(embed.get("field_map"))

    meta = {
        "name": d.get("name", INDEX_NAME),
        "host": d.get("host"),
        "sdk_version": sdk_version,
        "dimension": d.get("dimension"),
        "metric": d.get("metric"),
        "vector_type": d.get("vector_type"),
        "ready": status.get("ready"),
        "state": status.get("state"),
        "cloud": serverless.get("cloud"),
        "region": serverless.get("region"),
        "embed_model": embed.get("model"),
        "field_map": field_map or None,
        "text_field": field_map.get("text") if field_map else None,
        "namespaces": [],
        "total_vector_count": None,
    }

    # Stats give namespaces + counts (best effort).
    try:
        idx = get_index(meta.get("host"))
        stats = _to_dict(idx.describe_index_stats())
        ns = stats.get("namespaces") or {}
        meta["namespaces"] = sorted(ns.keys()) if isinstance(ns, dict) else []
        meta["total_vector_count"] = stats.get("total_vector_count")
        if meta.get("dimension") is None:
            meta["dimension"] = stats.get("dimension")
    except Exception:
        pass

    _index_meta = meta
    return meta


def get_index(host=None):
    """Return a cached index handle (prefers connecting by host)."""
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                pc = get_client()
                try:
                    if host:
                        _index = pc.Index(host=host)
                    else:
                        _index = pc.Index(INDEX_NAME)
                except Exception as e:
                    raise PineconeUnavailable(f"Index handle failed: {e}")
    return _index


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
_CANDIDATE_RETURN_FIELDS = [
    "text", "chunk_text", "content", "page_content", "chunk", "body",
    "source", "file", "filename", "document", "doc", "url",
    "title", "heading", "section", "chapter",
    "page", "page_number", "page_no",
    "category", "stream", "waste_type",
]


def _extract_hits(resp):
    """Normalise a search response into [{'id','score','fields'}, ...]."""
    d = _to_dict(resp)
    result = d.get("result")
    if result is None and "hits" in d:
        hits = d.get("hits")
    else:
        hits = _to_dict(result).get("hits", []) if result is not None else []
    out = []
    for h in hits or []:
        hd = _to_dict(h)
        out.append({
            "id": hd.get("_id") or hd.get("id"),
            "score": hd.get("_score", hd.get("score")),
            "fields": _to_dict(hd.get("fields") or hd.get("metadata") or {}),
        })
    return out


def retrieve(query_text, top_k=8, namespace=None, text_field=None,
             metadata_filter=None, rerank=False):
    """
    Semantic retrieval via integrated embedding.

    Returns a list of hit dicts: {"id", "score", "fields"}.
    Raises PineconeUnavailable on any failure so the caller can degrade.
    """
    if not query_text or not str(query_text).strip():
        return []

    meta = None
    try:
        meta = inspect_index()
    except PineconeUnavailable:
        raise
    except Exception:
        meta = None

    host = meta.get("host") if meta else None
    ns = namespace if namespace is not None else NAMESPACE
    tf = text_field or (meta.get("text_field") if meta else None) or "text"

    idx = get_index(host)

    query = {"inputs": {"text": str(query_text)}, "top_k": int(top_k)}
    if metadata_filter:
        query["filter"] = metadata_filter

    kwargs = {"namespace": ns, "query": query}
    return_fields = sorted(set(_CANDIDATE_RETURN_FIELDS + [tf]))
    kwargs["fields"] = return_fields
    if rerank:
        kwargs["rerank"] = {
            "model": os.getenv("RAG_RERANK_MODEL", "bge-reranker-v2-m3"),
            "top_n": int(top_k),
            "rank_fields": [tf],
        }
        query["top_k"] = max(int(top_k), 20)  # over-fetch before rerank

    # Try the modern method names in order; retry once without 'fields' if the
    # server rejects the field selection.
    last_err = None
    for method_name in ("search", "search_records"):
        method = getattr(idx, method_name, None)
        if not callable(method):
            continue
        for attempt_kwargs in (kwargs, {k: v for k, v in kwargs.items() if k != "fields"}):
            try:
                resp = method(**attempt_kwargs)
                return _extract_hits(resp)
            except TypeError as e:
                last_err = e
                continue  # signature mismatch -> try without fields / next method
            except Exception as e:
                last_err = e
                break  # real runtime error for this method -> try next method
    raise PineconeUnavailable(f"Pinecone search failed: {last_err}")
