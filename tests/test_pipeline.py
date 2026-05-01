from datetime import datetime

import warnings

import pytest

from music_ai_module.models import AppleWatchBiometrics, StaticUserProfile
from music_ai_module.pipeline import MusicAIPipeline


def test_strict_validation_raises(profile: StaticUserProfile) -> None:
    bad = AppleWatchBiometrics(
        timestamp=datetime(2026, 5, 1, 12, 0, 0),
        heart_rate=10,
        heart_rate_variability=35.5,
        respiratory_rate=18,
        environmental_audio_exposure=68.0,
        body_motion={"x": 0.0, "y": 0.0, "z": 0.0},
    )

    pipe = MusicAIPipeline()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with pytest.raises(ValueError):
            pipe.run(profile, bad, strict_validation=True)


def test_run_returns_strategy_bundle(profile: StaticUserProfile, biometrics: AppleWatchBiometrics) -> None:
    result = MusicAIPipeline().run(profile, biometrics)
    assert "music_strategy" in result["processed_params"]
    assert "features" in result["processed_params"]
    assert "state" in result["processed_params"]
    assert isinstance(result["prompt"], str)
    assert len(result["prompt"]) > 40


def test_pipeline_with_knowledge_graph(
    profile: StaticUserProfile, biometrics: AppleWatchBiometrics
) -> None:
    result = MusicAIPipeline().run(
        profile,
        biometrics,
        use_knowledge_graph=True,
        user_intent="work anxiety relief",
    )
    assert isinstance(result["prompt"], str)
    assert len(result["prompt"]) > 40
    ca = result["metadata"].get("clinical_audit")
    assert isinstance(ca, dict)
    assert "query_used" in ca
