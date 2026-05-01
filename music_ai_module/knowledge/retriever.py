"""GraphRAG retrieval: dense chunk retrieval + graph neighbourhood expansion."""

from __future__ import annotations

from typing import List, Set

import numpy as np

from ..config import SystemConfig
from .embeddings import EmbeddingService, cosine_top_k
from .fetcher import load_chunks_jsonl
from .graph_store import GraphStore
from .paths import resolved_knowledge_dir
from .schemas import GraphEdge, RetrievalHit, SourceChunk


def _query_tokens(q: str) -> Set[str]:
    import re

    words = re.findall(r"[a-zA-Z]{4,}", q.lower())
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "your",
        "have",
        "been",
        "were",
        "will",
    }
    return {w for w in words if w not in stop}


def _keyword_scores(query: str, chunks: List[SourceChunk]) -> List[tuple[int, float]]:
    q_tokens = _query_tokens(query)
    if not q_tokens:
        return [(i, 0.0) for i in range(len(chunks))]
    scores: List[tuple[int, float]] = []
    for i, ch in enumerate(chunks):
        text_l = ch.text.lower()
        hit = sum(1 for t in q_tokens if t in text_l)
        scores.append((i, float(hit) / max(len(q_tokens), 1)))
    scores.sort(key=lambda x: -x[1])
    return scores


class GraphRetriever:
    def __init__(
        self,
        config: SystemConfig,
        chunks: List[SourceChunk],
        graph: GraphStore,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.config = config
        self.chunks = chunks
        self.graph = graph
        kdir = resolved_knowledge_dir(config)
        cache_path = kdir / "embeddings.jsonl"
        self._emb = embedding_service or EmbeddingService(config, cache_path)
        self._doc_mat = None  # lazy
        self._chunk_texts = [c.text for c in chunks]

    def _ensure_matrix(self) -> None:
        if self._doc_mat is not None:
            return
        if not self._chunk_texts:
            self._doc_mat = np.zeros((0, 1), dtype=np.float64)
            return
        self._doc_mat = self._emb.embed(self._chunk_texts)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        expansion_hops: int = 1,
    ) -> List[RetrievalHit]:
        hits: List[RetrievalHit] = []
        pairs: List[tuple[int, float]] = []

        if self.chunks:
            if self.config.llm_api_key.strip():
                try:
                    self._ensure_matrix()
                    if self._doc_mat is not None and self._doc_mat.size > 0:
                        qv = self._emb.embed([query])[0]
                        pairs = cosine_top_k(
                            qv, self._doc_mat, min(top_k, len(self.chunks))
                        )
                except Exception:
                    pairs = []

            if not pairs:
                pairs = _keyword_scores(query, self.chunks)[: min(top_k, len(self.chunks))]

        for idx, score in pairs:
            chunk = self.chunks[idx]
            labels: List[str] = []
            edges_out: List[GraphEdge] = []
            tokens = _query_tokens(query) | _query_tokens(chunk.text[:500])
            for tok in tokens:
                for node in self.graph.find_nodes_by_label_substr(tok, limit=8):
                    nid = node.id
                    nbrs = self.graph.neighbors(nid, hops=expansion_hops)
                    nbrs.add(nid)
                    for x in nbrs:
                        gn = self.graph.get_node(x)
                        if gn:
                            labels.append(gn.label)
                    edges_out.extend(self.graph.edges_incident(nbrs))
            labels = list(dict.fromkeys(labels))[:24]
            edges_out = edges_out[:40]
            hits.append(
                RetrievalHit(
                    chunk=chunk,
                    score=score,
                    related_node_labels=labels,
                    related_edges=edges_out,
                )
            )
        return hits


def default_retriever_from_disk(config: SystemConfig) -> GraphRetriever:
    kdir = resolved_knowledge_dir(config)
    chunks = load_chunks_jsonl(kdir / "chunks.jsonl")
    graph = GraphStore.load(kdir / "graph.json")
    return GraphRetriever(config, chunks, graph)
