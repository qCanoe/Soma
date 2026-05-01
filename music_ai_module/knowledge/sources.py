"""Load source registry YAML for ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class SourceRecord:
    id: str
    url: str
    title: str = ""
    license_note: str = ""
    full_text_allowed: bool = True
    topics: List[str] = field(default_factory=list)
    trust_score: float = 0.8

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SourceRecord":
        return cls(
            id=str(d["id"]),
            url=str(d["url"]),
            title=str(d.get("title") or ""),
            license_note=str(d.get("license_note") or ""),
            full_text_allowed=bool(d.get("full_text_allowed", True)),
            topics=list(d.get("topics") or []),
            trust_score=float(d.get("trust_score", 0.8)),
        )


def load_sources(path: str | Path) -> List[SourceRecord]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyYAML is required for sources.yaml — pip install pyyaml") from exc

    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not data or "sources" not in data:
        return []
    return [SourceRecord.from_dict(x) for x in data["sources"]]
