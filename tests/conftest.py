from datetime import datetime

import pytest

from music_ai_module.models import AppleWatchBiometrics, StaticUserProfile


@pytest.fixture
def profile() -> StaticUserProfile:
    return StaticUserProfile(
        occupation="software_engineer",
        age=28,
        height_cm=180,
        baseline_heart_rate=65,
        chronic_stress_sources=["work_deadline"],
        music_preference="minimalist_ambient",
    )


@pytest.fixture
def biometrics() -> AppleWatchBiometrics:
    return AppleWatchBiometrics(
        timestamp=datetime(2026, 5, 1, 12, 0, 0),
        heart_rate=102,
        heart_rate_variability=35.5,
        respiratory_rate=18,
        environmental_audio_exposure=68.0,
        body_motion={"x": 0.3, "y": 0.25, "z": 0.15},
        blood_oxygen=97.5,
        sleep_stage="awake",
    )
