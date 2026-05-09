from music_ai_module.config import SystemConfig
from music_ai_module.knowledge.graph_store import GraphStore, seed_store_from_hand_entries
from music_ai_module.knowledge.retriever import (
    GraphRetriever,
    _fuse_dense_lexical,
    tokenize_for_retrieval,
)
from music_ai_module.knowledge.schemas import EdgeEvidence, GraphEdge, GraphNode, SourceChunk


def test_tokenize_mixed_cn_en() -> None:
    toks = tokenize_for_retrieval("焦虑 sleep PTSD therapy")
    assert "sleep" in toks
    assert "ptsd" in toks
    assert "therapy" in toks
    assert "焦虑" in toks


def test_retriever_chinese_lexical_fallback() -> None:
    cfg = SystemConfig()
    cfg.llm_api_key = ""
    chunks = [
        SourceChunk(
            chunk_id="c_noise",
            source_id="s",
            url="http://example.com",
            text="Today's weather forecast is unrelated.",
            start_char=0,
            end_char=30,
            title="t",
        ),
        SourceChunk(
            chunk_id="c_cn",
            source_id="s",
            url="http://example.com",
            text="音乐干预可以改善焦虑患者的睡眠质量与情绪调节。",
            start_char=0,
            end_char=50,
            title="t",
        ),
    ]
    graph = GraphStore()
    r = GraphRetriever(cfg, chunks, graph)
    hits = r.retrieve("焦虑 睡眠", top_k=1)
    assert hits and hits[0].chunk.chunk_id == "c_cn"


def test_fuse_dense_lexical_prefers_lexical_boost() -> None:
    lexical = [(0, 0.9), (1, 0.8), (2, 0.1)]
    dense = [(2, 0.99), (1, 0.5)]  # index 2 wins dense only
    fused = _fuse_dense_lexical(dense, lexical, top_k=1, w_lex=0.5)
    assert fused[0][0] == 1


def test_retriever_keyword_fallback() -> None:
    cfg = SystemConfig()
    cfg.llm_api_key = ""
    chunks = [
        SourceChunk(
            chunk_id="c1",
            source_id="s",
            url="http://example.com",
            text="Music-based interventions for anxiety and sleep quality.",
            start_char=0,
            end_char=50,
            title="t",
        )
    ]
    seed = {
        "nodes": [
            GraphNode(
                id="condition_anxiety",
                type="Condition",
                label="Anxiety",
                properties={},
            ).to_dict()
        ],
        "edges": [],
    }
    graph = seed_store_from_hand_entries(seed)
    r = GraphRetriever(cfg, chunks, graph)
    hits = r.retrieve("anxiety sleep music", top_k=2)
    assert hits
    assert hits[0].chunk.chunk_id == "c1"
    assert any("Anxiety" in lab for lab in hits[0].related_node_labels)


def test_graph_neighbors() -> None:
    ev = EdgeEvidence(
        chunk_id="c",
        quote="q",
        confidence=1.0,
        extracted_at="t",
        model="m",
    )
    g = GraphStore()
    g.upsert_node(GraphNode("a", "Condition", "A", {}))
    g.upsert_node(GraphNode("b", "Condition", "B", {}))
    g.add_edge(GraphEdge("e1", "a", "b", "RELATED_TO", ev))
    nbrs = g.neighbors("a", hops=1)
    assert "a" in nbrs and "b" in nbrs
