from music_ai_module.config import SystemConfig
from music_ai_module.knowledge.auditor import (
    ClinicalMusicAuditor,
    apply_audit_to_processed,
    build_audit_query,
)
from music_ai_module.knowledge.graph_store import GraphStore
from music_ai_module.knowledge.retriever import GraphRetriever
from music_ai_module.knowledge.schemas import SourceChunk
from music_ai_module.models import StaticUserProfile


def _minimal_processed(arousal: float, recovery: str, stress: str) -> dict:
    return {
        "rhythm": {"target_bpm": 80, "sympathetic_load": 5, "current_hr": 80},
        "texture": {"hrv_status": "flexible_resilient"},
        "state": {
            "arousal_score": arousal,
            "recovery_priority": recovery,
            "stress_state": stress,
        },
        "music_strategy": {
            "tempo_bpm": 80,
            "genre_style": "ambient",
            "instrument_set": ["piano"],
            "acoustic_texture_description": "soft",
            "emotional_anchor_description": "calm",
            "forbid_sharp_transients": False,
            "forbid_high_freq_peaks": False,
            "forbid_percussive_hits": False,
        },
    }


def test_build_audit_query_includes_intent() -> None:
    p = StaticUserProfile(
        occupation="software_engineer",
        age=30,
        height_cm=175,
        baseline_heart_rate=65,
        chronic_stress_sources=["work"],
    )
    proc = _minimal_processed(20.0, "calm", "low")
    q = build_audit_query(p, proc, "need sleep")
    assert "sleep" in q.lower()


def test_audit_high_arousal_enforces_safeguards() -> None:
    cfg = SystemConfig()
    cfg.llm_api_key = ""
    chunks = [
        SourceChunk(
            chunk_id="c1",
            source_id="s",
            url="http://x",
            text="anxiety interventions promising",
            start_char=0,
            end_char=30,
            title="t",
        )
    ]
    graph = GraphStore()
    retriever = GraphRetriever(cfg, chunks, graph)
    auditor = ClinicalMusicAuditor(cfg, retriever=retriever)
    p = StaticUserProfile(
        occupation="x",
        age=20,
        height_cm=170,
        baseline_heart_rate=60,
    )
    proc = _minimal_processed(70.0, "grounding", "high")
    audit = auditor.audit(p, proc, user_intent="panic overwhelm")
    assert audit.enforce_forbid_percussive_hits is True
    out = apply_audit_to_processed(proc, audit, cfg)
    assert out["music_strategy"]["forbid_percussive_hits"] is True
