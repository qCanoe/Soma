import json

from music_ai_module.knowledge.extractor import _extract_json_object


def test_extract_json_object_trailing_noise() -> None:
    raw = 'Sure\n{"entities": [], "relations": []}\n'
    data = _extract_json_object(raw)
    assert data["entities"] == []
    assert data["relations"] == []


def test_extract_json_object_raw() -> None:
    payload = {"entities": [{"type": "Condition", "label": "Anxiety"}], "relations": []}
    data = _extract_json_object(json.dumps(payload))
    assert data["entities"][0]["label"] == "Anxiety"
