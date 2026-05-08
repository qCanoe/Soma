"""GraphRAG retrieval: dense chunk retrieval + graph neighbourhood expansion."""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Sequence, Set, Tuple

import numpy as np

from ..config import SystemConfig
from .embeddings import EmbeddingService, cosine_top_k
from .fetcher import load_chunks_jsonl
from .graph_store import GraphStore
from .paths import resolved_knowledge_dir
from .schemas import GraphEdge, RetrievalHit, SourceChunk

_LATIN_STOP = frozenset(
    {
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
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "her",
        "was",
        "one",
        "our",
        "out",
        "day",
        "get",
        "has",
        "him",
        "his",
        "how",
        "its",
        "may",
        "new",
        "now",
        "old",
        "see",
        "two",
        "way",
        "who",
        "boy",
        "did",
        "let",
        "put",
        "say",
        "she",
        "too",
        "use",
    }
)

_RE_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_RE_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")


def _normalize_query_text(q: str) -> str:
    return unicodedata.normalize("NFKC", q or "").strip()


def tokenize_for_retrieval(q: str) -> Set[str]:
    """
    Mixed-script tokens for lexical fallback / hybrid reranking.

    - Latin-ish tokens: alphanumeric word of length ≥ 3 (after NFKC lowercase).
    - CJK (Han): overlapping bigrams per contiguous Han run; single Han kept as one token.
    """
    text = _normalize_query_text(q).lower()
    out: Set[str] = set()
    for m in _RE_LATIN.finditer(text):
        w = m.group()
        if w not in _LATIN_STOP:
            out.add(w)
    for m in _RE_CJK_RUN.finditer(text):
        s = m.group()
        if len(s) >= 2:
            for i in range(len(s) - 1):
                out.add(s[i : i + 2])
        else:
            out.add(s)
    return out


def _lexical_scores_for_chunks(
    q_tokens: Set[str], chunks: Sequence[SourceChunk]
) -> List[Tuple[int, float]]:
    if not q_tokens:
        return [(i, 0.0) for i in range(len(chunks))]
    scores: List[Tuple[int, float]] = []
    ntok = len(q_tokens)
    for i, ch in enumerate(chunks):
        hay = _normalize_query_text(ch.text).lower()
        hit = sum(1 for t in q_tokens if t in hay)
        scores.append((i, float(hit) / max(ntok, 1)))
    scores.sort(key=lambda x: -x[1])
    return scores


def _keyword_scores(query: str, chunks: Sequence[SourceChunk]) -> List[Tuple[int, float]]:
    return _lexical_scores_for_chunks(tokenize_for_retrieval(query), chunks)


def _fuse_dense_lexical(
    dense_pairs: List[Tuple[int, float]],
    lexical_sorted: List[Tuple[int, float]],
    top_k: int,
    w_lex: float,
) -> List[Tuple[int, float]]:
    """Combine cosine similarity with normalized lexical overlap."""
    w_lex = max(0.0, min(1.0, w_lex))
    if w_lex <= 0.0 or not dense_pairs:
        return dense_pairs[:top_k]
    lex_map: Dict[int, float] = {i: s for i, s in lexical_sorted}
    dense_map = {i: s for i, s in dense_pairs}
    lexical_top_indices = [i for i, _ in lexical_sorted[: max(top_k * 2, top_k)]]
    cand: Set[int] = set(dense_map) | set(lexical_top_indices)
    fused: List[Tuple[int, float]] = []
    for i in cand:
        d = float(dense_map.get(i, 0.0))
        lx = float(lex_map.get(i, 0.0))
        fused.append((i, (1.0 - w_lex) * d + w_lex * lx))
    fused.sort(key=lambda x: -x[1])
    return fused[:top_k]


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
        n = len(self.chunks)
        tk = min(top_k, n) if n else 0

        if self.chunks:
            lexical_all = _keyword_scores(query, self.chunks)
            if self.config.llm_api_key.strip():
                try:
                    self._ensure_matrix()
                    if self._doc_mat is not None and self._doc_mat.size > 0:
                        qnorm = _normalize_query_text(query)
                        qv = self._emb.embed([qnorm])[0]
                        dense = cosine_top_k(qv, self._doc_mat, tk)
                        w_lex = getattr(
                            self.config,
                            "knowledge_hybrid_lexical_weight",
                            0.0,
                        )
                        pairs = _fuse_dense_lexical(
                            dense,
                            lexical_all,
                            tk,
                            float(w_lex),
                        )
                except Exception:
                    pairs = []

            if not pairs:
                pairs = lexical_all[:tk]

        q_toks = tokenize_for_retrieval(query)
        for idx, score in pairs:
            chunk = self.chunks[idx]
            labels: List[str] = []
            edges_out: List[GraphEdge] = []
            chunk_preview = _normalize_query_text(chunk.text[:500])
            tokens = q_toks | tokenize_for_retrieval(chunk_preview)
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
