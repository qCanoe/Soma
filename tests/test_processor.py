from datetime import datetime

import pytest

from music_ai_module.config import SystemConfig
from music_ai_module.models import AppleWatchBiometrics, StaticUserProfile
from music_ai_module.processor import BiometricProcessor


def _bio(
    *,
    hr: int = 80,
    hrv: float = 50.0,
    resp: int = 14,
    noise: float = 50.0,
    motion: dict | None = None,
) -> AppleWatchBiometrics:
    return AppleWatchBiometrics(
        timestamp=datetime(2026, 5, 1, 12, 0, 0),
        heart_rate=hr,
        heart_rate_variability=hrv,
        respiratory_rate=resp,
        environmental_audio_exposure=noise,
        body_motion=motion or {"x": 0.01, "y": 0.01, "z": 0.01},
    )


def test_smooth_hr_used_for_target_bpm(profile: StaticUserProfile) -> None:
    cfg = SystemConfig(hr_smoothing_window=3)
    p = BiometricProcessor(cfg)

    p.process(profile, _bio(hr=60))
    p.process(profile, _bio(hr=60))
    out = p.process(profile, _bio(hr=120))

    smoothed = float(out["rhythm"]["smoothed_hr"])
    assert smoothed == pytest.approx((60 + 60 + 120) / 3.0)

    raw_entrain = 120 * (1 - cfg.rhythm_reduction_pct / 100.0)
    assert out["rhythm"]["target_bpm"] != int(round(raw_entrain))

    arousal = float(out["state"]["arousal_score"])
    smooth_entrain = smoothed * (1.0 - cfg.rhythm_reduction_pct / 100.0)
    expected = smooth_entrain - (arousal / 100.0) * cfg.arousal_extra_bpm_reduction_max
    assert abs(float(out["rhythm"]["target_bpm"]) - round(expected)) <= 1.0


def test_clamps_target_bpm_min_max(profile: StaticUserProfile) -> None:
    cfg = SystemConfig(hr_smoothing_window=1, min_bpm=45, max_bpm=140)
    p = BiometricProcessor(cfg)

    out_high = p.process(profile, _bio(hr=195))
    assert out_high["rhythm"]["target_bpm"] == 140

    out_low = p.process(profile, _bio(hr=40))
    assert out_low["rhythm"]["target_bpm"] == 45


def test_lower_hrv_increases_arousal(profile: StaticUserProfile) -> None:
    cfg = SystemConfig(hr_smoothing_window=1)
    calm = BiometricProcessor(cfg).process(profile, _bio(hrv=90.0))
    stressed = BiometricProcessor(cfg).process(profile, _bio(hrv=15.0))
    assert stressed["state"]["arousal_score"] >= calm["state"]["arousal_score"]


def test_avoid_instruments_filters_strategy(profile: StaticUserProfile) -> None:
    cfg = SystemConfig(hr_smoothing_window=1)
    prof = StaticUserProfile(
        occupation=profile.occupation,
        age=profile.age,
        height_cm=profile.height_cm,
        baseline_heart_rate=profile.baseline_heart_rate,
        avoid_instruments=["piano"],
        therapy_goal="calm",
    )
    out = BiometricProcessor(cfg).process(
        prof,
        _bio(hr=75, resp=12),
        validation_errors=[],
    )
    lowered = [x.lower() for x in out["music_strategy"]["instrument_set"]]
    assert all("piano" not in ins for ins in lowered)


def test_exercise_context_scales_hr_load(profile: StaticUserProfile) -> None:
    cfg = SystemConfig(hr_smoothing_window=1, activity_hr_load_scale=0.25)
    p = BiometricProcessor(cfg)
    rest = BiometricProcessor(cfg)
    bio_rest = _bio(hr=120, hrv=40.0, resp=16, noise=45.0, motion={"x": 0.01, "y": 0.01, "z": 0.01})
    bio_move = AppleWatchBiometrics(
        timestamp=bio_rest.timestamp,
        heart_rate=120,
        heart_rate_variability=40.0,
        respiratory_rate=16,
        environmental_audio_exposure=45.0,
        body_motion={"x": 2.0, "y": 0.5, "z": 0.3},
        activity_state="running",
    )
    out_rest = rest.process(profile, bio_rest)
    out_move = p.process(profile, bio_move)
    assert out_move["features"]["exercise_context"] is True
    assert out_move["state"]["arousal_score"] <= out_rest["state"]["arousal_score"]


def test_sensor_confidence_lowers_state_confidence(profile: StaticUserProfile) -> None:
    cfg = SystemConfig(hr_smoothing_window=1)
    b_low = AppleWatchBiometrics(
        timestamp=_bio().timestamp,
        heart_rate=85,
        heart_rate_variability=45.0,
        respiratory_rate=16,
        environmental_audio_exposure=50.0,
        body_motion={"x": 0.02, "y": 0.02, "z": 0.02},
        sensor_confidence=0.45,
    )
    out = BiometricProcessor(cfg).process(profile, b_low)
    assert out["state"]["confidence"] <= 0.55


def test_noise_forbid_hysteresis_requires_two_samples(profile: StaticUserProfile) -> None:
    cfg = SystemConfig(
        hr_smoothing_window=1,
        noise_forbid_enter_db=72.0,
        noise_forbid_exit_db=66.0,
        noise_forbid_enter_consecutive_samples=2,
        noise_forbid_exit_consecutive_samples=2,
    )
    p = BiometricProcessor(cfg)

    first = p.process(profile, _bio(noise=80.0))
    assert first["safeguards"]["forbid_sharp_transients"] is False

    second = p.process(profile, _bio(noise=80.0))
    assert second["safeguards"]["forbid_sharp_transients"] is True
