"""Local Embedding (PROJECT_SPEC.md section 28).

`sentence-transformers` is a heavy optional dependency (pulls in PyTorch) —
it is imported lazily inside functions, not at module load time, so the
rest of the app works fine when it isn't installed yet (section 41: core
features must work without Local AI). The model itself is never
auto-downloaded (section 42): the user points this at a local folder they
prepared themselves, or the feature stays off with a clear message.

HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE are forced on at import time so that
even a misconfigured path can't accidentally trigger a Hugging Face Hub
network call — this is enforced in code, not just by convention.
"""
from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "embedding"


class LocalModelNotInstalledError(RuntimeError):
    """Local AI model is not installed. (PROJECT_SPEC.md section 42's exact
    required message text is used verbatim wherever this is shown in the UI.)"""


def is_model_available(path: str | Path | None) -> bool:
    if not path:
        return False
    p = Path(path)
    return p.is_dir() and any(p.iterdir())


def load_model(path: str | Path):
    if not is_model_available(path):
        raise LocalModelNotInstalledError("Local AI model is not installed.")
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise LocalModelNotInstalledError(
            "sentence-transformers is not installed. Local AI features stay off until it is."
        ) from exc

    return SentenceTransformer(str(path), local_files_only=True)


def embed_texts(model, texts: list[str]) -> np.ndarray:
    return np.asarray(model.encode(texts, normalize_embeddings=True))


def cosine_similarities(query_vec: np.ndarray, candidate_vecs: np.ndarray) -> np.ndarray:
    """Vectors are assumed pre-normalized (embed_texts does this), so cosine
    similarity is just the dot product."""
    return candidate_vecs @ query_vec
