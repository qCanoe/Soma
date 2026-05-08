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
from .personalization import PersonalizationHints, resolve_personalization_strategy
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
        self._hrv_history: List[float] = []
        self._resp_history: List[float] = []
        self._noise_history: List[float] = []
        self._motion_history: List[float] = []
        self._arousal_history: Deque[float] = deque(
            maxlen=max(4, config.temporal_history_maxlen)
        )

        self._prev_smoothed_hr: float | None = None
        self._latched_stress_band: str | None = None
        self._stress_up_streak: int = 0
        self._stress_down_streak: int = 0

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

    def _smooth_series(self, buf: List[float], value: float) -> float:
        buf.append(float(value))
        w = max(1, self.config.hr_smoothing_window)
        if len(buf) > w:
            buf.pop(0)
        return float(np.mean(buf))

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
        hr_load_scale: float = 1.0,
    ) -> tuple[float, float, float, float, float, float, float, float]:
        safe_base = max(float(baseline_hr), 1.0)
        hr_delta = smoothed_hr - float(baseline_hr)
        hr_delta_pct = 100.0 * hr_delta / safe_base

        hr_load = _linear_score(hr_delta, 0.0, self.config.hr_load_ref_delta_bpm)
        hr_load = _clamp(hr_load * hr_load_scale, 0.0, 100.0)

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

    def _update_arousal_trend(self, arousal: float, sensor_q: float) -> str:
        self._arousal_history.append(arousal)
        if sensor_q < 0.55:
            return "low_confidence"
        hist = list(self._arousal_history)
        if len(hist) >= 4:
            tail = hist[-6:]
            if float(np.std(tail)) >= self.config.arousal_unstable_stdev_threshold:
                return "unstable"
        if len(self._arousal_history) < 4:
            return "stable"
        hlist = list(self._arousal_history)
        older = float(np.mean(hlist[-4:-2]))
        recent = float(np.mean(hlist[-2:]))
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

    def _exercise_context(
        self, bio: AppleWatchBiometrics, motion_smoothed: float
    ) -> bool:
        act = (bio.activity_state or "").lower().strip()
        if act in (
            "walking",
            "running",
            "exercise",
            "workout",
            "active",
            "cycling",
            "training",
        ):
            return True
        if bio.resting_context is True:
            return False
        if motion_smoothed >= self.config.motion_exercise_hint_g:
            return True
        return False

    def _sensor_quality_score(
        self,
        bio: AppleWatchBiometrics,
        validation_errors: List[str],
        smoothed_hr: float,
    ) -> float:
        q = 1.0 - 0.12 * len(validation_errors)
        if bio.sensor_confidence is not None:
            try:
                sc = float(bio.sensor_confidence)
                q = min(q, max(0.0, min(1.0, sc)))
            except (TypeError, ValueError):
                pass
        if self._prev_smoothed_hr is not None and self._prev_smoothed_hr > 0:
            if abs(smoothed_hr - self._prev_smoothed_hr) > 25.0:
                q *= 0.78
        return float(_clamp(q, 0.35, 1.0))

    def _stress_band_ord(self, band: str) -> int:
        return {"low": 0, "moderate": 1, "high": 2}.get(band, 1)

    def _update_stress_band_latched(self, raw_band: str) -> str:
        if self._latched_stress_band is None:
            self._latched_stress_band = raw_band
            self._stress_up_streak = 0
            self._stress_down_streak = 0
            return raw_band
        ro = self._stress_band_ord(raw_band)
        lo = self._stress_band_ord(self._latched_stress_band)
        if ro > lo:
            self._stress_down_streak = 0
            self._stress_up_streak += 1
            if self._stress_up_streak >= self.config.stress_band_enter_consecutive:
                self._latched_stress_band = raw_band
                self._stress_up_streak = 0
        elif ro < lo:
            self._stress_up_streak = 0
            self._stress_down_streak += 1
            if self._stress_down_streak >= self.config.stress_band_exit_consecutive:
                self._latched_stress_band = raw_band
                self._stress_down_streak = 0
        else:
            self._stress_up_streak = 0
            self._stress_down_streak = 0
        assert self._latched_stress_band is not None
        return self._latched_stress_band

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

    def _confidence(self, validation_errors: List[str], sensor_q: float) -> float:
        base = 1.0 - 0.06 * len(validation_errors)
        base = min(base, sensor_q)
        return float(_clamp(base, 0.45, 1.0))

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

    def _select_instruments(
        self,
        resp_load_score: float,
        avoid: List[str],
        *,
        cap: int | None = None,
        rhythm_preference_low: bool = False,
    ) -> List[str]:
        if rhythm_preference_low and resp_load_score < 40.0:
            chosen = ["soft_synth_pad", "ambient_strings"]
        elif resp_load_score >= 58.0:
            chosen = ["cello_legato", "sustained_synth"]
        elif resp_load_score >= 32.0:
            chosen = ["piano", "ambient_strings", "soft_synth_pad"]
        else:
            chosen = ["piano", "ambient_strings"]

        if cap is not None and cap > 0:
            chosen = chosen[:cap]

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

    def _apply_personalization_hints(
        self,
        strategy: MusicStrategy,
        hints: PersonalizationHints,
        profile: StaticUserProfile,
        resp_load: float,
    ) -> MusicStrategy:
        ms = MusicStrategy(**dataclass_to_dict(strategy))
        ms.tempo_bpm = int(
            round(
                _clamp(
                    float(ms.tempo_bpm + hints.tempo_offset_bpm),
                    float(self.config.min_bpm),
                    float(self.config.max_bpm),
                )
            )
        )
        if hints.forbid_sharp_extra:
            ms.forbid_sharp_transients = True
        if hints.forbid_high_freq_extra:
            ms.forbid_high_freq_peaks = True
        if hints.forbid_perc_extra:
            ms.forbid_percussive_hits = True
        avoid_extended = list(profile.avoid_instruments)
        for t in hints.avoid_material_tokens:
            t2 = str(t).strip()
            if t2:
                avoid_extended.append(t2)
        low_rhythm = hints.rhythm_drive_scale < 0.88
        ms.instrument_set = self._select_instruments(
            resp_load,
            avoid_extended,
            cap=hints.instrument_cap,
            rhythm_preference_low=low_rhythm,
        )
        if hints.genre_extras:
            ms.genre_style = ms.genre_style + "; " + "; ".join(hints.genre_extras[:6])
        if hints.texture_soften:
            ms.acoustic_texture_description = (
                "softened spectral balance; " + ms.acoustic_texture_description
            )
        return ms

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
        hints = resolve_personalization_strategy(profile)

        smoothed_hr = self.smooth_heart_rate(biometrics.heart_rate)
        smoothed_hrv = self._smooth_series(
            self._hrv_history, float(biometrics.heart_rate_variability)
        )
        smoothed_resp = self._smooth_series(
            self._resp_history, float(biometrics.respiratory_rate)
        )
        smoothed_noise = self._smooth_series(
            self._noise_history, float(biometrics.environmental_audio_exposure)
        )
        motion_mag_raw = self._motion_magnitude(biometrics.body_motion)
        smoothed_motion = self._smooth_series(self._motion_history, motion_mag_raw)

        exercise_ctx = self._exercise_context(biometrics, smoothed_motion)
        hr_scale = (
            self.config.activity_hr_load_scale if exercise_ctx else 1.0
        )

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
            hrv_ms=smoothed_hrv,
            resp_rate=smoothed_resp,
            noise_db=smoothed_noise,
            motion_mag=smoothed_motion,
            hr_load_scale=hr_scale,
        )

        sensor_q = self._sensor_quality_score(
            biometrics, val_errs, smoothed_hr
        )
        arousal_adj = arousal_raw * (0.55 + 0.45 * sensor_q)

        features = BiometricFeatures(
            raw_hr=biometrics.heart_rate,
            smoothed_hr=smoothed_hr,
            baseline_hr=profile.baseline_heart_rate,
            hr_delta_bpm=hr_delta,
            hr_delta_pct=hr_delta_pct,
            hrv_ms=smoothed_hrv,
            respiratory_rate=smoothed_resp,
            ambient_noise_db=smoothed_noise,
            motion_magnitude_g=smoothed_motion,
            hr_load_score=hr_load,
            hrv_risk_score=hrv_risk,
            respiratory_load_score=resp_load,
            noise_risk_score=noise_risk,
            motion_intensity_score=motion_score,
            smoothed_hrv_ms=smoothed_hrv,
            smoothed_respiratory_rate=smoothed_resp,
            smoothed_ambient_noise_db=smoothed_noise,
            smoothed_motion_magnitude_g=smoothed_motion,
            sensor_quality_score=sensor_q,
            exercise_context=exercise_ctx,
        )

        trend = self._update_arousal_trend(arousal_adj, sensor_q)
        self._update_masking_latch(arousal_adj)
        self._update_noise_forbid_latch(smoothed_noise)

        stress_raw = self._stress_band(arousal_adj, self.config)
        stress_state = self._update_stress_band_latched(stress_raw)
        recovery_pri = self._recovery_priority(
            profile, arousal_adj, stress_state
        )
        sympathetic_load_bpm = smoothed_hr - float(profile.baseline_heart_rate)

        state = PhysiologicalState(
            arousal_score=arousal_adj,
            stress_state=stress_state,
            recovery_priority=recovery_pri,
            confidence=self._confidence(val_errs, sensor_q),
            trend=trend,
            sympathetic_load_bpm=sympathetic_load_bpm,
        )

        texture_need = _clamp(
            0.55 * (features.hrv_risk_score / 100.0)
            + 0.45 * (arousal_adj / 100.0),
            0.0,
            1.0,
        )
        texture_need *= _clamp(0.82 + 0.18 * float(hints.density_scale), 0.65, 1.15)
        texture_need = _clamp(texture_need, 0.0, 1.0)
        if self._strong_masking_latched:
            texture_need = max(texture_need, 0.68)

        acoustic_inner, texture_legacy = self._build_texture_description(texture_need)
        texture_legacy["hrv_score"] = features.hrv_ms

        base_raw_bpm = smoothed_hr * (1.0 - self.config.rhythm_reduction_pct / 100.0)
        extra_drop = (arousal_adj / 100.0) * self.config.arousal_extra_bpm_reduction_max
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

        strategy = self._apply_personalization_hints(
            strategy, hints, profile, features.respiratory_load_score
        )

        downweighted: List[str] = []
        if exercise_ctx:
            downweighted.append("hr_load_scaled_for_activity")
        if sensor_q < 0.85:
            downweighted.append("arousal_damped_by_sensor_quality")
        phys_notes: List[str] = []
        if exercise_ctx:
            phys_notes.append("Elevated motion or activity context — HR load down-weighted.")
        if sensor_q < 0.7:
            phys_notes.append("Sensor quality marginal — interpret arousal cautiously.")
        if trend == "unstable":
            phys_notes.append("Arousal fluctuating recently — prefer gentle, stable textures.")

        explanation = {
            "personalization_applied": hints.explain_applied(),
            "physiology_notes": phys_notes,
            "downweighted_signals": downweighted,
            "stress_band_raw": stress_raw,
            "sensor_quality_score": sensor_q,
            "exercise_context": exercise_ctx,
        }

        self._prev_smoothed_hr = smoothed_hr

        rhythm_params = {
            "target_bpm": strategy.tempo_bpm,
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
            "instrument_set": strategy.instrument_set,
            "resp_rate": biometrics.respiratory_rate,
        }

        safeguards_params = {
            "noise_environment": "harsh_noisy" if forbid_noise else "quiet_safe",
            "forbid_sharp_transients": strategy.forbid_sharp_transients,
            "forbid_high_freq_peaks": strategy.forbid_high_freq_peaks,
            "forbid_percussive_hits": strategy.forbid_percussive_hits,
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
            "strategy_explanation": explanation,
        }
