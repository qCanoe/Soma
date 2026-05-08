"""
Main Pipeline — end-to-end orchestration of all layers.

Usage (minimal)
---------------
    from music_ai_module.pipeline import MusicAIPipeline
    from music_ai_module.models import StaticUserProfile, AppleWatchBiometrics
    from datetime import datetime

    pipeline = MusicAIPipeline()

    user = StaticUserProfile(
        occupation="software_engineer",
        age=28,
        height_cm=180,
        baseline_heart_rate=65,
        chronic_stress_sources=["work_deadline"],
        music_preference="minimalist_ambient",
    )

    biometrics = AppleWatchBiometrics(
        timestamp=datetime.now(),
        heart_rate=102,
        heart_rate_variability=35.5,
        respiratory_rate=18,
        environmental_audio_exposure=68,
        body_motion={"x": 0.3, "y": 0.25, "z": 0.15},
        blood_oxygen=97.5,
        sleep_stage="awake",
    )

    result = pipeline.run(user, biometrics)
    print(result["prompt"])           # → final music generation prompt
    print(result["processed_params"]) # → Layer-2 bundle + music_strategy
"""

from __future__ import annotations

import warnings
from dataclasses import replace
from typing import Any, Dict, Optional

from .compiler import MusicPromptCompiler
from .config import SystemConfig, default_config
from .models import AppleWatchBiometrics, StaticUserProfile
from .processor import BiometricProcessor


class MusicAIPipeline:
    """
    Orchestrates Layer 1 → Layer 2 → Layer 3.

    Validation policy
    -----------------
    By default, invalid sensor ranges emit warnings and processing continues
    using the current reading (see README — downstream clinical products should
    gate on ``validation_errors``).

    Set ``strict_validation=True`` to raise ``ValueError`` when any check fails.
    """

    def __init__(self, config: SystemConfig = default_config) -> None:
        self.config = config
        self.processor = BiometricProcessor(config)
        self.compiler = MusicPromptCompiler(config)

    def run(
        self,
        profile: StaticUserProfile,
        biometrics: AppleWatchBiometrics,
        verify: bool = False,
        strict_validation: bool = False,
        use_knowledge_graph: bool = False,
        user_intent: Optional[str] = None,
        session_feedback_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the full pipeline.

        Returns
        -------
        Flat dict with compiled prompt, segments, metadata, processed_params
        (features, state, music_strategy), and validation_errors.
        """
        errors = biometrics.validate()

        profile_eff = profile
        if session_feedback_summary:
            merged_fb = dict(profile.session_feedback_summary or {})
            merged_fb.update(
                {
                    k: v
                    for k, v in session_feedback_summary.items()
                    if v is not None
                }
            )
            profile_eff = replace(
                profile, session_feedback_summary=merged_fb
            )

        if errors:
            for err in errors:
                warnings.warn(f"Biometric validation: {err}", UserWarning, stacklevel=2)
            if strict_validation:
                raise ValueError(
                    "Biometric validation failed: " + "; ".join(errors)
                )

        processed = self.processor.process(
            profile_eff, biometrics, validation_errors=errors
        )

        use_kg = use_knowledge_graph or self.config.knowledge_enabled_default
        if use_kg:
            from .knowledge.auditor import (
                ClinicalMusicAuditor,
                apply_audit_to_processed,
            )

            auditor = ClinicalMusicAuditor(self.config)
            audit = auditor.audit(profile_eff, processed, user_intent=user_intent)
            processed = apply_audit_to_processed(processed, audit, self.config)

        compiled = self.compiler.compile(profile_eff, processed, verify=verify)

        expl = processed.get("strategy_explanation")
        if isinstance(expl, dict):
            compiled["metadata"]["strategy_explanation"] = expl

        return {
            **compiled,
            "processed_params": processed,
            "validation_errors": errors,
        }

    @staticmethod
    def describe(result: Dict[str, Any]) -> None:
        """Print a human-readable summary of a pipeline result."""
        sep = "=" * 70

        print(f"\n{sep}")
        print("COMPILED MUSIC GENERATION PROMPT")
        print(sep)
        print(f"\n{result['prompt']}\n")

        print(sep)
        print("SEGMENT BREAKDOWN")
        print(sep)
        for name, content in result["segments"].items():
            print(f"\n[{name.upper()}]\n{content}\n")

        print(sep)
        print("PHYSIOLOGICAL STATE (Layer 2)")
        print(sep)
        st = result["processed_params"].get("state") or {}
        print(f"  Arousal score      : {st.get('arousal_score')}")
        print(f"  Stress state       : {st.get('stress_state')}")
        print(f"  Recovery priority  : {st.get('recovery_priority')}")
        print(f"  Confidence         : {st.get('confidence')}")
        print(f"  Trend              : {st.get('trend')}")

        print(sep)
        print("ACOUSTIC PARAMETERS (legacy Layer 2 summary)")
        print(sep)
        rhythm = result["processed_params"]["rhythm"]
        texture = result["processed_params"]["texture"]
        breathing = result["processed_params"]["breathing"]
        safeguard = result["processed_params"]["safeguards"]
        print(f"  Target BPM         : {rhythm['target_bpm']}")
        print(f"  Raw HR             : {rhythm['current_hr']}")
        print(f"  Smoothed HR        : {rhythm.get('smoothed_hr')}")
        print(f"  Sympathetic Load   : +{rhythm['sympathetic_load']} BPM vs baseline")
        print(f"  HRV Status         : {texture['hrv_status']}")
        print(f"  Pink Noise         : {texture['apply_pink_noise']}")
        print(f"  Breathing Status   : {breathing['respiratory_status']}")
        print(f"  Environment        : {safeguard['noise_environment']}")

        print(sep)
        print("METADATA")
        print(sep)
        for key, val in result["metadata"].items():
            if isinstance(val, float) and val < 0.01:
                print(f"  {key}: {val:.2e}")
            else:
                print(f"  {key}: {val}")

        if result.get("verification_status"):
            print(f"\n  Verification       : {result['verification_status']}")
