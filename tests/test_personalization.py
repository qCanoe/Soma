from music_ai_module.models import StaticUserProfile
from music_ai_module.personalization import resolve_personalization_strategy


def test_volume_soft_triggers_safety_bias() -> None:
    p = StaticUserProfile(
        occupation="software_engineer",
        age=30,
        height_cm=175,
        baseline_heart_rate=65,
        volume_sensitivity="soft",
    )
    h = resolve_personalization_strategy(p)
    assert h.forbid_sharp_extra is True
    assert h.forbid_high_freq_extra is True


def test_session_feedback_too_fast_lowers_drive() -> None:
    p = StaticUserProfile(
        occupation="student",
        age=20,
        height_cm=170,
        baseline_heart_rate=60,
        session_feedback_summary={
            "sound_fit": "too_fast",
            "historical_sound_issues": ["too_fast"],
        },
    )
    h = resolve_personalization_strategy(p)
    assert h.tempo_offset_bpm < 0
    assert h.rhythm_drive_scale < 1.0


def test_preferred_styles_add_genre_extras() -> None:
    p = StaticUserProfile(
        occupation="healthcare_worker",
        age=40,
        height_cm=165,
        baseline_heart_rate=72,
        preferred_styles=["jazz", "ambient"],
    )
    h = resolve_personalization_strategy(p)
    assert any("jazz" in g for g in h.genre_extras)
