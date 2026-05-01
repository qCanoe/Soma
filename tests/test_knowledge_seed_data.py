import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "data" / "knowledge"


def test_seed_sources_cover_core_clinical_music_topics() -> None:
    data = yaml.safe_load((KNOWLEDGE_DIR / "sources.yaml").read_text(encoding="utf-8"))
    sources = data["sources"]
    ids = {s["id"] for s in sources}

    assert len(sources) >= 8
    assert {
        "nccih_music_health",
        "nccih_mbi_toolkit",
        "nccih_anxiety_complementary",
        "who_icd11_license",
        "pmc_adhd_music_review",
        "pmc_hyperacusis_sound_therapy",
        "pmc_ptsd_music_therapy",
        "frontiers_sleep_music_elements",
    }.issubset(ids)


def test_seed_chunks_and_graph_evidence_are_traceable() -> None:
    chunks = {}
    for line in (KNOWLEDGE_DIR / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            chunks[row["chunk_id"]] = row

    graph = json.loads((KNOWLEDGE_DIR / "graph.json").read_text(encoding="utf-8"))
    nodes = graph["nodes"]
    edges = graph["edges"]

    assert len(chunks) >= 8
    assert len(nodes) >= 20
    assert len(edges) >= 18

    for edge in edges:
        evidence = edge.get("evidence")
        assert evidence, edge["id"]
        chunk = chunks[evidence["chunk_id"]]
        assert evidence["quote"] in chunk["text"], edge["id"]
        assert edge["source_id"] in nodes, edge["id"]
        assert edge["target_id"] in nodes, edge["id"]
