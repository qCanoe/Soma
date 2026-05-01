from music_ai_module.knowledge.graph_store import GraphStore


def test_merge_extraction_requires_verbatim_quote() -> None:
    store = GraphStore()
    chunk = "Alpha beta gamma delta."
    entities = [
        {"type": "Condition", "label": "Alpha"},
        {"type": "Symptom", "label": "Beta"},
    ]
    relations_ok = [
        {
            "subject": "Alpha",
            "predicate": "RELATED_TO",
            "object": "Beta",
            "quote": "Alpha beta",
        }
    ]
    n, e = store.merge_extraction(
        entities,
        relations_ok,
        "chunk1",
        chunk,
        "test-model",
        "now",
    )
    assert n == 2
    assert e == 1

    relations_bad = [
        {
            "subject": "Alpha",
            "predicate": "RELATED_TO",
            "object": "Beta",
            "quote": "not in chunk",
        }
    ]
    store2 = GraphStore()
    store2.merge_extraction(entities, relations_ok, "c", chunk, "m", "t")
    store2.merge_extraction(entities, relations_bad, "c", chunk, "m", "t")
    assert len(store2.edges) == 1
