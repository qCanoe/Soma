from music_ai_module.compiler import MusicPromptCompiler
from music_ai_module.config import SystemConfig
from music_ai_module.models import MusicStrategy, StaticUserProfile, dataclass_to_dict


def test_compiler_renders_strategy_only() -> None:
    compiler = MusicPromptCompiler(SystemConfig())

    processed = {
        "rhythm": {"target_bpm": 72, "sympathetic_load": 10},
        "texture": {"hrv_status": "flexible_resilient"},
        "state": {
            "arousal_score": 22.0,
            "stress_state": "low",
            "recovery_priority": "focus",
            "confidence": 1.0,
            "trend": "stable",
        },
        "music_strategy": dataclass_to_dict(
            MusicStrategy(
                tempo_bpm=72,
                genre_style="Test genre phrase",
                instrument_set=["piano", "ambient_strings"],
                acoustic_texture_description="clean, unadorned instruments",
                emotional_anchor_description="Supportive focus state",
                forbid_sharp_transients=False,
                forbid_high_freq_peaks=False,
                forbid_percussive_hits=False,
            )
        ),
    }

    profile = StaticUserProfile(
        occupation="software_engineer",
        age=28,
        height_cm=180,
        baseline_heart_rate=65,
    )

    result = compiler.compile(profile, processed, verify=False)
    assert "Test genre phrase" in result["prompt"]
    assert "Tempo 72 BPM" in result["prompt"]
    assert compiler._client is None


def test_metadata_includes_state_fields() -> None:
    compiler = MusicPromptCompiler(SystemConfig())
    processed = {
        "rhythm": {"target_bpm": 60, "sympathetic_load": 0},
        "texture": {"hrv_status": "flexible_resilient"},
        "state": {"arousal_score": 5.0},
        "music_strategy": dataclass_to_dict(
            MusicStrategy(
                tempo_bpm=60,
                genre_style="G",
                instrument_set=["cello_legato"],
                acoustic_texture_description="clean",
                emotional_anchor_description="calm",
                forbid_sharp_transients=False,
                forbid_high_freq_peaks=False,
                forbid_percussive_hits=False,
            )
        ),
    }
    profile = StaticUserProfile(
        occupation="student",
        age=20,
        height_cm=170,
        baseline_heart_rate=60,
    )
    meta = compiler.compile(profile, processed, verify=False)["metadata"]
    assert meta["arousal_score"] == 5.0

