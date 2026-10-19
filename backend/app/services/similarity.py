"""
Text embeddings for similarity retrieval (Lab 4).

Default: a local sentence-embedding model (fastembed, BAAI/bge-small-en-v1.5,
~67 MB, downloaded once into ./data/models). It compares MEANING — "database
design" is close to "SQL schemas and normalisation" even with no shared words.
No API key and no data leaves the server.

Fallback: hashed bag-of-words vectors (lexical overlap only), used when
EMBEDDING_BACKEND=hashed or the model can't be loaded (e.g. offline first run).
"""
import hashlib
import logging
import math
import os
import re
import threading
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Sequence

from app.config import settings

logger = logging.getLogger(__name__)

DIMENSIONS = 2048
_STOP = {"the", "and", "for", "with", "a", "an", "of", "to", "in", "on", "is", "are", "be", "or", "as", "at", "by",
         "learning", "resource", "resources", "skill", "skills", "required", "requirements"}

_model: Any = None
_model_failed = False
_lock = threading.Lock()


# ----------------------------- model embeddings -----------------------------

def _load_model():
    global _model, _model_failed
    if settings.EMBEDDING_BACKEND.lower() != "model" or _model_failed:
        return None
    if _model is not None:
        return _model
    with _lock:
        if _model is None and not _model_failed:
            try:
                from fastembed import TextEmbedding
                _model = TextEmbedding(model_name=settings.EMBEDDING_MODEL,
                                       cache_dir=os.path.abspath(settings.EMBEDDING_CACHE_DIR))
                logger.info("Embedding model loaded: %s", settings.EMBEDDING_MODEL)
            except Exception as exc:   # offline / not installed → lexical fallback
                _model_failed = True
                logger.warning("Embedding model unavailable (%s); using hashed embeddings.", exc)
    return _model


def backend_name() -> str:
    return f"model:{settings.EMBEDDING_MODEL}" if _load_model() is not None else "hashed"


@lru_cache(maxsize=8192)
def _model_vector(text: str) -> tuple:
    vec = next(iter(_load_model().embed([text])))
    norm = math.sqrt(float((vec * vec).sum())) or 1.0
    return tuple(float(x) / norm for x in vec)


# ----------------------------- hashed embeddings ----------------------------

def _tokens(text: str):
    words = [w for w in re.findall(r"[a-z0-9+#.]+", (text or "").lower()) if w not in _STOP and len(w) > 1]
    words = [w.strip(".") for w in words if w.strip(".")]
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]


def _bucket(token: str):
    h = int(hashlib.md5(token.encode()).hexdigest(), 16)
    return h % DIMENSIONS, (1.0 if (h >> 64) & 1 else -1.0)


def _hashed(text: str) -> Dict[int, float]:
    counts: Dict[str, int] = {}
    for t in _tokens(text):
        counts[t] = counts.get(t, 0) + 1
    vec: Dict[int, float] = {}
    for tok, n in counts.items():
        i, sign = _bucket(tok)
        vec[i] = vec.get(i, 0.0) + sign * (1.0 + math.log(n))
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {i: v / norm for i, v in vec.items()}


# ----------------------------- public API -----------------------------------

def embed(text: str):
    """Unit-length vector for `text` (dense tuple from the model, or sparse dict when hashed)."""
    text = (text or "").strip()[:2000]
    if _load_model() is not None and text:
        return _model_vector(text)
    return _hashed(text)


def related_threshold() -> float:
    """Below this, two texts are treated as unrelated (the model's scores sit around 0.5 for unrelated text)."""
    return 0.6 if _load_model() is not None else 0.05


def embed_many(texts: Sequence[str]) -> List[Any]:
    return [embed(t) for t in texts]


def cosine(a, b) -> float:
    if isinstance(a, dict) and isinstance(b, dict):
        if len(a) > len(b):
            a, b = b, a
        return round(max(0.0, sum(v * b.get(i, 0.0) for i, v in a.items())), 4)
    if isinstance(a, tuple) and isinstance(b, tuple) and a and b:
        return round(max(0.0, sum(x * y for x, y in zip(a, b))), 4)
    return 0.0


def profile_text(skills: Iterable[str], roles: Iterable[str] = (), projects: Iterable[str] = ()) -> str:
    """The text used to compare students: skills, target roles and project technologies."""
    return " ".join(list(skills) + list(roles) + list(projects))
