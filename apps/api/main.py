"""
Local HTTP API wrapping ``MusicAIPipeline`` (Layer 1–3).

Run from repository root:

    pip install -e ".[api]"
    python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000

Then open http://127.0.0.1:8000/ for the static SPA and POST to /api/pipeline/run
or /api/healthkit/mock/run (camelCase vitals prototype).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from music_ai_module import MusicAIPipeline, StaticUserProfile, SystemConfig
from music_ai_module.models import AppleWatchBiometrics


_API_DIR = Path(__file__).resolve().parent
_WEB_ROOT = _API_DIR.parent / "web"


def _json_safe(obj: Any) -> Any:
    """Normalize numpy scalars and nested containers for JSON."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


# --- Request models (mirror StaticUserProfile / AppleWatchBiometrics) ---


class ProfileIn(BaseModel):
    occupation: str
    age: int
    height_cm: float
    baseline_heart_rate: int
    chronic_stress_sources: List[str] = Field(default_factory=list)
    music_preference: str = "ambient"
    sound_sensitivity: str = "normal"
    preferred_density: str = "medium"
    avoid_instruments: List[str] = Field(default_factory=list)
    therapy_goal: str = "calm"
    preferred_styles: List[str] = Field(default_factory=list)
    sounds_to_avoid: List[str] = Field(default_factory=list)
    rhythm_preference: str = "medium"
    volume_sensitivity: str = "moderate"
    sensitive_text: str = ""
    session_feedback_summary: Dict[str, Any] = Field(default_factory=dict)


class BiometricsIn(BaseModel):
    timestamp: datetime
    heart_rate: int
    heart_rate_variability: float
    respiratory_rate: int
    environmental_audio_exposure: float
    body_motion: Dict[str, float]
    wrist_temperature: Optional[float] = None
    blood_oxygen: Optional[float] = None
    sleep_stage: Optional[str] = None
    activity_state: Optional[str] = None
    sensor_confidence: Optional[float] = None
    measurement_window_s: Optional[float] = None
    resting_context: Optional[bool] = None


class PipelineRunIn(BaseModel):
    profile: ProfileIn
    biometrics: BiometricsIn
    verify: bool = False
    strict_validation: bool = False
    use_knowledge_graph: bool = False
    user_intent: Optional[str] = None
    session_feedback_summary: Optional[Dict[str, Any]] = None


# --- Mock HealthKit (camelCase vitals from web prototype) ---


class MockVitalsCamel(BaseModel):
    """Session vitalsSnapshot shape from docs/session-api-contract.md."""

    heartRate: int
    hrv: float
    respiratoryRate: int
    ambientNoise: float
    bodyMotion: Dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}
    )
    bloodOxygen: Optional[float] = None
    wristTemperature: Optional[float] = None
    sleepStage: Optional[str] = None
    stressScore: Optional[int] = None
    baselineHR: Optional[int] = None
    activityState: Optional[str] = None
    sensorConfidence: Optional[float] = None
    measurementWindowS: Optional[float] = None
    restingContext: Optional[bool] = None


class MockProfilePartial(BaseModel):
    """Subset of therapy profile; missing fields use prototype defaults."""

    occupation: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    baseline_heart_rate: Optional[int] = None
    chronic_stress_sources: Optional[List[str]] = None
    music_preference: Optional[str] = None
    sound_sensitivity: Optional[str] = None
    preferred_density: Optional[str] = None
    avoid_instruments: Optional[List[str]] = None
    therapy_goal: Optional[str] = None
    preferred_styles: Optional[List[str]] = None
    sounds_to_avoid: Optional[List[str]] = None
    rhythm_preference: Optional[str] = None
    volume_sensitivity: Optional[str] = None
    sensitive_text: Optional[str] = None
    session_feedback_summary: Optional[Dict[str, Any]] = None


class MockHealthKitRunIn(BaseModel):
    vitals: MockVitalsCamel
    profile: Optional[MockProfilePartial] = None
    timestamp: Optional[datetime] = None
    verify: bool = False
    strict_validation: bool = False
    use_knowledge_graph: bool = False
    user_intent: Optional[str] = None
    session_feedback_summary: Optional[Dict[str, Any]] = None


def _merge_mock_profile(
    partial: Optional[MockProfilePartial], vitals: MockVitalsCamel
) -> StaticUserProfile:
    p = partial or MockProfilePartial()
    baseline = (
        p.baseline_heart_rate
        if p.baseline_heart_rate is not None
        else (vitals.baselineHR if vitals.baselineHR is not None else 65)
    )
    return StaticUserProfile(
        occupation=p.occupation or "software_engineer",
        age=p.age if p.age is not None else 28,
        height_cm=p.height_cm if p.height_cm is not None else 170.0,
        baseline_heart_rate=baseline,
        chronic_stress_sources=list(p.chronic_stress_sources or []),
        music_preference=p.music_preference or "ambient",
        sound_sensitivity=p.sound_sensitivity or "normal",
        preferred_density=p.preferred_density or "medium",
        avoid_instruments=list(p.avoid_instruments or []),
        therapy_goal=p.therapy_goal or "calm",
        preferred_styles=list(p.preferred_styles or []),
        sounds_to_avoid=list(p.sounds_to_avoid or []),
        rhythm_preference=p.rhythm_preference or "medium",
        volume_sensitivity=p.volume_sensitivity or "moderate",
        sensitive_text=(p.sensitive_text or "").strip(),
        session_feedback_summary=dict(p.session_feedback_summary or {}),
    )


def _vitals_camel_to_biometrics(
    vitals: MockVitalsCamel,
    *,
    timestamp: datetime,
) -> AppleWatchBiometrics:
    return AppleWatchBiometrics(
        timestamp=timestamp,
        heart_rate=vitals.heartRate,
        heart_rate_variability=vitals.hrv,
        respiratory_rate=vitals.respiratoryRate,
        environmental_audio_exposure=float(vitals.ambientNoise),
        body_motion=dict(vitals.bodyMotion),
        wrist_temperature=vitals.wristTemperature,
        blood_oxygen=vitals.bloodOxygen,
        sleep_stage=vitals.sleepStage,
        activity_state=vitals.activityState,
        sensor_confidence=vitals.sensorConfidence,
        measurement_window_s=vitals.measurementWindowS,
        resting_context=vitals.restingContext,
    )


def create_app(*, serve_web: bool = True) -> FastAPI:
    app = FastAPI(
        title="Soma MindWave API",
        version="0.1.0",
        description="Runs ``MusicAIPipeline`` over JSON. Session CRUD is not implemented yet (see docs/session-api-contract.md).",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    config = SystemConfig()
    pipeline = MusicAIPipeline(config)

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/pipeline/run")
    def run_pipeline(body: PipelineRunIn) -> JSONResponse:
        profile = StaticUserProfile(
            occupation=body.profile.occupation,
            age=body.profile.age,
            height_cm=body.profile.height_cm,
            baseline_heart_rate=body.profile.baseline_heart_rate,
            chronic_stress_sources=list(body.profile.chronic_stress_sources),
            music_preference=body.profile.music_preference,
            sound_sensitivity=body.profile.sound_sensitivity,
            preferred_density=body.profile.preferred_density,
            avoid_instruments=list(body.profile.avoid_instruments),
            therapy_goal=body.profile.therapy_goal,
            preferred_styles=list(body.profile.preferred_styles),
            sounds_to_avoid=list(body.profile.sounds_to_avoid),
            rhythm_preference=body.profile.rhythm_preference,
            volume_sensitivity=body.profile.volume_sensitivity,
            sensitive_text=body.profile.sensitive_text,
            session_feedback_summary=dict(body.profile.session_feedback_summary or {}),
        )
        bio = body.biometrics
        biometrics = AppleWatchBiometrics(
            timestamp=bio.timestamp,
            heart_rate=bio.heart_rate,
            heart_rate_variability=bio.heart_rate_variability,
            respiratory_rate=bio.respiratory_rate,
            environmental_audio_exposure=bio.environmental_audio_exposure,
            body_motion=dict(bio.body_motion),
            wrist_temperature=bio.wrist_temperature,
            blood_oxygen=bio.blood_oxygen,
            sleep_stage=bio.sleep_stage,
            activity_state=bio.activity_state,
            sensor_confidence=bio.sensor_confidence,
            measurement_window_s=bio.measurement_window_s,
            resting_context=bio.resting_context,
        )
        result = pipeline.run(
            profile,
            biometrics,
            verify=body.verify,
            strict_validation=body.strict_validation,
            use_knowledge_graph=body.use_knowledge_graph,
            user_intent=body.user_intent,
            session_feedback_summary=body.session_feedback_summary,
        )
        safe = _json_safe(result)
        return JSONResponse(content=safe)

    @app.post("/api/healthkit/mock/run")
    def run_healthkit_mock(body: MockHealthKitRunIn) -> JSONResponse:
        """
        Prototype bridge: web ``vitalsSnapshot`` (camelCase) + optional partial
        profile → ``MusicAIPipeline`` without the client knowing full
        ``ProfileIn`` / ``BiometricsIn`` schemas.
        """
        ts = body.timestamp or datetime.now()
        profile = _merge_mock_profile(body.profile, body.vitals)
        biometrics = _vitals_camel_to_biometrics(body.vitals, timestamp=ts)
        result = pipeline.run(
            profile,
            biometrics,
            verify=body.verify,
            strict_validation=body.strict_validation,
            use_knowledge_graph=body.use_knowledge_graph,
            user_intent=body.user_intent,
            session_feedback_summary=body.session_feedback_summary,
        )
        safe = _json_safe(result)
        return JSONResponse(content=safe)

    if serve_web and _WEB_ROOT.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(_WEB_ROOT), html=True),
            name="web",
        )

    return app


# Default app for uvicorn apps.api.main:app
app = create_app(serve_web=_WEB_ROOT.is_dir())
