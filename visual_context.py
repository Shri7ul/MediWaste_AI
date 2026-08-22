# visual_context.py
"""
Visual context estimation with CLIP (zero-shot).

Produces a coarse, *estimated* context for a waste image — whether it looks
used, contaminated, blood-stained, or chemical-related. These are decision
*inputs* for context-dependent items (e.g. gloves/PPE) and display hints; they
are explicitly NOT clinical ground truth and are labelled as estimates in the
UI.

The CLIP model is loaded once (lazily) and cached for the process lifetime, so
it is never reloaded per request.
"""

import threading

import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_NAME = "openai/clip-vit-base-patch32"

# Each key maps to [positive_prompt, negative_prompt]; index 0 winning -> "YES".
CONTEXT_PROMPTS = {
    "Used": [
        "a used medical item after patient treatment",
        "a new unused clean medical item",
    ],
    "Contaminated": [
        "medical waste contaminated with blood or body fluid",
        "clean medical waste without contamination",
    ],
    "Blood": [
        "medical waste with visible blood stains",
        "medical waste with no visible blood",
    ],
    "Chemical": [
        "a chemical container, reagent, or disinfectant",
        "an item with no chemicals",
    ],
}

_lock = threading.Lock()
_model = None
_processor = None


def _load():
    """Load and cache the CLIP model/processor exactly once."""
    global _model, _processor
    if _model is None:
        with _lock:
            if _model is None:
                print("Loading CLIP context model...")
                m = CLIPModel.from_pretrained(MODEL_NAME).to(DEVICE)
                m.eval()
                _processor = CLIPProcessor.from_pretrained(MODEL_NAME)
                _model = m
                print("CLIP context model ready.")
    return _model, _processor


def clip_predict(image, texts):
    """Pairwise/grouped CLIP scoring for an ad-hoc prompt list (kept for reuse).

    Returns the softmax over the supplied `texts` for a single image.
    """
    model, processor = _load()
    inputs = processor(text=texts, images=image, return_tensors="pt", padding=True)
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
    probs = outputs.logits_per_image.softmax(dim=1)
    return probs[0].cpu().numpy()


def _flatten_prompts():
    """Flatten CONTEXT_PROMPTS into one ordered text list + per-key (pos, neg)
    index spans. Computed once at import since the prompt table is static."""
    texts, spans = [], {}
    for key, prompts in CONTEXT_PROMPTS.items():
        start = len(texts)
        texts.extend(prompts)               # [positive, negative]
        spans[key] = (start, start + 1)      # (positive_idx, negative_idx)
    return texts, spans


# Precomputed flat prompt list + index bookkeeping (module-level, built once).
_ALL_TEXTS, _PROMPT_SPANS = _flatten_prompts()


def predict_visual_context(image_path):
    """
    Return a context estimate:
        {"Used": "YES"/"NO", "Used_confidence": float, ... for each dimension}

    The image is encoded ONCE and scored against ALL context prompts in a single
    forward pass (previously the image was re-encoded once per dimension). Each
    CLIP image-text logit is independent of the other texts in the batch, so a
    per-dimension pairwise softmax over each (positive, negative) pair yields the
    SAME result as the previous per-pair calls — this is a batching/latency
    optimisation, NOT a change to the model, prompts, or decision logic.
    """
    image = Image.open(image_path).convert("RGB")
    model, processor = _load()

    inputs = processor(text=_ALL_TEXTS, images=image,
                       return_tensors="pt", padding=True)
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
    # Raw per-(image,text) similarity logits for the single image: shape [n_texts].
    logits = outputs.logits_per_image[0]

    context = {}
    for key, (pos_i, neg_i) in _PROMPT_SPANS.items():
        pair = torch.softmax(logits[[pos_i, neg_i]], dim=0)
        pos_prob = float(pair[0])
        neg_prob = float(pair[1])
        # Positive wins ties (matches the previous argmax, which returned index 0).
        is_yes = pos_prob >= neg_prob
        context[key] = "YES" if is_yes else "NO"
        context[key + "_confidence"] = round(pos_prob if is_yes else neg_prob, 3)
    context["_estimate"] = True  # marker: these are estimates, not ground truth
    return context
