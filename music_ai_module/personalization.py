"""
Personalization: map StaticUserProfile (+ optional session feedback) to concrete
hints for Layer 2 strategy building.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .models import StaticUserProfile


def _norm_list(xs: Optional[List[str]]) -> List[str]:
    if not xs:
        return []
    return [str(x).strip() for x in xs if str(x).strip()]


def _feedback_tags(summary: Optional[Dict[str, Any]]) -> Set[str]:
    """Flatten session_feedback_summary into lowercase tags."""
    if not summary:
        return set()
    tags: Set[str] = set()
    sf = summary.get("sound_fit") or summary.get("soundFit")
    if isinstance(sf, str) and sf.lower() != "good":
        tags.add(f"sound:{sf.lower()}")
    hist = summary.get("historical_sound_issues") or summary.get(
        "historicalSoundIssues"
    )
    if isinstance(hist, list):
        for x in hist:
            if isinstance(x, str) and x.lower() != "good":
                tags.add(f"sound:{x.lower()}")
    help_w = summary.get("helpfulness")
    if isinstance(help_w, str) and help_w.lower() in ("not_helped", "hurt"):
        tags.add("help:negative")
    notes = summary.get("notes") or summary.get("session_notes")
    if isinstance(notes, str):
        n = notes.lower()
        for key, tag in (
            ("too loud", "loud"),
            ("too sharp", "sharp"),
            ("too fast", "fast"),
            ("busy", "busy"),
            ("dense", "dense"),
            ("cold", "cold"),
            ("monoton", "monotone"),
        ):
            if key in n:
                tags.add(f"note:{tag}")
    return tags


@dataclass
class PersonalizationHints:
    """Resolved personalization cues for BiometricProcessor."""

    genre_extras: List[str] = field(default_factory=list)
    avoid_material_tokens: List[str] = field(default_factory=list)
    forbid_high_freq_extra: bool = False
    forbid_sharp_extra: bool = False
    forbid_perc_extra: bool = False
    density_scale: float = 1.0  # <1 → fewer layers / shorter instrument list
    rhythm_drive_scale: float = 1.0  # <1 → less pulse / more legato bias
    tempo_offset_bpm: int = 0
    instrument_cap: Optional[int] = None
    texture_soften: bool = False  # gentler wording / less bright timbre hints

    def explain_applied(self) -> List[str]:
        lines: List[str] = []
        if self.genre_extras:
            lines.append("genre_modifiers: " + "; ".join(self.genre_extras[:4]))
        if self.avoid_material_tokens:
            lines.append(
                "avoid: " + ", ".join(self.avoid_material_tokens[:8])
            )
        flags = []
        if self.forbid_sharp_extra:
            flags.append("softer_onsets")
        if self.forbid_high_freq_extra:
            flags.append("limit_highs")
        if self.forbid_perc_extra:
            flags.append("reduce_percussion")
        if flags:
            lines.append("safety_bias: " + ", ".join(flags))
        if self.tempo_offset_bpm:
            lines.append(f"tempo_offset_bpm: {self.tempo_offset_bpm:+d}")
        if self.density_scale < 0.95:
            lines.append(f"density_scale: {self.density_scale:.2f}")
        if self.rhythm_drive_scale < 0.95:
            lines.append(f"rhythm_drive_scale: {self.rhythm_drive_scale:.2f}")
        if self.instrument_cap is not None:
            lines.append(f"instrument_cap: {self.instrument_cap}")
        return lines


def resolve_personalization_strategy(
    profile: StaticUserProfile,
) -> PersonalizationHints:
    """
    Convert profile fields + embedded session_feedback_summary into hints.
    """
    hints = PersonalizationHints()
    pref_styles = _norm_list(getattr(profile, "preferred_styles", None))
    for st in pref_styles[:6]:
        hints.genre_extras.append(f"listener prefers {st} repertoire cues")

    sounds_avoid = _norm_list(getattr(profile, "sounds_to_avoid", None))
    sens_txt = getattr(profile, "sensitive_text", None) or ""
    if isinstance(sens_txt, str) and sens_txt.strip():
        hints.avoid_material_tokens.append(sens_txt.strip().lower())
    for s in sounds_avoid:
        hints.avoid_material_tokens.append(s.lower())

    vol = str(getattr(profile, "volume_sensitivity", "") or "").lower().strip()
    if vol == "soft":
        hints.forbid_sharp_extra = True
        hints.forbid_high_freq_extra = True
        hints.texture_soften = True
        hints.genre_extras.append("conservative dynamics; intimate monitoring distance")
    elif vol == "immersive":
        hints.genre_extras.append("slightly fuller bed; still no startling transients")

    sens = str(profile.sound_sensitivity or "").lower().strip()
    if sens == "high":
        hints.forbid_high_freq_extra = True
        hints.forbid_sharp_extra = True
        hints.texture_soften = True
    elif sens == "low":
        hints.genre_extras.append("slightly richer harmonics without harsh treble")

    dens = str(profile.preferred_density or "").lower().strip()
    if dens == "low":
        hints.density_scale = 0.72
        hints.instrument_cap = 2
        hints.rhythm_drive_scale *= 0.85
    elif dens == "high":
        hints.density_scale = 1.08
        hints.instrument_cap = 5

    rhythm_pref = str(getattr(profile, "rhythm_preference", "") or "").lower().strip()
    if rhythm_pref == "low":
        hints.rhythm_drive_scale *= 0.7
        hints.tempo_offset_bpm -= 4
        hints.genre_extras.append(
            "minimal pulse; sustained tones and long breath-like phrases"
        )
    elif rhythm_pref == "high":
        hints.rhythm_drive_scale *= 1.1
        hints.tempo_offset_bpm += 4
        hints.genre_extras.append("subtle motional pulse without percussion")

    fb = getattr(profile, "session_feedback_summary", None) or {}
    if isinstance(fb, dict):
        tags = _feedback_tags(fb)
        if "sound:too_fast" in tags:
            hints.tempo_offset_bpm -= 8
            hints.rhythm_drive_scale *= 0.72
        if "sound:too_busy" in tags:
            hints.density_scale *= 0.65
            hints.instrument_cap = min(hints.instrument_cap or 4, 2)
        if "sound:too_sharp" in tags or "note:sharp" in tags:
            hints.forbid_sharp_extra = True
            hints.forbid_high_freq_extra = True
        if "sound:disliked" in tags:
            hints.genre_extras.append(
                "fresh orchestration; avoid generic hold-music clichés"
            )
        if "note:loud" in tags:
            hints.forbid_sharp_extra = True
            hints.texture_soften = True
        if "note:dense" in tags or "note:busy" in tags:
            hints.density_scale *= 0.75
        if "note:cold" in tags:
            hints.genre_extras.append("warmer spectral tilt; gentle consonant harmony")
            hints.texture_soften = True
        if "note:monotone" in tags:
            hints.genre_extras.append(
                "slow harmonic drift with subtle variation; not static looping"
            )

    # Clamp derived scales
    hints.density_scale = max(0.55, min(1.2, hints.density_scale))
    hints.rhythm_drive_scale = max(0.55, min(1.2, hints.rhythm_drive_scale))
    hints.tempo_offset_bpm = int(max(-15, min(12, hints.tempo_offset_bpm)))
    return hints
