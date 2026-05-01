"""
Single source for occupation → Suno genre paragraph text.

Used by BiometricProcessor when building MusicStrategy.genre_style.
"""

from __future__ import annotations

from typing import Dict

OCCUPATION_GENRE_PROMPTS: Dict[str, str] = {
    "software_engineer": (
        "Minimalist electronic, complexity-free, logic-uncluttered, "
        "supports focus without cognitive interference"
    ),
    "student": (
        "Focus-oriented ambient, concentration-supportive, "
        "background presence, non-intrusive harmonic motion"
    ),
    "healthcare_worker": (
        "Grounding meditative ambient, nervous system stabilizing, "
        "emotionally safe, clinically calibrated for high-stress recovery"
    ),
}

DEFAULT_GENRE_PROMPT = (
    "Meditative ambient, grounding, calming, emotionally neutral"
)

# Short tags for Layer 2 diagnostics / UI (not passed to Suno directly).
OCCUPATION_AESTHETIC_TAGS: Dict[str, str] = {
    "software_engineer": "minimalist_electronic",
    "student": "focus_ambient",
    "healthcare_worker": "grounding_meditative",
}
