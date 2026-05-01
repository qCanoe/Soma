"""Resolve knowledge data directory relative to repository root."""

from __future__ import annotations

from pathlib import Path

from ..config import SystemConfig


def package_parent() -> Path:
    """Repository root (MindWave/) — parent of music_ai_module package."""
    return Path(__file__).resolve().parent.parent.parent


def resolved_knowledge_dir(config: SystemConfig) -> Path:
    raw = (config.knowledge_data_dir or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (package_parent() / "data" / "knowledge").resolve()
