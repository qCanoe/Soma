"""
Layer 1: Multi-Modal Data Input Models

Defines the data structures for static user profiles, real-time
Apple Watch biometric readings, extracted features, inferred physiological
state, and compiled music strategy for deterministic prompt rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Validation bounds (physiologically plausible ranges)
# ---------------------------------------------------------------------------

VALID_RANGES = {
    "heart_rate": (30, 200),  # BPM
    "heart_rate_variability": (5, 250),  # ms (SDNN)
    "respiratory_rate": (8, 30),  # breaths/min
    "wrist_temperature": (35, 42),  # °C
    "blood_oxygen": (85, 100),  # SpO2 %
    "environmental_audio": (20, 130),  # dB
}


@dataclass
class StaticUserProfile:
    """
    User static characteristics — captured at onboarding, updated quarterly.

    occupation / baseline_heart_rate drive personalization.
    therapy_goal steers recovery_priority when not overridden by high arousal.
    """

    occupation: str
    age: int
    height_cm: float
    baseline_heart_rate: int
    chronic_stress_sources: List[str] = field(default_factory=list)
    music_preference: str = "ambient"
    # Personalization (optional; safe defaults preserve backward compatibility)
    sound_sensitivity: str = "normal"  # low | normal | high
    preferred_density: str = "medium"  # low | medium | high
    avoid_instruments: List[str] = field(default_factory=list)
    therapy_goal: str = "calm"  # focus | calm | sleep | grounding


@dataclass
class AppleWatchBiometrics:
    """
    Real-time biometric snapshot from Apple Watch.
    """

    timestamp: datetime
    heart_rate: int
    heart_rate_variability: float
    respiratory_rate: int
    environmental_audio_exposure: float
    body_motion: Dict[str, float]
    wrist_temperature: Optional[float] = None
    blood_oxygen: Optional[float] = None
    sleep_stage: Optional[str] = None

    def validate(self) -> List[str]:
        errors: List[str] = []

        checks = [
            ("heart_rate", self.heart_rate),
            ("heart_rate_variability", self.heart_rate_variability),
            ("respiratory_rate", self.respiratory_rate),
            ("environmental_audio", self.environmental_audio_exposure),
        ]

        if self.wrist_temperature is not None:
            checks.append(("wrist_temperature", self.wrist_temperature))
        if self.blood_oxygen is not None:
            checks.append(("blood_oxygen", self.blood_oxygen))

        for field_name, value in checks:
            lo, hi = VALID_RANGES[field_name]
            if not (lo <= value <= hi):
                errors.append(
                    f"{field_name} value {value} is outside valid range [{lo}, {hi}]"
                )

        return errors


@dataclass
class BiometricFeatures:
    """Normalized measurements and component stress scores (0–100 each)."""

    raw_hr: int
    smoothed_hr: float
    baseline_hr: int
    hr_delta_bpm: float
    hr_delta_pct: float
    hrv_ms: float
    respiratory_rate: float
    ambient_noise_db: float
    motion_magnitude_g: float

    hr_load_score: float
    hrv_risk_score: float
    respiratory_load_score: float
    noise_risk_score: float
    motion_intensity_score: float


@dataclass
class PhysiologicalState:
    """Fused interpretation used for strategy and UX."""

    arousal_score: float
    stress_state: str  # low | moderate | high
    recovery_priority: str  # focus | calm | sleep | grounding
    confidence: float
    trend: str  # improving | stable | worsening
    sympathetic_load_bpm: float


@dataclass
class MusicStrategy:
    """
    Layer 3 input: deterministic rendering only — no physiologic inference here.
    """

    tempo_bpm: int
    genre_style: str
    instrument_set: List[str]
    acoustic_texture_description: str
    emotional_anchor_description: str
    forbid_sharp_transients: bool
    forbid_high_freq_peaks: bool
    forbid_percussive_hits: bool


def dataclass_to_dict(obj: Any) -> Dict[str, Any]:
    """JSON-friendly dict for nested dataclasses."""
    return asdict(obj)
