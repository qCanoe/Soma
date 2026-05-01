"""CLI for ingesting sources, querying GraphRAG, and auditing demo cases."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from ..config import SystemConfig
from ..models import AppleWatchBiometrics, StaticUserProfile
from ..pipeline import MusicAIPipeline
from .auditor import ClinicalMusicAuditor
from .extractor import extract_from_chunk
from .fetcher import append_chunks_jsonl, fetch_and_chunk_source, load_chunks_jsonl
from .graph_store import GraphStore
from .paths import resolved_knowledge_dir
from .retriever import GraphRetriever
from .sources import load_sources


def cmd_ingest(args: argparse.Namespace) -> None:
    cfg = SystemConfig()
    kdir = resolved_knowledge_dir(cfg)
    kdir.mkdir(parents=True, exist_ok=True)
    raw_dir = kdir / "raw"
    sources = load_sources(args.sources)
    graph_path = kdir / "graph.json"
    chunks_path = kdir / "chunks.jsonl"
    ext_path = kdir / "extractions.jsonl"

    store = GraphStore.load(graph_path)

    if args.reset:
        if chunks_path.is_file():
            chunks_path.unlink()
        if ext_path.is_file():
            ext_path.unlink()

    for src in sources:
        text, chunks = fetch_and_chunk_source(
            src,
            chunk_size=cfg.knowledge_chunk_size,
            overlap=cfg.knowledge_chunk_overlap,
            raw_dir=raw_dir if src.full_text_allowed else None,
        )
        append_chunks_jsonl(chunks_path, chunks)
        if args.extract:
            now = datetime.now(timezone.utc).isoformat()
            for ch in chunks:
                try:
                    ext = extract_from_chunk(cfg, ch.chunk_id, ch.text)
                except Exception as exc:
                    print(f"[extract skip] {ch.chunk_id}: {exc}")
                    continue
                store.merge_extraction(
                    ext.entities,
                    ext.relations,
                    ch.chunk_id,
                    ch.text,
                    ext.model,
                    now,
                )
                with ext_path.open("a", encoding="utf-8") as ef:
                    ef.write(json.dumps(ext.to_dict(), ensure_ascii=False) + "\n")

    store.save(graph_path)
    print(f"Wrote graph to {graph_path}, chunks appended to {chunks_path}")


def cmd_query(args: argparse.Namespace) -> None:
    cfg = SystemConfig()
    kdir = resolved_knowledge_dir(cfg)
    chunks = load_chunks_jsonl(kdir / "chunks.jsonl")
    graph = GraphStore.load(kdir / "graph.json")
    retr = GraphRetriever(cfg, chunks, graph)
    hits = retr.retrieve(args.text, top_k=args.top_k)
    for i, h in enumerate(hits, 1):
        print(f"--- Hit {i} score={h.score:.4f} chunk={h.chunk.chunk_id}")
        print(h.chunk.text[:400].replace("\n", " "))
        if h.related_node_labels:
            print("  nodes:", ", ".join(h.related_node_labels[:12]))


# Demo cases aligned with data/case.md (minimal fields for pipeline audit smoke test)
DEMO_CASES: Dict[str, Dict[str, Any]] = {
    "case_001": {
        "user_intent": "work anxiety post-work brain tension",
        "profile": dict(
            occupation="software_engineer",
            age=28,
            height_cm=178,
            baseline_heart_rate=62,
            chronic_stress_sources=["work_anxiety"],
            music_preference="neo_soul",
            sound_sensitivity="normal",
        ),
        "bio": dict(
            heart_rate=85,
            heart_rate_variability=38.0,
            respiratory_rate=17,
            environmental_audio_exposure=55.0,
            body_motion=dict(x=0.1, y=0.08, z=0.06),
        ),
    },
    "case_002": {
        "user_intent": "insomnia auditory sensitivity sleep",
        "profile": dict(
            occupation="retiree",
            age=62,
            height_cm=160,
            baseline_heart_rate=70,
            chronic_stress_sources=["sleep_disturbance"],
            music_preference="ambient_classical",
            sound_sensitivity="high",
        ),
        "bio": dict(
            heart_rate=72,
            heart_rate_variability=35.0,
            respiratory_rate=14,
            environmental_audio_exposure=40.0,
            body_motion=dict(x=0.05, y=0.04, z=0.03),
        ),
    },
    "case_003": {
        "user_intent": "attention deficit study distraction focus",
        "profile": dict(
            occupation="student",
            age=21,
            height_cm=175,
            baseline_heart_rate=68,
            chronic_stress_sources=["study_stress"],
            music_preference="minimal_idm",
            sound_sensitivity="normal",
            therapy_goal="focus",
        ),
        "bio": dict(
            heart_rate=78,
            heart_rate_variability=42.0,
            respiratory_rate=16,
            environmental_audio_exposure=50.0,
            body_motion=dict(x=0.15, y=0.12, z=0.1),
        ),
    },
}


def cmd_audit(args: argparse.Namespace) -> None:
    from datetime import datetime

    case = DEMO_CASES.get(args.case)
    if not case:
        raise SystemExit(f"Unknown case {args.case!r}; choose from {list(DEMO_CASES)}")

    profile = StaticUserProfile(**case["profile"])
    b = case["bio"]
    bio = AppleWatchBiometrics(
        timestamp=datetime.now(),
        heart_rate=b["heart_rate"],
        heart_rate_variability=b["heart_rate_variability"],
        respiratory_rate=b["respiratory_rate"],
        environmental_audio_exposure=b["environmental_audio_exposure"],
        body_motion=b["body_motion"],
    )
    pipe = MusicAIPipeline()
    result = pipe.run(
        profile,
        bio,
        use_knowledge_graph=True,
        user_intent=case["user_intent"],
    )
    print(result["prompt"][: min(500, len(result["prompt"]))])
    print("...")
    ca = result["processed_params"].get("clinical_audit")
    if ca:
        print(json.dumps(ca, indent=2, ensure_ascii=False)[:4000])


def main() -> None:
    p = argparse.ArgumentParser(description="MindWave medical music knowledge graph tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest", help="Fetch sources and append chunks (+ optional LLM extract)")
    pi.add_argument("--sources", default="data/knowledge/sources.yaml")
    pi.add_argument("--extract", action="store_true", help="Run LLM extraction (needs API key)")
    pi.add_argument("--reset", action="store_true", help="Delete chunks.jsonl and extractions.jsonl first")
    pi.set_defaults(func=cmd_ingest)

    pq = sub.add_parser("query", help="Dense retrieval over chunks + graph expansion")
    pq.add_argument("text")
    pq.add_argument("--top-k", type=int, default=5)
    pq.set_defaults(func=cmd_query)

    pa = sub.add_parser("audit", help="Run MusicAIPipeline with clinical audit for a demo case")
    pa.add_argument("--case", required=True)
    pa.set_defaults(func=cmd_audit)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
