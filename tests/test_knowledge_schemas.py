from music_ai_module.knowledge.schemas import (
    EdgeEvidence,
    GraphEdge,
    GraphNode,
    SourceChunk,
    stable_node_id,
)


def test_stable_node_id_slugs() -> None:
    assert stable_node_id("Condition", "Anxiety").startswith("condition")
    assert "anxiety" in stable_node_id("Condition", "Anxiety")


def test_graph_node_roundtrip() -> None:
    n = GraphNode(id="n1", type="Condition", label="Test", properties={"k": 1})
    d = n.to_dict()
    m = GraphNode.from_dict(d)
    assert m.id == "n1" and m.properties["k"] == 1


def test_edge_evidence_roundtrip() -> None:
    ev = EdgeEvidence(
        chunk_id="c1",
        quote="hello world",
        confidence=0.9,
        extracted_at="t",
        model="m",
    )
    e = GraphEdge(
        id="e1",
        source_id="a",
        target_id="b",
        predicate="MAY_HELP",
        evidence=ev,
    )
    d = e.to_dict()
    assert d["evidence"]["quote"] == "hello world"
    e2 = GraphEdge.from_dict(d)
    assert e2.evidence and e2.evidence.chunk_id == "c1"


def test_source_chunk_roundtrip() -> None:
    c = SourceChunk(
        chunk_id="x",
        source_id="s",
        url="http://example.com",
        text="body",
        start_char=0,
        end_char=4,
        title="t",
    )
    c2 = SourceChunk.from_dict(c.to_dict())
    assert c2.text == "body"
