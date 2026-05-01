"""OpenAI-compatible embeddings with JSONL cache on disk."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
from openai import OpenAI

from ..config import SystemConfig


def _cache_key(model: str, text: str) -> str:
    h = hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()
    return h[:24]


def load_embedding_cache(path: Path) -> Dict[str, List[float]]:
    if not path.is_file():
        return {}
    cache: Dict[str, List[float]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        cache[row["key"]] = row["embedding"]
    return cache


def save_embedding_cache(path: Path, cache: Dict[str, List[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for key, emb in cache.items():
            f.write(json.dumps({"key": key, "embedding": emb}, ensure_ascii=False) + "\n")


class EmbeddingService:
    def __init__(self, config: SystemConfig, cache_path: Path) -> None:
        self.config = config
        self.cache_path = cache_path
        self._cache = load_embedding_cache(cache_path)
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.config.llm_api_key,
                base_url=self.config.llm_base_url,
            )
        return self._client

    def embed(
        self,
        texts: Sequence[str],
        model: str | None = None,
    ) -> np.ndarray:
        """Return matrix shape (len(texts), dim)."""
        mdl = model or self.config.embedding_model
        client = self._get_client()
        vectors: List[List[float]] = []
        to_fetch: List[str] = []
        keys: List[str] = []
        for t in texts:
            k = _cache_key(mdl, t)
            keys.append(k)
            if k in self._cache:
                vectors.append(self._cache[k])  # placeholder slot
            else:
                vectors.append([])
                to_fetch.append(t)

        if to_fetch:
            resp = client.embeddings.create(model=mdl, input=list(to_fetch))
            i_fetch = 0
            for i, row in enumerate(vectors):
                if row:
                    continue
                emb = resp.data[i_fetch].embedding
                i_fetch += 1
                vectors[i] = emb
                self._cache[keys[i]] = emb
            save_embedding_cache(self.cache_path, self._cache)

        mat = np.array(vectors, dtype=np.float64)
        return mat


def cosine_top_k(query_vec: np.ndarray, doc_mat: np.ndarray, k: int) -> List[tuple[int, float]]:
    """Return list of (row_index, score) sorted descending."""
    if doc_mat.size == 0:
        return []
    q = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    d = doc_mat / (np.linalg.norm(doc_mat, axis=1, keepdims=True) + 1e-9)
    sims = d @ q
    order = np.argsort(-sims)[:k]
    return [(int(i), float(sims[i])) for i in order]
