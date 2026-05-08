"""
System Configuration

Single source of truth for all tunable parameters.
Override defaults by setting environment variables before importing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class SystemConfig:
    """
    Central configuration for the biometric-to-music pipeline.

    All values can be overridden via environment variables at import time.

    LLM / API
    ---------
    llm_api_key   : API key for the LLM verification endpoint.
    llm_base_url  : Base URL for the OpenAI-compatible LLM endpoint.
    llm_model     : Model name used for optional prompt verification.
    suno_api_key  : API key for Suno music generation (optional — Layer 4).

    Music Generation
    ----------------
    min_bpm               : Hard floor for generated music tempo.
    max_bpm               : Hard ceiling for generated music tempo.
    rhythm_reduction_pct  : Percentage by which smoothed HR is reduced to derive
                            the base entrainment BPM (default 15 %).
    arousal_extra_bpm_reduction_max : Additional BPM reduction when arousal is high (0–100).

    Physiological Thresholds
    ------------------------
    hrv_safety_threshold  : HRV (ms) reference for elevated masking risk scoring.
    max_noise_db          : Ambient noise (dB) reference for noise risk scoring.
    respiratory_elevated_threshold : Breaths/min above which respiratory load rises.

    Arousal model (continuous scores 0–100 each, combined with weights below)
    ------------------------------------------------------------------------
    arousal_weight_hr     : Weight for HR delta load score.
    arousal_weight_hrv    : Weight for HRV risk score.
    arousal_weight_resp   : Weight for respiratory load score.
    arousal_weight_noise  : Weight for ambient noise risk score.
    arousal_weight_motion : Weight for motion intensity score.

    Stress bands (arousal_score on 0–100 scale)
    -------------------------------------------
    arousal_low_max       : Upper bound of low stress band (exclusive).
    arousal_moderate_max  : Upper bound of moderate band (exclusive).

    Masking hysteresis (reduces flip-flop near thresholds)
    ------------------------------------------------------
    masking_enter_arousal : Arousal level (0–100) to count toward activating strong masking.
    masking_exit_arousal  : Arousal level below which we count toward releasing masking.
    masking_enter_consecutive_samples : Consecutive samples at/above enter threshold.
    masking_exit_consecutive_samples  : Consecutive samples below exit threshold to release.

    Noise safeguards hysteresis (boolean constraints)
    -------------------------------------------------
    noise_forbid_enter_db : Ambient dB at/above which we count toward harsh safeguards.
    noise_forbid_exit_db  : dB below which we count toward releasing safeguards.
    noise_forbid_enter_consecutive_samples : Samples needed to enable safeguards.
    noise_forbid_exit_consecutive_samples  : Samples needed to disable safeguards.

    Sympathetic load → emotional strategy bands (BPM above baseline, smoothed HR)
    -----------------------------------------------------------------------------
    sympathetic_load_moderate_bpm : Above baseline: moderate emotional strategy.
    sympathetic_load_high_bpm     : Above baseline: deep grounding strategy.

    Timing
    ------
    sample_interval_s      : Seconds between biometric readings.
    feedback_loop_s        : Duration of one music-intervention cycle.
    cycles_per_session     : How many cycles constitute a full session.

    Smoothing & history
    -------------------
    hr_smoothing_window       : HR samples in moving average.
    temporal_history_maxlen   : Samples kept for trend / hysteresis (HR, HRV, arousal).
    """

    # LLM / API
    llm_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    llm_base_url: str = os.environ.get(
        "LLM_BASE_URL", "https://api.openai.com/v1"
    )
    llm_model: str = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")
    suno_api_key: str = os.environ.get("SUNO_API_KEY", "")

    # Knowledge graph / GraphRAG (optional)
    embedding_model: str = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    knowledge_data_dir: str = os.environ.get("KNOWLEDGE_DATA_DIR", "")
    knowledge_max_prompt_chars: int = _env_int("KNOWLEDGE_MAX_PROMPT_CHARS", 500)
    knowledge_max_anchor_chars: int = _env_int("KNOWLEDGE_MAX_ANCHOR_CHARS", 200)
    knowledge_chunk_size: int = _env_int("KNOWLEDGE_CHUNK_SIZE", 1200)
    knowledge_chunk_overlap: int = _env_int("KNOWLEDGE_CHUNK_OVERLAP", 200)
    knowledge_enabled_default: bool = os.environ.get(
        "KNOWLEDGE_ENABLED_DEFAULT", ""
    ).lower() in ("1", "true", "yes")
    # Dense + lexical rerank when embeddings OK: (1-w)*cosine + w*lexical_hit_ratio; w=0 → dense only.
    knowledge_hybrid_lexical_weight: float = _env_float(
        "KNOWLEDGE_HYBRID_LEXICAL_WEIGHT", 0.22
    )

    # Music generation bounds
    min_bpm: int = _env_int("MIN_BPM", 45)
    max_bpm: int = _env_int("MAX_BPM", 140)
    rhythm_reduction_pct: float = _env_float("RHYTHM_REDUCTION_PCT", 15.0)
    arousal_extra_bpm_reduction_max: float = _env_float(
        "AROUSAL_EXTRA_BPM_REDUCTION_MAX", 8.0
    )

    # Physiological thresholds (also used as curve anchors)
    hrv_safety_threshold: float = _env_float("HRV_SAFETY_THRESHOLD_MS", 40.0)
    max_noise_db: float = _env_float("MAX_NOISE_DB", 70.0)
    respiratory_elevated_threshold: float = _env_float(
        "RESPIRATORY_ELEVATED_THRESHOLD", 18.0
    )

    # Scoring curve anchors (physiologically plausible spans)
    hr_load_ref_delta_bpm: float = _env_float("HR_LOAD_REF_DELTA_BPM", 40.0)
    hrv_calm_ref_ms: float = _env_float("HRV_CALM_REF_MS", 80.0)
    resp_calm_br_min: float = _env_float("RESP_CALM_BR_MIN", 12.0)
    resp_stress_br_min: float = _env_float("RESP_STRESS_BR_MIN", 26.0)
    noise_calm_db: float = _env_float("NOISE_CALM_DB", 45.0)
    noise_stress_db: float = _env_float("NOISE_STRESS_DB", 85.0)
    motion_calm_g: float = _env_float("MOTION_CALM_G", 0.08)
    motion_stress_g: float = _env_float("MOTION_STRESS_G", 1.2)

    # Arousal weights (must sum to ~1.0 for interpretability)
    arousal_weight_hr: float = _env_float("AROUSAL_WEIGHT_HR", 0.35)
    arousal_weight_hrv: float = _env_float("AROUSAL_WEIGHT_HRV", 0.30)
    arousal_weight_resp: float = _env_float("AROUSAL_WEIGHT_RESP", 0.20)
    arousal_weight_noise: float = _env_float("AROUSAL_WEIGHT_NOISE", 0.10)
    arousal_weight_motion: float = _env_float("AROUSAL_WEIGHT_MOTION", 0.05)

    # Stress bands on 0–100 arousal_score
    arousal_low_max: float = _env_float("AROUSAL_LOW_MAX", 31.0)
    arousal_moderate_max: float = _env_float("AROUSAL_MODERATE_MAX", 66.0)

    # Masking intensity hysteresis
    masking_enter_arousal: float = _env_float("MASKING_ENTER_AROUSAL", 58.0)
    masking_exit_arousal: float = _env_float("MASKING_EXIT_AROUSAL", 48.0)
    masking_enter_consecutive_samples: int = _env_int(
        "MASKING_ENTER_CONSECUTIVE_SAMPLES", 2
    )
    masking_exit_consecutive_samples: int = _env_int(
        "MASKING_EXIT_CONSECUTIVE_SAMPLES", 2
    )

    # Noise safeguard hysteresis (startle constraints)
    noise_forbid_enter_db: float = _env_float("NOISE_FORBID_ENTER_DB", 72.0)
    noise_forbid_exit_db: float = _env_float("NOISE_FORBID_EXIT_DB", 66.0)
    noise_forbid_enter_consecutive_samples: int = _env_int(
        "NOISE_FORBID_ENTER_CONSECUTIVE_SAMPLES", 2
    )
    noise_forbid_exit_consecutive_samples: int = _env_int(
        "NOISE_FORBID_EXIT_CONSECUTIVE_SAMPLES", 2
    )

    # Emotional strategy breakpoints (BPM above resting baseline)
    sympathetic_load_moderate_bpm: float = _env_float(
        "SYMPATHETIC_LOAD_MODERATE_BPM", 10.0
    )
    sympathetic_load_high_bpm: float = _env_float(
        "SYMPATHETIC_LOAD_HIGH_BPM", 20.0
    )

    # Timing
    sample_interval_s: int = _env_int("SAMPLE_INTERVAL_S", 30)
    feedback_loop_s: int = _env_int("FEEDBACK_LOOP_S", 180)
    cycles_per_session: int = _env_int("CYCLES_PER_SESSION", 3)

    # HR smoothing & temporal buffers
    hr_smoothing_window: int = _env_int("HR_SMOOTHING_WINDOW", 5)
    temporal_history_maxlen: int = _env_int("TEMPORAL_HISTORY_MAXLEN", 12)


# Module-level default instance — importable directly
default_config = SystemConfig()
