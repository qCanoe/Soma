"""
Layer 3: Music Prompt Compiler

Renders a MusicStrategy into the standard 7-segment Suno prompt.
No physiological inference — strategy is produced entirely in Layer 2.

OPTIONAL VERIFICATION — OpenAI-compatible LLM client is created lazily
only when verify=True.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from .config import SystemConfig, default_config
from .models import MusicStrategy, StaticUserProfile


class MusicPromptCompiler:
    """
    Compile a music generation prompt from a precomputed MusicStrategy.
    """

    def __init__(self, config: SystemConfig = default_config) -> None:
        self.config = config
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.config.llm_api_key,
                base_url=self.config.llm_base_url,
            )
        return self._client

    @staticmethod
    def _strategy_from_processed(processed_params: Dict[str, Any]) -> MusicStrategy:
        ms = processed_params.get("music_strategy")
        if ms is None:
            raise KeyError(
                "processed_params must include 'music_strategy' from BiometricProcessor"
            )
        return MusicStrategy(**ms)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile(
        self,
        profile: StaticUserProfile,
        processed_params: Dict[str, Any],
        verify: bool = False,
    ) -> Dict[str, Any]:
        """
        Build the 7-segment prompt from ``processed_params['music_strategy']``.

        ``profile`` is accepted for API compatibility; genre text is already
        resolved inside MusicStrategy.genre_style.
        """
        _ = profile  # MusicStrategy already embeds resolved genre / personalization
        strategy = self._strategy_from_processed(processed_params)

        segments = self._build_segments(strategy)
        segments_compact, truncated = self._apply_prompt_budget(
            segments, self.config.suno_max_prompt_chars
        )
        prompt = self._join_segments(segments_compact)
        metadata = self._build_metadata(prompt, processed_params)
        metadata["prompt_compacted"] = truncated
        metadata["prompt_budget_chars"] = self.config.suno_max_prompt_chars
        if len(prompt) > self.config.suno_max_prompt_chars:
            prompt = prompt[: self.config.suno_max_prompt_chars]
            metadata["prompt_hard_clipped"] = True
            metadata["prompt_length_chars"] = len(prompt)
        result: Dict[str, Any] = {
            "prompt": prompt,
            "segments": segments_compact,
            "metadata": metadata,
        }

        if verify:
            result = self._verify(result)

        return result

    # ------------------------------------------------------------------
    # Segment builders
    # ------------------------------------------------------------------

    def _build_segments(self, strategy: MusicStrategy) -> Dict[str, str]:
        return {
            "music_type": self._seg_music_type(),
            "genre": self._seg_genre(strategy),
            "tempo": self._seg_tempo(strategy),
            "instruments": self._seg_instruments(strategy),
            "texture": self._seg_texture(strategy),
            "emotional_anchor": self._seg_emotional_anchor(strategy),
            "constraints": self._seg_constraints(strategy),
        }

    @staticmethod
    def _seg_music_type() -> str:
        return "Pure instrumental music, generative and continuous"

    @staticmethod
    def _seg_genre(strategy: MusicStrategy) -> str:
        return strategy.genre_style

    def _seg_tempo(self, strategy: MusicStrategy) -> str:
        bpm = int(
            max(
                self.config.min_bpm,
                min(self.config.max_bpm, strategy.tempo_bpm),
            )
        )
        return f"Tempo {bpm} BPM"

    @staticmethod
    def _seg_instruments(strategy: MusicStrategy) -> str:
        instruments = ", ".join(strategy.instrument_set)
        return f"Instruments: {instruments}"

    @staticmethod
    def _seg_texture(strategy: MusicStrategy) -> str:
        return "Acoustic texture: " + strategy.acoustic_texture_description

    @staticmethod
    def _seg_emotional_anchor(strategy: MusicStrategy) -> str:
        return "Emotional anchor: " + strategy.emotional_anchor_description

    def _seg_constraints(self, strategy: MusicStrategy) -> str:
        items = []
        if strategy.forbid_sharp_transients:
            items.append(
                "FORBIDDEN: Sharp transient attacks or sudden envelope spikes "
                "(startle trigger prevention)"
            )
        if strategy.forbid_high_freq_peaks:
            items.append(
                "FORBIDDEN: High-frequency peaks above 8 kHz "
                "(environmental noise summation prevents masking)"
            )
        if strategy.forbid_percussive_hits:
            items.append(
                "FORBIDDEN: Percussive hits, drums, or impact sounds "
                "(sudden acoustic threats)"
            )
        items += [
            "FORBIDDEN: Sudden volume jumps or dynamic compression artifacts",
            "FORBIDDEN: Dissonant intervals or tonal instability "
            "(harmonic threat detection)",
        ]
        return "Strict negative constraints: " + "; ".join(items)

    def _apply_prompt_budget(
        self, segments: Dict[str, str], max_chars: int
    ) -> Tuple[Dict[str, str], bool]:
        """Shorten segments so joined prompt fits Suno-style character limits."""
        order = [
            "music_type",
            "genre",
            "tempo",
            "instruments",
            "texture",
            "emotional_anchor",
            "constraints",
        ]
        out: Dict[str, str] = {
            k: segments[k] for k in order if segments.get(k)
        }

        def joined() -> str:
            return " | ".join(out[k] for k in order if out.get(k))

        if len(joined()) <= max_chars:
            return out, False

        def trim_key(key: str, limit: int) -> None:
            v = out.get(key) or ""
            if len(v) <= limit:
                return
            out[key] = v[: max(1, limit - 3)].rstrip() + "..."

        rounds = 0
        while len(joined()) > max_chars and rounds < 28:
            rounds += 1
            if len(out.get("emotional_anchor", "")) > 52:
                trim_key("emotional_anchor", 50)
            elif len(out.get("texture", "")) > 62:
                trim_key("texture", 58)
            elif len(out.get("genre", "")) > 95:
                trim_key("genre", 88)
            elif out.get("instruments", "").count(",") > 1:
                ins = out["instruments"]
                prefix = "Instruments: "
                if ins.startswith(prefix):
                    parts = [
                        p.strip()
                        for p in ins[len(prefix) :].split(",")
                        if p.strip()
                    ]
                    if len(parts) > 2:
                        out["instruments"] = prefix + ", ".join(parts[:2])
            elif len(out.get("music_type", "")) > 42:
                out["music_type"] = "Pure instrumental, continuous"
            else:
                trim_key("constraints", min(220, max_chars // 2))
                if len(joined()) > max_chars:
                    trim_key("constraints", 160)
                break

        if len(joined()) > max_chars:
            for lim in (200, 160, 120, 90, 70):
                trim_key("constraints", lim)
                if len(joined()) <= max_chars:
                    break
            if len(joined()) > max_chars:
                trim_key("genre", 60)
                trim_key("texture", 44)
                trim_key("emotional_anchor", 40)
        return out, True

    # ------------------------------------------------------------------
    # Assembly helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _join_segments(segments: Dict[str, str]) -> str:
        ordered = [
            "music_type",
            "genre",
            "tempo",
            "instruments",
            "texture",
            "emotional_anchor",
            "constraints",
        ]
        return " | ".join(segments[k] for k in ordered if segments.get(k))

    @staticmethod
    def _build_metadata(prompt: str, processed_params: Dict[str, Any]) -> Dict[str, Any]:
        token_estimate = int(len(prompt.split()) * 1.3)
        rhythm = processed_params["rhythm"]
        texture = processed_params["texture"]
        state = processed_params.get("state") or {}

        meta: Dict[str, Any] = {
            "prompt_length_chars": len(prompt),
            "prompt_length_tokens_estimate": token_estimate,
            "target_bpm": rhythm["target_bpm"],
            "sympathetic_load": rhythm["sympathetic_load"],
            "hrv_status": texture["hrv_status"],
            "arousal_score": state.get("arousal_score"),
            "stress_state": state.get("stress_state"),
            "recovery_priority": state.get("recovery_priority"),
            "confidence": state.get("confidence"),
            "trend": state.get("trend"),
            "api_cost_estimate_usd": token_estimate * 0.00002,
            "validation_status": "pass" if len(prompt) < 2000 else "warning",
        }
        ca = processed_params.get("clinical_audit")
        if isinstance(ca, dict):
            meta["clinical_audit"] = {
                "query_used": ca.get("query_used"),
                "evidence_summary": ca.get("evidence_summary"),
                "bpm_min": ca.get("bpm_min"),
                "bpm_max": ca.get("bpm_max"),
                "disclaimer": ca.get("disclaimer"),
            }
        return meta

    # ------------------------------------------------------------------
    # Optional LLM verification
    # ------------------------------------------------------------------

    def _verify(self, result: Dict[str, Any]) -> Dict[str, Any]:
        raw_prompt = result["prompt"]
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a music production prompt engineer. "
                            "Your ONLY task is to verify technical completeness "
                            "and clarity of music generation prompts. "
                            "DO NOT add creative elements, subjective descriptions, "
                            "or artistic interpretations. "
                            "Only verify: 1) All required fields present, "
                            "2) BPM is an exact number, "
                            "3) Instruments are realistic, "
                            "4) Constraints are unambiguous. "
                            "Return ONLY the prompt text "
                            "(optionally with minor clarity fixes). "
                            "NO explanations, NO additions, NO creative changes."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Verify technical completeness of this music prompt:"
                            f"\n\n{raw_prompt}"
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=200,
                timeout=10,
            )
            result["verified_prompt"] = response.choices[0].message.content.strip()
            result["verification_status"] = "success"
            result["verification_cost_usd"] = 0.0005
        except Exception as exc:
            result["verification_status"] = "skipped"
            result["verification_error"] = str(exc)

        return result
