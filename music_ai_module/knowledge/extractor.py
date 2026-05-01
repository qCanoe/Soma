"""LLM-based entity/relation extraction from a single chunk (strict JSON)."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from openai import OpenAI

from ..config import SystemConfig
from .schemas import ExtractionResult, NodeType, RelationType


SYSTEM_PROMPT = """You extract a biomedical + music-intervention knowledge graph from ONE text chunk.
Output ONLY valid JSON with keys: entities, relations.

entities: array of {type, label, aliases?}
  type must be one of: Condition, Symptom, BiometricMarker, MusicIntervention,
  AcousticParameter, SafetyConstraint, EvidenceClaim, Source
relations: array of {subject, predicate, object, quote}
  subject and object must exactly match an entity label (case-sensitive match to label field).
  predicate must be one of: INDICATES, MAY_HELP, HAS_PARAMETER, AVOID_FOR,
  SUPPORTED_BY, CONTRAINDICATED_WITH, RELATED_TO
  quote MUST be a verbatim substring copied from the provided CHUNK_TEXT. If you cannot
  quote verbatim, omit that relation.

Do not diagnose users. Only assert what the text supports."""


def _extract_json_object(raw: str) -> Dict[str, Any]:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}\s*$", raw)
    if m:
        return json.loads(m.group(0))
    raise ValueError("Model did not return JSON object")


def extract_from_chunk(
    config: SystemConfig,
    chunk_id: str,
    chunk_text: str,
) -> ExtractionResult:
    if not config.llm_api_key.strip():
        raise RuntimeError("OPENAI_API_KEY (or llm_api_key) is required for extraction")

    client = OpenAI(api_key=config.llm_api_key, base_url=config.llm_base_url)
    user = f'CHUNK_ID: {chunk_id}\n\nCHUNK_TEXT:\n"""{chunk_text}"""'

    kwargs: Dict[str, Any] = {
        "model": config.llm_model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    try:
        resp = client.chat.completions.create(
            **kwargs,
            response_format={"type": "json_object"},
        )
    except Exception:
        resp = client.chat.completions.create(**kwargs)

    raw = (resp.choices[0].message.content or "").strip()
    data = _extract_json_object(raw)
    entities = list(data.get("entities") or [])
    relations = list(data.get("relations") or [])

    allowed_n = {t.value for t in NodeType}
    allowed_r = {t.value for t in RelationType}
    entities = [
        e
        for e in entities
        if str(e.get("type") or "") in allowed_n and str(e.get("label") or "").strip()
    ]
    relations = [
        r
        for r in relations
        if str(r.get("predicate") or "") in allowed_r
        and str(r.get("subject") or "").strip()
        and str(r.get("object") or "").strip()
    ]

    now = datetime.now(timezone.utc).isoformat()
    return ExtractionResult(
        chunk_id=chunk_id,
        entities=entities,
        relations=relations,
        raw_response=raw,
        model=config.llm_model,
    )


def validate_relations_against_chunk(
    relations: List[Dict[str, Any]],
    chunk_text: str,
) -> List[Dict[str, Any]]:
    """Drop relations whose quote is not in chunk_text."""
    out: List[Dict[str, Any]] = []
    for r in relations:
        q = str(r.get("quote") or "").strip()
        if q and q in chunk_text:
            out.append(r)
    return out
