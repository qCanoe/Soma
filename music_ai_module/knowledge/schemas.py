"""
Knowledge graph and GraphRAG schemas — nodes, edges, chunks, audit output.

All extracted claims must bind to a source chunk and quoted evidence span.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeType(str, Enum):
    """Allowed ontology node labels."""

    CONDITION = "Condition"
    SYMPTOM = "Symptom"
    BIOMETRIC_MARKER = "BiometricMarker"
    MUSIC_INTERVENTION = "MusicIntervention"
    ACOUSTIC_PARAMETER = "AcousticParameter"
    SAFETY_CONSTRAINT = "SafetyConstraint"
    EVIDENCE_CLAIM = "EvidenceClaim"
    SOURCE = "Source"


class RelationType(str, Enum):
    """Allowed directed edge predicates."""

    INDICATES = "INDICATES"
    MAY_HELP = "MAY_HELP"
    HAS_PARAMETER = "HAS_PARAMETER"
    AVOID_FOR = "AVOID_FOR"
    SUPPORTED_BY = "SUPPORTED_BY"
    CONTRAINDICATED_WITH = "CONTRAINDICATED_WITH"
    RELATED_TO = "RELATED_TO"


def stable_node_id(node_type: str, label: str) -> str:
    """Deterministic id from type + normalized label."""
    import re

    slug = re.sub(r"[^a-z0-9]+", "_", f"{node_type}_{label}".lower()).strip("_")
    return slug[:120] if slug else "node_unknown"


@dataclass
class SourceChunk:
    """A text span from a fetched document, used for citation and embedding."""

    chunk_id: str
    source_id: str
    url: str
    text: str
    start_char: int
    end_char: int
    title: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SourceChunk":
        return cls(**d)


@dataclass
class GraphNode:
    """Graph vertex."""

    id: str
    type: str
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "type": self.type, "label": self.label, "properties": self.properties}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GraphNode":
        return cls(
            id=d["id"],
            type=d["type"],
            label=d["label"],
            properties=dict(d.get("properties") or {}),
        )


@dataclass
class EdgeEvidence:
    """Provenance for one graph edge."""

    chunk_id: str
    quote: str
    confidence: float = 0.8
    extracted_at: str = ""
    model: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EdgeEvidence":
        return cls(
            chunk_id=d["chunk_id"],
            quote=str(d.get("quote") or ""),
            confidence=float(d.get("confidence") or 0.8),
            extracted_at=str(d.get("extracted_at") or ""),
            model=str(d.get("model") or ""),
        )


@dataclass
class GraphEdge:
    """Directed labeled edge with mandatory evidence when from extraction."""

    id: str
    source_id: str
    target_id: str
    predicate: str
    evidence: Optional[EdgeEvidence] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "predicate": self.predicate,
        }
        if self.evidence:
            out["evidence"] = self.evidence.to_dict()
        return out

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GraphEdge":
        ev = d.get("evidence")
        return cls(
            id=d["id"],
            source_id=d["source_id"],
            target_id=d["target_id"],
            predicate=d["predicate"],
            evidence=EdgeEvidence.from_dict(ev) if ev else None,
        )


@dataclass
class ExtractionResult:
    """LLM output for one chunk."""

    chunk_id: str
    entities: List[Dict[str, Any]]
    relations: List[Dict[str, Any]]
    raw_response: str = ""
    model: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "entities": self.entities,
            "relations": self.relations,
            "raw_response": self.raw_response,
            "model": self.model,
        }


@dataclass
class RetrievalHit:
    """One retrieved chunk with score and optional graph context."""

    chunk: SourceChunk
    score: float
    related_node_labels: List[str] = field(default_factory=list)
    related_edges: List[GraphEdge] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk.chunk_id,
            "score": self.score,
            "source_id": self.chunk.source_id,
            "url": self.chunk.url,
            "snippet": self.chunk.text[:280],
            "related_node_labels": self.related_node_labels,
            "edge_count": len(self.related_edges),
        }


@dataclass
class ClinicalAuditResult:
    """Structured output of ClinicalMusicAuditor."""

    query_used: str
    hits: List[RetrievalHit]
    bpm_min: Optional[int] = None
    bpm_max: Optional[int] = None
    enforce_forbid_sharp_transients: Optional[bool] = None
    enforce_forbid_high_freq_peaks: Optional[bool] = None
    enforce_forbid_percussive_hits: Optional[bool] = None
    emotional_anchor_suffix: str = ""
    safety_notes: List[str] = field(default_factory=list)
    evidence_summary: List[str] = field(default_factory=list)
    disclaimer: str = (
        "Wellness music only — not medical diagnosis or treatment. "
        "Consult a qualified clinician for health concerns."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_used": self.query_used,
            "hits": [h.to_dict() for h in self.hits],
            "bpm_min": self.bpm_min,
            "bpm_max": self.bpm_max,
            "enforce_forbid_sharp_transients": self.enforce_forbid_sharp_transients,
            "enforce_forbid_high_freq_peaks": self.enforce_forbid_high_freq_peaks,
            "enforce_forbid_percussive_hits": self.enforce_forbid_percussive_hits,
            "emotional_anchor_suffix": self.emotional_anchor_suffix,
            "safety_notes": self.safety_notes,
            "evidence_summary": self.evidence_summary,
            "disclaimer": self.disclaimer,
        }


def dict_list_to_jsonl(rows: List[Dict[str, Any]]) -> str:
    import json

    return "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else "")


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    import json
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        return []
    out: List[Dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out
