"""
music_ai_module
===============

Biometric-to-music pipeline: converts Apple Watch physiological data into
a standardised music generation prompt via a layered architecture.

Public API
----------
    from music_ai_module import MusicAIPipeline, SystemConfig
    from music_ai_module.models import StaticUserProfile, AppleWatchBiometrics
"""

from .config import SystemConfig, default_config
from .compiler import MusicPromptCompiler
from .models import (
    AppleWatchBiometrics,
    BiometricFeatures,
    MusicStrategy,
    PhysiologicalState,
    StaticUserProfile,
    dataclass_to_dict,
)
from .pipeline import MusicAIPipeline
from .personalization import PersonalizationHints, resolve_personalization_strategy
from .processor import BiometricProcessor

__all__ = [
    "MusicAIPipeline",
    "BiometricProcessor",
    "MusicPromptCompiler",
    "SystemConfig",
    "default_config",
    "StaticUserProfile",
    "AppleWatchBiometrics",
    "BiometricFeatures",
    "PhysiologicalState",
    "MusicStrategy",
    "dataclass_to_dict",
    "PersonalizationHints",
    "resolve_personalization_strategy",
]
