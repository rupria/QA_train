"""Lazy, local-only embedding inference after the model is installed."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .store import ModelStore


def format_query(instruction: str, query: str) -> str:
    instruction = instruction.strip()
    query = query.strip()
    if not instruction or not query:
        raise ValueError("instruction and query must be non-empty")
    return f"Instruct: {instruction}\nQuery: {query}"


class LocalEmbeddingRuntime:
    def __init__(
        self,
        store: ModelStore | None = None,
        model_key: str = "embedding",
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.store = store or ModelStore()
        self.model_key = model_key
        self.model_factory = model_factory or _sentence_transformer
        self._model = None

    def load(self):
        if self._model is None:
            status = self.store.ensure(self.model_key)
            self._model = self.model_factory(status.path, local_files_only=True)
        return self._model

    def encode_queries(self, queries: Sequence[str]):
        spec = self.store.manifest.model(self.model_key)
        texts = [format_query(spec.query_instruction, query) for query in queries]
        if not texts:
            raise ValueError("queries must contain at least one item")
        return self.load().encode(texts, normalize_embeddings=True, convert_to_numpy=True)

    def encode_documents(self, documents: Sequence[str]):
        texts = [document.strip() for document in documents]
        if not texts or any(not item for item in texts):
            raise ValueError("documents must contain non-empty text")
        return self.load().encode(texts, normalize_embeddings=True, convert_to_numpy=True)


def _sentence_transformer(path: str, **kwargs):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers and transformers are required for local embedding inference"
        ) from exc
    return SentenceTransformer(path, trust_remote_code=False, **kwargs)
