from music_ai_module.config import SystemConfig
from music_ai_module.knowledge.graph_store import GraphStore, seed_store_from_hand_entries
from music_ai_module.knowledge.retriever import GraphRetriever
from music_ai_module.knowledge.schemas import GraphEdge, GraphNode, SourceChunk, EdgeEvidence


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
