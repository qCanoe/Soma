"""Apply GraphRAG retrieval + deterministic clinical safety rules to Layer-2 output."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from ..config import SystemConfig
from ..models import StaticUserProfile
from .retriever import GraphRetriever, default_retriever_from_disk
from .schemas import ClinicalAuditResult, RetrievalHit


def build_audit_query(
    profile: StaticUserProfile,
    processed_params: Dict[str, Any],
    user_intent: Optional[str],
) -> str:
    state = processed_params.get("state") or {}
    parts: List[str] = []
    if user_intent:
        parts.append(user_intent)
    rp = state.get("recovery_priority")
    if rp:
        parts.append(str(rp))
    ss = state.get("stress_state")
    if ss:
        parts.append(str(ss))
    if profile.chronic_stress_sources:
        parts.append(" ".join(profile.chronic_stress_sources))
    if profile.sound_sensitivity.lower() == "high":
        parts.append("sound sensitivity hyperacusis gentle dynamics")
    if profile.therapy_goal:
        parts.append(profile.therapy_goal)
    return " ".join(parts).strip()


class ClinicalMusicAuditor:
    """Combine GraphRAG hits with rule-based safety overlays (wellness scope)."""

    def __init__(
        self,
        config: SystemConfig,
        retriever: Optional[GraphRetriever] = None,
    ) -> None:
        self.config = config
        self._retriever = retriever

    def _retriever_lazy(self) -> GraphRetriever:
        if self._retriever is None:
            self._retriever = default_retriever_from_disk(self.config)
        return self._retriever

    def audit(
        self,
        profile: StaticUserProfile,
        processed_params: Dict[str, Any],
        user_intent: Optional[str] = None,
        top_k: int = 5,
    ) -> ClinicalAuditResult:
        query = build_audit_query(profile, processed_params, user_intent)
        hits: List[RetrievalHit] = []
        try:
            hits = self._retriever_lazy().retrieve(query, top_k=top_k)
        except Exception:
            hits = []

        state = processed_params.get("state") or {}
        recovery = str(state.get("recovery_priority") or "").lower()
        stress = str(state.get("stress_state") or "").lower()
        arousal = float(state.get("arousal_score") or 0.0)

        bpm_min: Optional[int] = None
        bpm_max: Optional[int] = None
        f_st: Optional[bool] = None
        f_hf: Optional[bool] = None
        f_pr: Optional[bool] = None
        safety_notes: List[str] = []
        suffix_parts: List[str] = []

        if recovery == "sleep":
            bpm_max = min(bpm_max or 85, 85)
            safety_notes.append("Sleep-oriented session: favour slower tempo and soft textures.")
            suffix_parts.append("sleep-supportive, minimal stimulation")
        if recovery == "grounding" or stress == "high" or arousal >= 66:
            f_st = True
            f_hf = True
            f_pr = True
            safety_notes.append("High arousal / grounding: avoid startling transients and percussion.")
            suffix_parts.append("grounding, trauma-informed gentle dynamics")
        if profile.sound_sensitivity.lower() == "high":
            f_st = True
            f_hf = True
            f_pr = True
            safety_notes.append("Sound sensitivity: conservative dynamics and timbre.")
            suffix_parts.append("sound-sensitive friendly")

        for h in hits[:2]:
            src = h.chunk.source_id
            snippet = h.chunk.text[:120].replace("\n", " ")
            safety_notes.append(f"Retrieved: {src} — {snippet}…")

        ev = [h.to_dict() for h in hits[:5]]
        anchor = ""
        if suffix_parts:
            anchor = "Evidence-aware: " + "; ".join(suffix_parts)[: self.config.knowledge_max_anchor_chars]

        return ClinicalAuditResult(
            query_used=query,
            hits=hits,
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            enforce_forbid_sharp_transients=f_st,
            enforce_forbid_high_freq_peaks=f_hf,
            enforce_forbid_percussive_hits=f_pr,
            emotional_anchor_suffix=anchor,
            safety_notes=safety_notes[:12],
            evidence_summary=[f"{x.get('chunk_id')}:{x.get('score'):.3f}" for x in ev],
        )


def apply_audit_to_processed(
    processed_params: Dict[str, Any],
    audit: ClinicalAuditResult,
    config: SystemConfig,
) -> Dict[str, Any]:
    """Return a shallow-copied processed_params with merged music_strategy and clinical_audit."""
    out = deepcopy(processed_params)
    ms = dict(out.get("music_strategy") or {})
    tempo = int(ms.get("tempo_bpm") or config.min_bpm)

    if audit.bpm_min is not None:
        tempo = max(tempo, audit.bpm_min)
    if audit.bpm_max is not None:
        tempo = min(tempo, audit.bpm_max)
    tempo = int(max(config.min_bpm, min(config.max_bpm, tempo)))
    ms["tempo_bpm"] = tempo

    if audit.enforce_forbid_sharp_transients is True:
        ms["forbid_sharp_transients"] = True
    if audit.enforce_forbid_high_freq_peaks is True:
        ms["forbid_high_freq_peaks"] = True
    if audit.enforce_forbid_percussive_hits is True:
        ms["forbid_percussive_hits"] = True

    if audit.emotional_anchor_suffix:
        base = str(ms.get("emotional_anchor_description") or "")
        ms["emotional_anchor_description"] = (base + " " + audit.emotional_anchor_suffix).strip()

    out["music_strategy"] = ms
    out["clinical_audit"] = audit.to_dict()
    return out
