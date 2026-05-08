"""Tests for the mock HealthKit → pipeline prototype endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app(serve_web=False)
    return TestClient(app)


def test_healthkit_mock_run_returns_prompt_and_strategy(client: TestClient) -> None:
    body = {
        "vitals": {
            "heartRate": 85,
            "hrv": 38.0,
            "respiratoryRate": 18,
            "ambientNoise": 62.0,
            "bodyMotion": {"x": 0.28, "y": 0.22, "z": 0.14},
            "bloodOxygen": 97.5,
            "wristTemperature": 36.6,
            "sleepStage": "awake",
            "stressScore": 8,
            "baselineHR": 65,
        },
        "profile": {"therapy_goal": "calm"},
        "timestamp": "2026-05-07T14:00:00",
    }
    r = client.post("/api/healthkit/mock/run", json=body)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["prompt"], str)
    assert len(data["prompt"]) > 40
    assert "music_strategy" in data["processed_params"]
    assert "features" in data["processed_params"]
    assert "state" in data["processed_params"]


def test_healthkit_mock_run_defaults_profile_from_baseline_hr(client: TestClient) -> None:
    body = {
        "vitals": {
            "heartRate": 90,
            "hrv": 45.0,
            "respiratoryRate": 16,
            "ambientNoise": 50.0,
            "bodyMotion": {"x": 0.1, "y": 0.1, "z": 0.05},
            "baselineHR": 70,
        },
    }
    r = client.post("/api/healthkit/mock/run", json=body)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["prompt"], str)
    assert len(data["prompt"]) > 10


def test_healthkit_mock_accepts_session_feedback_summary(client: TestClient) -> None:
    body = {
        "vitals": {
            "heartRate": 85,
            "hrv": 38.0,
            "respiratoryRate": 18,
            "ambientNoise": 55.0,
            "bodyMotion": {"x": 0.1, "y": 0.1, "z": 0.05},
            "baselineHR": 65,
        },
        "profile": {
            "therapy_goal": "calm",
            "session_feedback_summary": {"sound_fit": "too_fast"},
        },
    }
    r = client.post("/api/healthkit/mock/run", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["metadata"].get("strategy_explanation")
    se = data["metadata"]["strategy_explanation"]
    assert isinstance(se, dict)
    assert "personalization_applied" in se


def test_healthkit_mock_run_requires_vitals(client: TestClient) -> None:
    r = client.post("/api/healthkit/mock/run", json={})
    assert r.status_code == 422
