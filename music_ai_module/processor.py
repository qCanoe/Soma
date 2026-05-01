"""
Layer 2: Middleware Rules Engine

Extracts biometric features, estimates physiological state (continuous arousal
model + temporal hysteresis), and compiles a MusicStrategy for deterministic
Layer-3 prompt rendering.
"""

from __future__ import annotations

from collections import deque
from math import sqrt
from typing import Deque, Dict, List

import numpy as np

from .config import SystemConfig, default_config
from .models import (
    AppleWatchBiometrics,
    BiometricFeatures,
    MusicStrategy,
    PhysiologicalState,
    StaticUserProfile,
    dataclass_to_dict,
)
from .style_maps import DEFAULT_GENRE_PROMPT, OCCUPATION_AESTHETIC_TAGS, OCCUPATION_GENRE_PROMPTS


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _linear_score(value: float, v0: float, v1: float) -> float:
    """Map v0→0, v1→100 with clamp."""
    if v1 <= v0:
        return 0.0
    return _clamp((value - v0) / (v1 - v0) * 100.0, 0.0, 100.0)


class BiometricProcessor:
    """
    Features → PhysiologicalState → MusicStrategy (+ legacy Layer-2 dict keys).
    """

    def __init__(self, config: SystemConfig = default_config) -> None:
        self.config = config
        self._hr_history: List[float] = []
        self._arousal_history: Deque[float] = deque(
            maxlen=max(4, config.temporal_history_maxlen)
        )

        self._strong_masking_latched: bool = False
        self._mask_enter_streak: int = 0
        self._mask_exit_streak: int = 0

        self._noise_forbid_latched: bool = False
        self._noise_enter_streak: int = 0
        self._noise_exit_streak: int = 0

    # ------------------------------------------------------------------
    # Smoothing
    # ------------------------------------------------------------------

    def smooth_heart_rate(self, current_hr: int) -> float:
        """Sliding-window moving average to suppress sensor noise."""
        self._hr_history.append(float(current_hr))
        if len(self._hr_history) > self.config.hr_smoothing_window:
            self._hr_history.pop(0)
        return float(np.mean(self._hr_history))

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _motion_magnitude(self, body_motion: Dict[str, float]) -> float:
        x = float(body_motion.get("x", 0.0))
        y = float(body_motion.get("y", 0.0))
        z = float(body_motion.get("z", 0.0))
        return sqrt(x * x + y * y + z * z)

    def _normalized_arousal_weights(self) -> tuple[float, float, float, float, float]:
        wh = self.config.arousal_weight_hr
        wv = self.config.arousal_weight_hrv
        wr = self.config.arousal_weight_resp
        wn = self.config.arousal_weight_noise
        wm = self.config.arousal_weight_motion
        s = wh + wv + wr + wn + wm
        if s <= 0:
            return (0.2, 0.2, 0.2, 0.2, 0.2)
        return (wh / s, wv / s, wr / s, wn / s, wm / s)

    def _compute_component_scores(
        self,
        smoothed_hr: float,
        baseline_hr: int,
        hrv_ms: float,
        resp_rate: float,
        noise_db: float,
        motion_mag: float,
    ) -> tuple[float, float, float, float, float, float, float, float]:
        safe_base = max(float(baseline_hr), 1.0)
        hr_delta = smoothed_hr - float(baseline_hr)
        hr_delta_pct = 100.0 * hr_delta / safe_base

        hr_load = _linear_score(hr_delta, 0.0, self.config.hr_load_ref_delta_bpm)

        # Lower HRV ⇒ higher risk (smooth ramp between low HRV and calm reference)
        hrv_risk = 100.0 - _linear_score(
            hrv_ms,
            max(5.0, self.config.hrv_safety_threshold * 0.35),
            max(self.config.hrv_calm_ref_ms, self.config.hrv_safety_threshold + 5.0),
        )

        resp_load = _linear_score(
            resp_rate,
            self.config.resp_calm_br_min,
            max(
                self.config.resp_stress_br_min,
                self.config.respiratory_elevated_threshold + 2.0,
            ),
        )

        noise_risk = _linear_score(
            noise_db,
            self.config.noise_calm_db,
            max(self.config.noise_stress_db, self.config.max_noise_db + 10.0),
        )

        motion_score = _linear_score(
            motion_mag,
            self.config.motion_calm_g,
            max(self.config.motion_stress_g, self.config.motion_calm_g + 0.05),
        )

        wh, wv, wr, wn, wm = self._normalized_arousal_weights()
        arousal = _clamp(
            wh * hr_load
            + wv * hrv_risk
            + wr * resp_load
            + wn * noise_risk
            + wm * motion_score,
            0.0,
            100.0,
        )

        return (
            hr_delta,
            hr_delta_pct,
            hr_load,
            hrv_risk,
            resp_load,
            noise_risk,
            motion_score,
            arousal,
        )

    # ------------------------------------------------------------------
    # Temporal & hysteresis
    # ------------------------------------------------------------------

    def _update_arousal_trend(self, arousal: float) -> str:
        self._arousal_history.append(arousal)
        if len(self._arousal_history) < 4:
            return "stable"
        hist = list(self._arousal_history)
        older = float(np.mean(hist[-4:-2]))
        recent = float(np.mean(hist[-2:]))
        if recent < older - 3.0:
            return "improving"
        if recent > older + 3.0:
            return "worsening"
        return "stable"

    def _update_masking_latch(self, arousal: float) -> None:
        if arousal >= self.config.masking_enter_arousal:
            self._mask_enter_streak += 1
            self._mask_exit_streak = 0
        elif arousal <= self.config.masking_exit_arousal:
            self._mask_exit_streak += 1
            self._mask_enter_streak = 0
        else:
            self._mask_enter_streak = 0
            self._mask_exit_streak = 0

        if (
            not self._strong_masking_latched
            and self._mask_enter_streak >= self.config.masking_enter_consecutive_samples
        ):
            self._strong_masking_latched = True
        if (
            self._strong_masking_latched
            and self._mask_exit_streak >= self.config.masking_exit_consecutive_samples
        ):
            self._strong_masking_latched = False

    def _update_noise_forbid_latch(self, noise_db: float) -> None:
        if noise_db >= self.config.noise_forbid_enter_db:
            self._noise_enter_streak += 1
            self._noise_exit_streak = 0
        elif noise_db <= self.config.noise_forbid_exit_db:
            self._noise_exit_streak += 1
            self._noise_enter_streak = 0
        else:
            self._noise_enter_streak = 0
            self._noise_exit_streak = 0

        if (
            not self._noise_forbid_latched
            and self._noise_enter_streak
            >= self.config.noise_forbid_enter_consecutive_samples
        ):
            self._noise_forbid_latched = True
        if (
            self._noise_forbid_latched
            and self._noise_exit_streak
            >= self.config.noise_forbid_exit_consecutive_samples
        ):
            self._noise_forbid_latched = False

    # ------------------------------------------------------------------
    # Strategy helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _stress_band(arousal: float, cfg: SystemConfig) -> str:
        if arousal <= cfg.arousal_low_max:
            return "low"
        if arousal <= cfg.arousal_moderate_max:
            return "moderate"
        return "high"

    def _recovery_priority(
        self, profile: StaticUserProfile, arousal: float, stress_state: str
    ) -> str:
        if arousal >= self.config.arousal_moderate_max:
            return "grounding"
        tg = profile.therapy_goal.lower().strip()
        if tg == "sleep":
            return "sleep"
        if tg == "grounding":
            return "grounding"
        if tg == "focus" and stress_state == "low":
            return "focus"
        return "calm"

    def _confidence(self, validation_errors: List[str]) -> float:
        base = 1.0 - 0.06 * len(validation_errors)
        return float(_clamp(base, 0.5, 1.0))

    def _resolve_genre_style(self, profile: StaticUserProfile) -> str:
        base = OCCUPATION_GENRE_PROMPTS.get(profile.occupation, DEFAULT_GENRE_PROMPT)
        pref = profile.music_preference.lower()
        extras: List[str] = []

        if "minimalist" in pref:
            extras.append(
                "ultra-minimal arrangement, generous negative space, low melodic density"
            )
        elif "ambient" in pref:
            extras.append("warm ambient harmonic bed with slow-evolving textures")

        if "electronic" in pref:
            extras.append(
                "soft electronic timbres and sine-like tones without percussive attacks"
            )
        if "classical" in pref or "acoustic" in pref:
            extras.append("organic acoustic instruments with natural decay tails")

        sens = profile.sound_sensitivity.lower()
        if sens == "high":
            extras.append(
                "gentle dynamics and conservative loudness peaks for sound-sensitive listeners"
            )
        elif sens == "low":
            extras.append("slightly fuller harmonic presence while avoiding startling transients")

        dens = profile.preferred_density.lower()
        if dens == "low":
            extras.append("very sparse layering and breathable sonic gaps")
        elif dens == "high":
            extras.append(
                "richer layered pads without rhythmic punctuation or sharp impacts"
            )

        if extras:
            return base + "; " + "; ".join(extras)
        return base

    def _select_instruments(self, resp_load_score: float, avoid: List[str]) -> List[str]:
        if resp_load_score >= 58.0:
            chosen = ["cello_legato", "sustained_synth"]
        elif resp_load_score >= 32.0:
            chosen = ["piano", "ambient_strings", "soft_synth_pad"]
        else:
            chosen = ["piano", "ambient_strings"]

        if not avoid:
            return chosen

        avoid_l = [a.strip().lower() for a in avoid if a.strip()]
        filtered: List[str] = []
        for ins in chosen:
            il = ins.lower()
            if any(a in il or il in a for a in avoid_l):
                continue
            filtered.append(ins)

        return filtered if filtered else ["soft_synth_pad"]

    def _build_texture_description(self, masking_strength: float) -> tuple[str, Dict]:
        """Returns acoustic_texture inner text + legacy texture dict."""
        pink = masking_strength >= 0.38
        pad = masking_strength >= 0.28

        if pink and pad:
            inner = (
                "pink noise broadband masking foundation "
                "(1/f spectrum for threat isolation); "
                "continuous synthesizer pad (seamless harmonic grounding)"
            )
        elif pad:
            inner = (
                "continuous synthesizer pad (gentle grounding) "
                "with clean instrumental focal layers"
            )
        elif pink:
            inner = "subtle pink-noise undertone for auditory threat buffering"
        else:
            inner = "clean, unadorned instruments with natural resonance"

        legacy = {
            "hrv_status": "stressed_rigid" if masking_strength >= 0.45 else "flexible_resilient",
            "apply_pink_noise": pink,
            "apply_pad_texture": pad,
            "pad_type": "continuous_synthesizer" if pad else None,
            "hrv_score": 0.0,  # filled by caller
            "masking_strength": masking_strength,
        }
        return inner, legacy

    def _build_emotional_anchor(
        self,
        sympathetic_load_bpm: float,
        profile: StaticUserProfile,
        recovery_priority: str,
    ) -> str:
        mod = self.config.sympathetic_load_moderate_bpm
        high = self.config.sympathetic_load_high_bpm

        if sympathetic_load_bpm >= high:
            text = (
                "Deep nervous system grounding, immediate safety establishment, "
                "vagal tone rebalancing, parasympathetic activation cues, "
                "trauma-informed gentle progression"
            )
        elif sympathetic_load_bpm >= mod:
            text = (
                "Calm supportive presence, gentle deactivation of arousal, "
                "spacious harmonic movement allowing breath recovery"
            )
        else:
            text = (
                "Supportive focus state, minimal emotional narrative, "
                "transparent presence supporting user's agency"
            )

        rp = recovery_priority.lower()
        if rp == "sleep":
            text += "; oriented toward sleep onset with ultra-slow harmonic motion"
        elif rp == "focus":
            text += "; oriented toward sustained attention without overstimulation"

        if profile.chronic_stress_sources:
            src = ", ".join(profile.chronic_stress_sources[:4])
            text += f". Context-aware framing for chronic stress themes: {src}."

        return text

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        profile: StaticUserProfile,
        biometrics: AppleWatchBiometrics,
        validation_errors: List[str] | None = None,
    ) -> Dict:
        """
        Returns Layer-2 bundle including legacy keys, features, state, music_strategy.
        """
        val_errs = validation_errors or []

        smoothed_hr = self.smooth_heart_rate(biometrics.heart_rate)
        motion_mag = self._motion_magnitude(biometrics.body_motion)

        (
            hr_delta,
            hr_delta_pct,
            hr_load,
            hrv_risk,
            resp_load,
            noise_risk,
            motion_score,
            arousal_raw,
        ) = self._compute_component_scores(
            smoothed_hr=smoothed_hr,
            baseline_hr=profile.baseline_heart_rate,
            hrv_ms=biometrics.heart_rate_variability,
            resp_rate=float(biometrics.respiratory_rate),
            noise_db=biometrics.environmental_audio_exposure,
            motion_mag=motion_mag,
        )

        features = BiometricFeatures(
            raw_hr=biometrics.heart_rate,
            smoothed_hr=smoothed_hr,
            baseline_hr=profile.baseline_heart_rate,
            hr_delta_bpm=hr_delta,
            hr_delta_pct=hr_delta_pct,
            hrv_ms=biometrics.heart_rate_variability,
            respiratory_rate=float(biometrics.respiratory_rate),
            ambient_noise_db=biometrics.environmental_audio_exposure,
            motion_magnitude_g=motion_mag,
            hr_load_score=hr_load,
            hrv_risk_score=hrv_risk,
            respiratory_load_score=resp_load,
            noise_risk_score=noise_risk,
            motion_intensity_score=motion_score,
        )

        trend = self._update_arousal_trend(arousal_raw)
        self._update_masking_latch(arousal_raw)
        self._update_noise_forbid_latch(biometrics.environmental_audio_exposure)

        stress_state = self._stress_band(arousal_raw, self.config)
        recovery_pri = self._recovery_priority(profile, arousal_raw, stress_state)
        sympathetic_load_bpm = smoothed_hr - float(profile.baseline_heart_rate)

        state = PhysiologicalState(
            arousal_score=arousal_raw,
            stress_state=stress_state,
            recovery_priority=recovery_pri,
            confidence=self._confidence(val_errs),
            trend=trend,
            sympathetic_load_bpm=sympathetic_load_bpm,
        )

        # Continuous masking strength + hysteresis latch boost
        texture_need = _clamp(
            0.55 * (features.hrv_risk_score / 100.0)
            + 0.45 * (arousal_raw / 100.0),
            0.0,
            1.0,
        )
        if self._strong_masking_latched:
            texture_need = max(texture_need, 0.68)

        acoustic_inner, texture_legacy = self._build_texture_description(texture_need)
        texture_legacy["hrv_score"] = features.hrv_ms

        base_raw_bpm = smoothed_hr * (1.0 - self.config.rhythm_reduction_pct / 100.0)
        extra_drop = (arousal_raw / 100.0) * self.config.arousal_extra_bpm_reduction_max
        target_bpm = int(round(base_raw_bpm - extra_drop))
        target_bpm = int(
            _clamp(
                float(target_bpm),
                float(self.config.min_bpm),
                float(self.config.max_bpm),
            )
        )

        instruments = self._select_instruments(
            features.respiratory_load_score,
            profile.avoid_instruments,
        )

        genre_style = self._resolve_genre_style(profile)

        emotional = self._build_emotional_anchor(
            sympathetic_load_bpm=sympathetic_load_bpm,
            profile=profile,
            recovery_priority=recovery_pri,
        )

        forbid_noise = self._noise_forbid_latched

        strategy = MusicStrategy(
            tempo_bpm=target_bpm,
            genre_style=genre_style,
            instrument_set=instruments,
            acoustic_texture_description=acoustic_inner,
            emotional_anchor_description=emotional,
            forbid_sharp_transients=forbid_noise,
            forbid_high_freq_peaks=forbid_noise,
            forbid_percussive_hits=forbid_noise,
        )

        rhythm_params = {
            "target_bpm": target_bpm,
            "current_hr": biometrics.heart_rate,
            "smoothed_hr": smoothed_hr,
            "baseline_hr": profile.baseline_heart_rate,
            "sympathetic_load": int(round(sympathetic_load_bpm)),
        }

        resp_score = features.respiratory_load_score
        if resp_score >= 58.0:
            resp_label = "elevated_anxious"
            legato = True
        elif resp_score >= 32.0:
            resp_label = "elevated_moderate"
            legato = False
        else:
            resp_label = "normal_calm"
            legato = False

        breathing_params = {
            "respiratory_status": resp_label,
            "trigger_legato": legato,
            "instrument_set": instruments,
            "resp_rate": biometrics.respiratory_rate,
        }

        safeguards_params = {
            "noise_environment": "harsh_noisy" if forbid_noise else "quiet_safe",
            "forbid_sharp_transients": forbid_noise,
            "forbid_high_freq_peaks": forbid_noise,
            "forbid_percussive_hits": forbid_noise,
            "ambient_db": biometrics.environmental_audio_exposure,
        }

        aesthetic_style = OCCUPATION_AESTHETIC_TAGS.get(profile.occupation, "ambient")

        return {
            "rhythm": rhythm_params,
            "texture": texture_legacy,
            "breathing": breathing_params,
            "safeguards": safeguards_params,
            "aesthetic_style": aesthetic_style,
            "timestamp": biometrics.timestamp.isoformat(),
            "features": dataclass_to_dict(features),
            "state": dataclass_to_dict(state),
            "music_strategy": dataclass_to_dict(strategy),
        }
