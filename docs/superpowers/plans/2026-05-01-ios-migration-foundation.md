# iOS App Migration Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Soma/MindWave 迁移到原生 iOS App 建立第一阶段基础：明确架构边界、锁定跨平台数据契约、用 Swift 复刻核心生理信号到音乐策略管线，并用 parity fixtures 保护 Python 与 Swift 行为一致。

**Architecture:** 现有 Python `music_ai_module` 在迁移期作为算法真源和 parity oracle；新增 `ios/SomaCore` Swift Package 承载 iOS 端可离线运行的 Layer 1 到 Layer 3 确定性逻辑。iOS App 后续负责 HealthKit 授权与采样、SwiftUI 会话体验、AVFoundation 播放；Suno 生成、LLM 验证、GraphRAG 和所有密钥必须留在服务端，不进入 App bundle。

**Tech Stack:** Python 3.10+, pytest, Swift 5.10+, Swift Package Manager, XCTest, Foundation；后续 App 层使用 SwiftUI, HealthKit, AVFoundation, URLSession。

---

## Scope Check

整个项目迁移到 iOS 覆盖多个独立子系统，不能放进一个巨型计划一次性实现。建议拆成五个可独立交付的计划：

- `ios-migration-foundation`：本计划，完成架构边界、契约、Swift 核心算法和 parity 测试。
- `ios-swiftui-shell`：建立 Xcode iOS App、主会话页面、profile/vitals/player UI、SomaCore 集成。
- `ios-healthkit-adapter`：HealthKit 权限、采样、后台限制、模拟数据与真实数据切换。
- `suno-backend-proxy`：服务端代理 Suno API，移除浏览器和 App 内的用户密钥保存。
- `clinical-knowledge-backend`：GraphRAG/LLM 审计保留在 Python 服务端，并通过 API 给 App 提供安全约束。

本计划只交付第一项。完成后，团队可以在 iOS 端稳定复用核心算法，再开始做 SwiftUI 和 HealthKit。

## File Structure

- Create: `docs/ios-migration-architecture.md`
  - 记录迁移架构、所有权边界、数据流、隐私约束和后续计划拆分。
- Create: `scripts/export_ios_parity_fixtures.py`
  - 从现有 Python `MusicAIPipeline` 生成确定性的 JSON parity fixtures。
- Create: `tests/fixtures/ios_parity_cases.json`
  - 保存 Swift 端必须对齐的代表性输入输出样本。
- Create: `tests/test_ios_parity_fixtures.py`
  - 保护 fixture schema，避免 Swift 端读取格式漂移。
- Create: `ios/SomaCore/Package.swift`
  - Swift Package 定义，支持本地 XCTest，不依赖完整 Xcode app。
- Create: `ios/SomaCore/Sources/SomaCore/Models.swift`
  - Swift 版 `StaticUserProfile`、`AppleWatchBiometrics`、`BiometricFeatures`、`PhysiologicalState`、`MusicStrategy`。
- Create: `ios/SomaCore/Sources/SomaCore/SystemConfig.swift`
  - Swift 版可注入配置，默认值与 `music_ai_module/config.py` 对齐。
- Create: `ios/SomaCore/Sources/SomaCore/BiometricProcessor.swift`
  - Swift 版 Layer 2 规则引擎，先实现核心确定性路径：HR 平滑、arousal scoring、target BPM、instrument/texture/safeguard。
- Create: `ios/SomaCore/Sources/SomaCore/MusicPromptCompiler.swift`
  - Swift 版 Layer 3 prompt renderer，不包含 LLM 验证。
- Create: `ios/SomaCore/Tests/SomaCoreTests/ModelsTests.swift`
  - 验证生理范围校验和模型 Codable。
- Create: `ios/SomaCore/Tests/SomaCoreTests/BiometricProcessorTests.swift`
  - 验证 BPM clamp、HRV 对 arousal 影响、禁用乐器过滤、噪声 hysteresis。
- Create: `ios/SomaCore/Tests/SomaCoreTests/MusicPromptCompilerTests.swift`
  - 验证 7 段 prompt 输出与 metadata。
- Create: `ios/SomaCore/Tests/SomaCoreTests/ParityFixtureTests.swift`
  - 读取 Python fixture，验证 Swift 输出关键字段与 Python 一致。
- Create: `ios/SomaCore/Tests/SomaCoreTests/Fixtures/ios_parity_cases.json`
  - Swift Package resource 副本，由 Python export script 同步写入。

## Migration Directions To Start

1. 先稳定契约，不先画 App 页面。当前 Web 原型把 UI、Suno、demo cases、profile localStorage、vitals 计算混在一个 `apps/web/index.html` 内；迁移前要先确定 iOS 能调用的核心输入输出。
2. 先原生移植确定性核心，不把 Python 打包进 iOS。`music_ai_module/models.py`、`processor.py`、`compiler.py` 基本是纯规则逻辑，适合 Swift Package；GraphRAG、OpenAI、Suno 保持服务端。
3. 先用 fixture 对齐行为，再接 HealthKit。HealthKit 真机数据噪声大、权限多，如果没有 parity fixtures，很难判断 bug 来自传感器还是算法迁移。
4. 先改密钥架构，再做上线版本。Web 当前把 Suno key 放在 `localStorage`，iOS 不能复制这个模式；App Store 版本必须通过服务端代理持有第三方 API key。
5. 先把医疗声明和隐私边界写入架构文档。项目涉及 wellness/biometrics/music therapy，App 不能宣称诊断或治疗疾病。

---

### Task 1: Document iOS Migration Boundaries

**Files:**
- Create: `docs/ios-migration-architecture.md`
- Test: existing Python test suite

- [ ] **Step 1: Write the migration architecture document**

Create `docs/ios-migration-architecture.md` with this content:

```markdown
# Soma iOS Migration Architecture

## Objective

Soma is moving from a static web prototype plus Python pipeline into a native iOS app that can read Apple Watch / HealthKit signals, generate a personalized music strategy, and play therapeutic soundscapes.

## Source System

- `music_ai_module/models.py`: canonical profile and biometric data model.
- `music_ai_module/processor.py`: canonical deterministic Layer 2 rules engine.
- `music_ai_module/compiler.py`: canonical deterministic Layer 3 Suno prompt renderer.
- `music_ai_module/knowledge/`: optional clinical knowledge graph and audit layer.
- `apps/web/index.html`: static UI prototype with profile modal, vitals modal, Suno generation, cached demo tracks, and a mirrored vitals calculation.

## Target Ownership

- iOS App owns HealthKit permission, Apple Watch data reads, session UI, local preferences, audio playback, and user-facing safety copy.
- `SomaCore` Swift Package owns deterministic Layer 1 to Layer 3 logic that can run offline on device.
- Backend owns Suno API calls, LLM verification, GraphRAG retrieval, clinical audit, rate limiting, and all third-party secrets.
- Python package remains the migration oracle until Swift parity tests cover the production scenarios.

## Data Flow

1. `HealthKitAdapter` reads heart rate, HRV, respiratory rate, SpO2, wrist temperature, sleep stage, ambient sound exposure, and motion-derived values.
2. iOS maps the sample into `AppleWatchBiometrics`.
3. `SomaCore.BiometricProcessor` produces features, physiological state, and music strategy.
4. `SomaCore.MusicPromptCompiler` renders a deterministic prompt.
5. iOS sends the prompt plus session metadata to the backend.
6. Backend calls Suno and returns task status plus playable audio URLs.
7. iOS plays audio with `AVPlayer` and displays vitals/session state.

## Security And Privacy

- Do not store Suno, OpenAI, or embedding provider API keys inside the iOS app.
- Do not send raw HealthKit data to third-party APIs directly from the device.
- Do not persist raw biometric streams unless a product decision explicitly requires it.
- User-facing copy must describe the product as wellness support, not diagnosis or treatment.
- All outbound API calls should use TLS and short-lived authenticated backend sessions.

## Migration Phases

1. Foundation: contract docs, parity fixtures, Swift `SomaCore`.
2. SwiftUI shell: session screen, profile, vitals, player, settings.
3. HealthKit adapter: permissions, real samples, simulator fixture mode.
4. Backend proxy: Suno generation, polling, cancellation, rate limits.
5. Knowledge backend: GraphRAG and clinical audit served by Python API.
6. TestFlight hardening: privacy strings, error states, offline states, accessibility, battery behavior.
```

- [ ] **Step 2: Run existing regression tests**

Run:

```bash
python -m pytest tests -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 3: Commit**

```bash
git add docs/ios-migration-architecture.md
git commit -m "docs: define iOS migration boundaries"
```

---

### Task 2: Export Python Parity Fixtures

**Files:**
- Create: `scripts/export_ios_parity_fixtures.py`
- Create: `tests/fixtures/ios_parity_cases.json`
- Create: `tests/test_ios_parity_fixtures.py`
- Test: `tests/test_ios_parity_fixtures.py`

- [ ] **Step 1: Write the failing fixture schema test**

Create `tests/test_ios_parity_fixtures.py`:

```python
import json
from pathlib import Path


FIXTURE_PATH = Path("tests/fixtures/ios_parity_cases.json")


def test_ios_parity_fixture_schema() -> None:
    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert [case["id"] for case in cases] == [
        "calm_baseline",
        "high_arousal_noise",
        "sleep_sensitive",
    ]

    for case in cases:
        assert set(case) == {"id", "profile", "biometrics", "expected"}
        assert "baseline_heart_rate" in case["profile"]
        assert "heart_rate" in case["biometrics"]
        assert "target_bpm" in case["expected"]
        assert "arousal_score" in case["expected"]
        assert "stress_state" in case["expected"]
        assert "recovery_priority" in case["expected"]
        assert "instrument_set" in case["expected"]
        assert "prompt" in case["expected"]
        assert isinstance(case["expected"]["target_bpm"], int)
        assert isinstance(case["expected"]["arousal_score"], float)
        assert isinstance(case["expected"]["instrument_set"], list)
        assert len(case["expected"]["prompt"]) > 40
```

- [ ] **Step 2: Run the schema test to verify it fails**

Run:

```bash
python -m pytest tests/test_ios_parity_fixtures.py -q
```

Expected:

```text
FileNotFoundError: [Errno 2] No such file or directory: 'tests/fixtures/ios_parity_cases.json'
```

- [ ] **Step 3: Write the fixture export script**

Create `scripts/export_ios_parity_fixtures.py`:

```python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from music_ai_module.models import AppleWatchBiometrics, StaticUserProfile
from music_ai_module.pipeline import MusicAIPipeline


ROOT = Path(__file__).resolve().parents[1]
PYTHON_FIXTURE = ROOT / "tests" / "fixtures" / "ios_parity_cases.json"
SWIFT_FIXTURE = (
    ROOT
    / "ios"
    / "SomaCore"
    / "Tests"
    / "SomaCoreTests"
    / "Fixtures"
    / "ios_parity_cases.json"
)


def _profile_dict(profile: StaticUserProfile) -> dict[str, Any]:
    return {
        "occupation": profile.occupation,
        "age": profile.age,
        "height_cm": profile.height_cm,
        "baseline_heart_rate": profile.baseline_heart_rate,
        "chronic_stress_sources": profile.chronic_stress_sources,
        "music_preference": profile.music_preference,
        "sound_sensitivity": profile.sound_sensitivity,
        "preferred_density": profile.preferred_density,
        "avoid_instruments": profile.avoid_instruments,
        "therapy_goal": profile.therapy_goal,
    }


def _biometrics_dict(biometrics: AppleWatchBiometrics) -> dict[str, Any]:
    return {
        "timestamp": biometrics.timestamp.isoformat(),
        "heart_rate": biometrics.heart_rate,
        "heart_rate_variability": biometrics.heart_rate_variability,
        "respiratory_rate": biometrics.respiratory_rate,
        "environmental_audio_exposure": biometrics.environmental_audio_exposure,
        "body_motion": biometrics.body_motion,
        "wrist_temperature": biometrics.wrist_temperature,
        "blood_oxygen": biometrics.blood_oxygen,
        "sleep_stage": biometrics.sleep_stage,
    }


def _expected(result: dict[str, Any]) -> dict[str, Any]:
    processed = result["processed_params"]
    strategy = processed["music_strategy"]
    state = processed["state"]
    return {
        "target_bpm": processed["rhythm"]["target_bpm"],
        "arousal_score": round(float(state["arousal_score"]), 4),
        "stress_state": state["stress_state"],
        "recovery_priority": state["recovery_priority"],
        "instrument_set": strategy["instrument_set"],
        "forbid_sharp_transients": strategy["forbid_sharp_transients"],
        "forbid_high_freq_peaks": strategy["forbid_high_freq_peaks"],
        "forbid_percussive_hits": strategy["forbid_percussive_hits"],
        "prompt": result["prompt"],
    }


def build_cases() -> list[dict[str, Any]]:
    timestamp = datetime(2026, 5, 1, 12, 0, 0)
    raw_cases = [
        (
            "calm_baseline",
            StaticUserProfile(
                occupation="software_engineer",
                age=28,
                height_cm=180,
                baseline_heart_rate=65,
                chronic_stress_sources=["work_deadline"],
                music_preference="minimalist_ambient",
                therapy_goal="calm",
            ),
            AppleWatchBiometrics(
                timestamp=timestamp,
                heart_rate=72,
                heart_rate_variability=72.0,
                respiratory_rate=13,
                environmental_audio_exposure=42.0,
                body_motion={"x": 0.02, "y": 0.02, "z": 0.01},
                wrist_temperature=36.5,
                blood_oxygen=98.0,
                sleep_stage="awake",
            ),
        ),
        (
            "high_arousal_noise",
            StaticUserProfile(
                occupation="teacher",
                age=45,
                height_cm=170,
                baseline_heart_rate=68,
                chronic_stress_sources=["teaching_load", "research_pressure"],
                music_preference="ambient_classical",
                sound_sensitivity="high",
                preferred_density="low",
                therapy_goal="grounding",
            ),
            AppleWatchBiometrics(
                timestamp=timestamp,
                heart_rate=118,
                heart_rate_variability=18.0,
                respiratory_rate=24,
                environmental_audio_exposure=82.0,
                body_motion={"x": 0.45, "y": 0.30, "z": 0.20},
                wrist_temperature=37.1,
                blood_oxygen=96.0,
                sleep_stage="awake",
            ),
        ),
        (
            "sleep_sensitive",
            StaticUserProfile(
                occupation="retiree",
                age=62,
                height_cm=160,
                baseline_heart_rate=68,
                chronic_stress_sources=["sleep_quality"],
                music_preference="ambient_acoustic",
                sound_sensitivity="high",
                preferred_density="low",
                avoid_instruments=["drums", "piano"],
                therapy_goal="sleep",
            ),
            AppleWatchBiometrics(
                timestamp=timestamp,
                heart_rate=70,
                heart_rate_variability=35.0,
                respiratory_rate=14,
                environmental_audio_exposure=38.0,
                body_motion={"x": 0.03, "y": 0.02, "z": 0.01},
                wrist_temperature=36.2,
                blood_oxygen=97.0,
                sleep_stage="core",
            ),
        ),
    ]

    pipeline = MusicAIPipeline()
    cases: list[dict[str, Any]] = []
    for case_id, profile, biometrics in raw_cases:
        result = pipeline.run(profile, biometrics)
        cases.append(
            {
                "id": case_id,
                "profile": _profile_dict(profile),
                "biometrics": _biometrics_dict(biometrics),
                "expected": _expected(result),
            }
        )
    return cases


def main() -> None:
    cases = build_cases()
    payload = json.dumps(cases, indent=2, ensure_ascii=False) + "\n"

    for path in (PYTHON_FIXTURE, SWIFT_FIXTURE):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")

    print(f"Wrote {len(cases)} iOS parity cases")
    print(f"- {PYTHON_FIXTURE.relative_to(ROOT)}")
    print(f"- {SWIFT_FIXTURE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Generate fixtures**

Run:

```bash
python scripts/export_ios_parity_fixtures.py
```

Expected:

```text
Wrote 3 iOS parity cases
- tests/fixtures/ios_parity_cases.json
- ios/SomaCore/Tests/SomaCoreTests/Fixtures/ios_parity_cases.json
```

- [ ] **Step 5: Run the fixture test to verify it passes**

Run:

```bash
python -m pytest tests/test_ios_parity_fixtures.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Commit**

```bash
git add scripts/export_ios_parity_fixtures.py tests/fixtures/ios_parity_cases.json tests/test_ios_parity_fixtures.py ios/SomaCore/Tests/SomaCoreTests/Fixtures/ios_parity_cases.json
git commit -m "test: add iOS parity fixtures"
```

---

### Task 3: Create SomaCore Swift Models

**Files:**
- Create: `ios/SomaCore/Package.swift`
- Create: `ios/SomaCore/Sources/SomaCore/Models.swift`
- Create: `ios/SomaCore/Sources/SomaCore/SystemConfig.swift`
- Create: `ios/SomaCore/Tests/SomaCoreTests/ModelsTests.swift`
- Test: Swift package tests

- [ ] **Step 1: Write Swift model tests first**

Create `ios/SomaCore/Tests/SomaCoreTests/ModelsTests.swift`:

```swift
import XCTest
@testable import SomaCore

final class ModelsTests: XCTestCase {
    func testBiometricsValidationRejectsImpossibleHeartRate() {
        let biometrics = AppleWatchBiometrics(
            timestamp: Date(timeIntervalSince1970: 0),
            heartRate: 10,
            heartRateVariability: 35.5,
            respiratoryRate: 18,
            environmentalAudioExposure: 68,
            bodyMotion: ["x": 0.0, "y": 0.0, "z": 0.0],
            wristTemperature: nil,
            bloodOxygen: nil,
            sleepStage: nil
        )

        XCTAssertEqual(
            biometrics.validationErrors(),
            ["heart_rate value 10.0 is outside valid range [30.0, 200.0]"]
        )
    }

    func testProfileRoundTripsThroughJSON() throws {
        let profile = StaticUserProfile(
            occupation: "software_engineer",
            age: 28,
            heightCM: 180,
            baselineHeartRate: 65,
            chronicStressSources: ["work_deadline"],
            musicPreference: "minimalist_ambient",
            soundSensitivity: "normal",
            preferredDensity: "medium",
            avoidInstruments: [],
            therapyGoal: "calm"
        )

        let data = try JSONEncoder().encode(profile)
        let decoded = try JSONDecoder().decode(StaticUserProfile.self, from: data)

        XCTAssertEqual(decoded.occupation, "software_engineer")
        XCTAssertEqual(decoded.baselineHeartRate, 65)
        XCTAssertEqual(decoded.chronicStressSources, ["work_deadline"])
    }
}
```

- [ ] **Step 2: Run Swift tests to verify they fail**

Run:

```bash
cd ios/SomaCore && swift test
```

Expected:

```text
error: Could not find Package.swift
```

- [ ] **Step 3: Create the Swift package manifest**

Create `ios/SomaCore/Package.swift`:

```swift
// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "SomaCore",
    platforms: [
        .iOS(.v16),
        .macOS(.v13)
    ],
    products: [
        .library(name: "SomaCore", targets: ["SomaCore"])
    ],
    targets: [
        .target(name: "SomaCore"),
        .testTarget(
            name: "SomaCoreTests",
            dependencies: ["SomaCore"],
            resources: [.process("Fixtures")]
        )
    ]
)
```

- [ ] **Step 4: Create Swift system config**

Create `ios/SomaCore/Sources/SomaCore/SystemConfig.swift`:

```swift
import Foundation

public struct SystemConfig: Equatable, Sendable {
    public var minBPM: Int
    public var maxBPM: Int
    public var rhythmReductionPct: Double
    public var arousalExtraBPMReductionMax: Double
    public var hrvSafetyThreshold: Double
    public var maxNoiseDB: Double
    public var respiratoryElevatedThreshold: Double
    public var hrLoadRefDeltaBPM: Double
    public var hrvCalmRefMS: Double
    public var respCalmBRMin: Double
    public var respStressBRMin: Double
    public var noiseCalmDB: Double
    public var noiseStressDB: Double
    public var motionCalmG: Double
    public var motionStressG: Double
    public var arousalWeightHR: Double
    public var arousalWeightHRV: Double
    public var arousalWeightResp: Double
    public var arousalWeightNoise: Double
    public var arousalWeightMotion: Double
    public var arousalLowMax: Double
    public var arousalModerateMax: Double
    public var maskingEnterArousal: Double
    public var maskingExitArousal: Double
    public var maskingEnterConsecutiveSamples: Int
    public var maskingExitConsecutiveSamples: Int
    public var noiseForbidEnterDB: Double
    public var noiseForbidExitDB: Double
    public var noiseForbidEnterConsecutiveSamples: Int
    public var noiseForbidExitConsecutiveSamples: Int
    public var sympatheticLoadModerateBPM: Double
    public var sympatheticLoadHighBPM: Double
    public var hrSmoothingWindow: Int
    public var temporalHistoryMaxlen: Int

    public init(
        minBPM: Int = 45,
        maxBPM: Int = 140,
        rhythmReductionPct: Double = 15.0,
        arousalExtraBPMReductionMax: Double = 8.0,
        hrvSafetyThreshold: Double = 40.0,
        maxNoiseDB: Double = 70.0,
        respiratoryElevatedThreshold: Double = 18.0,
        hrLoadRefDeltaBPM: Double = 40.0,
        hrvCalmRefMS: Double = 80.0,
        respCalmBRMin: Double = 12.0,
        respStressBRMin: Double = 26.0,
        noiseCalmDB: Double = 45.0,
        noiseStressDB: Double = 85.0,
        motionCalmG: Double = 0.08,
        motionStressG: Double = 1.2,
        arousalWeightHR: Double = 0.35,
        arousalWeightHRV: Double = 0.30,
        arousalWeightResp: Double = 0.20,
        arousalWeightNoise: Double = 0.10,
        arousalWeightMotion: Double = 0.05,
        arousalLowMax: Double = 31.0,
        arousalModerateMax: Double = 66.0,
        maskingEnterArousal: Double = 58.0,
        maskingExitArousal: Double = 48.0,
        maskingEnterConsecutiveSamples: Int = 2,
        maskingExitConsecutiveSamples: Int = 2,
        noiseForbidEnterDB: Double = 72.0,
        noiseForbidExitDB: Double = 66.0,
        noiseForbidEnterConsecutiveSamples: Int = 2,
        noiseForbidExitConsecutiveSamples: Int = 2,
        sympatheticLoadModerateBPM: Double = 10.0,
        sympatheticLoadHighBPM: Double = 20.0,
        hrSmoothingWindow: Int = 5,
        temporalHistoryMaxlen: Int = 12
    ) {
        self.minBPM = minBPM
        self.maxBPM = maxBPM
        self.rhythmReductionPct = rhythmReductionPct
        self.arousalExtraBPMReductionMax = arousalExtraBPMReductionMax
        self.hrvSafetyThreshold = hrvSafetyThreshold
        self.maxNoiseDB = maxNoiseDB
        self.respiratoryElevatedThreshold = respiratoryElevatedThreshold
        self.hrLoadRefDeltaBPM = hrLoadRefDeltaBPM
        self.hrvCalmRefMS = hrvCalmRefMS
        self.respCalmBRMin = respCalmBRMin
        self.respStressBRMin = respStressBRMin
        self.noiseCalmDB = noiseCalmDB
        self.noiseStressDB = noiseStressDB
        self.motionCalmG = motionCalmG
        self.motionStressG = motionStressG
        self.arousalWeightHR = arousalWeightHR
        self.arousalWeightHRV = arousalWeightHRV
        self.arousalWeightResp = arousalWeightResp
        self.arousalWeightNoise = arousalWeightNoise
        self.arousalWeightMotion = arousalWeightMotion
        self.arousalLowMax = arousalLowMax
        self.arousalModerateMax = arousalModerateMax
        self.maskingEnterArousal = maskingEnterArousal
        self.maskingExitArousal = maskingExitArousal
        self.maskingEnterConsecutiveSamples = maskingEnterConsecutiveSamples
        self.maskingExitConsecutiveSamples = maskingExitConsecutiveSamples
        self.noiseForbidEnterDB = noiseForbidEnterDB
        self.noiseForbidExitDB = noiseForbidExitDB
        self.noiseForbidEnterConsecutiveSamples = noiseForbidEnterConsecutiveSamples
        self.noiseForbidExitConsecutiveSamples = noiseForbidExitConsecutiveSamples
        self.sympatheticLoadModerateBPM = sympatheticLoadModerateBPM
        self.sympatheticLoadHighBPM = sympatheticLoadHighBPM
        self.hrSmoothingWindow = hrSmoothingWindow
        self.temporalHistoryMaxlen = temporalHistoryMaxlen
    }
}
```

- [ ] **Step 5: Create Swift models**

Create `ios/SomaCore/Sources/SomaCore/Models.swift`:

```swift
import Foundation

public struct StaticUserProfile: Codable, Equatable, Sendable {
    public var occupation: String
    public var age: Int
    public var heightCM: Double
    public var baselineHeartRate: Int
    public var chronicStressSources: [String]
    public var musicPreference: String
    public var soundSensitivity: String
    public var preferredDensity: String
    public var avoidInstruments: [String]
    public var therapyGoal: String

    enum CodingKeys: String, CodingKey {
        case occupation
        case age
        case heightCM = "height_cm"
        case baselineHeartRate = "baseline_heart_rate"
        case chronicStressSources = "chronic_stress_sources"
        case musicPreference = "music_preference"
        case soundSensitivity = "sound_sensitivity"
        case preferredDensity = "preferred_density"
        case avoidInstruments = "avoid_instruments"
        case therapyGoal = "therapy_goal"
    }

    public init(
        occupation: String,
        age: Int,
        heightCM: Double,
        baselineHeartRate: Int,
        chronicStressSources: [String] = [],
        musicPreference: String = "ambient",
        soundSensitivity: String = "normal",
        preferredDensity: String = "medium",
        avoidInstruments: [String] = [],
        therapyGoal: String = "calm"
    ) {
        self.occupation = occupation
        self.age = age
        self.heightCM = heightCM
        self.baselineHeartRate = baselineHeartRate
        self.chronicStressSources = chronicStressSources
        self.musicPreference = musicPreference
        self.soundSensitivity = soundSensitivity
        self.preferredDensity = preferredDensity
        self.avoidInstruments = avoidInstruments
        self.therapyGoal = therapyGoal
    }
}

public struct AppleWatchBiometrics: Codable, Equatable, Sendable {
    public var timestamp: Date
    public var heartRate: Int
    public var heartRateVariability: Double
    public var respiratoryRate: Int
    public var environmentalAudioExposure: Double
    public var bodyMotion: [String: Double]
    public var wristTemperature: Double?
    public var bloodOxygen: Double?
    public var sleepStage: String?

    enum CodingKeys: String, CodingKey {
        case timestamp
        case heartRate = "heart_rate"
        case heartRateVariability = "heart_rate_variability"
        case respiratoryRate = "respiratory_rate"
        case environmentalAudioExposure = "environmental_audio_exposure"
        case bodyMotion = "body_motion"
        case wristTemperature = "wrist_temperature"
        case bloodOxygen = "blood_oxygen"
        case sleepStage = "sleep_stage"
    }

    public init(
        timestamp: Date,
        heartRate: Int,
        heartRateVariability: Double,
        respiratoryRate: Int,
        environmentalAudioExposure: Double,
        bodyMotion: [String: Double],
        wristTemperature: Double? = nil,
        bloodOxygen: Double? = nil,
        sleepStage: String? = nil
    ) {
        self.timestamp = timestamp
        self.heartRate = heartRate
        self.heartRateVariability = heartRateVariability
        self.respiratoryRate = respiratoryRate
        self.environmentalAudioExposure = environmentalAudioExposure
        self.bodyMotion = bodyMotion
        self.wristTemperature = wristTemperature
        self.bloodOxygen = bloodOxygen
        self.sleepStage = sleepStage
    }

    public func validationErrors() -> [String] {
        var errors: [String] = []

        func check(_ field: String, _ value: Double, _ lower: Double, _ upper: Double) {
            if value < lower || value > upper {
                errors.append("\(field) value \(value) is outside valid range [\(lower), \(upper)]")
            }
        }

        check("heart_rate", Double(heartRate), 30, 200)
        check("heart_rate_variability", heartRateVariability, 5, 250)
        check("respiratory_rate", Double(respiratoryRate), 8, 30)
        check("environmental_audio", environmentalAudioExposure, 20, 130)

        if let wristTemperature {
            check("wrist_temperature", wristTemperature, 35, 42)
        }
        if let bloodOxygen {
            check("blood_oxygen", bloodOxygen, 85, 100)
        }

        return errors
    }
}

public struct BiometricFeatures: Codable, Equatable, Sendable {
    public var rawHR: Int
    public var smoothedHR: Double
    public var baselineHR: Int
    public var hrDeltaBPM: Double
    public var hrDeltaPct: Double
    public var hrvMS: Double
    public var respiratoryRate: Double
    public var ambientNoiseDB: Double
    public var motionMagnitudeG: Double
    public var hrLoadScore: Double
    public var hrvRiskScore: Double
    public var respiratoryLoadScore: Double
    public var noiseRiskScore: Double
    public var motionIntensityScore: Double
}

public struct PhysiologicalState: Codable, Equatable, Sendable {
    public var arousalScore: Double
    public var stressState: String
    public var recoveryPriority: String
    public var confidence: Double
    public var trend: String
    public var sympatheticLoadBPM: Double
}

public struct MusicStrategy: Codable, Equatable, Sendable {
    public var tempoBPM: Int
    public var genreStyle: String
    public var instrumentSet: [String]
    public var acousticTextureDescription: String
    public var emotionalAnchorDescription: String
    public var forbidSharpTransients: Bool
    public var forbidHighFreqPeaks: Bool
    public var forbidPercussiveHits: Bool
}

public struct ProcessedParams: Codable, Equatable, Sendable {
    public var features: BiometricFeatures
    public var state: PhysiologicalState
    public var musicStrategy: MusicStrategy
}
```

- [ ] **Step 6: Run Swift tests**

Run:

```bash
cd ios/SomaCore && swift test
```

Expected:

```text
Test Suite 'All tests' passed
```

- [ ] **Step 7: Commit**

```bash
git add ios/SomaCore/Package.swift ios/SomaCore/Sources/SomaCore/Models.swift ios/SomaCore/Sources/SomaCore/SystemConfig.swift ios/SomaCore/Tests/SomaCoreTests/ModelsTests.swift
git commit -m "feat: add SomaCore Swift models"
```

---

### Task 4: Port The Deterministic Biometric Processor

**Files:**
- Create: `ios/SomaCore/Sources/SomaCore/BiometricProcessor.swift`
- Create: `ios/SomaCore/Tests/SomaCoreTests/BiometricProcessorTests.swift`
- Test: Swift package tests

- [ ] **Step 1: Write failing processor tests**

Create `ios/SomaCore/Tests/SomaCoreTests/BiometricProcessorTests.swift`:

```swift
import XCTest
@testable import SomaCore

final class BiometricProcessorTests: XCTestCase {
    private func profile(avoid: [String] = [], therapyGoal: String = "calm") -> StaticUserProfile {
        StaticUserProfile(
            occupation: "software_engineer",
            age: 28,
            heightCM: 180,
            baselineHeartRate: 65,
            chronicStressSources: ["work_deadline"],
            musicPreference: "minimalist_ambient",
            soundSensitivity: "normal",
            preferredDensity: "medium",
            avoidInstruments: avoid,
            therapyGoal: therapyGoal
        )
    }

    private func biometrics(
        hr: Int = 80,
        hrv: Double = 50,
        resp: Int = 14,
        noise: Double = 50,
        motion: [String: Double] = ["x": 0.01, "y": 0.01, "z": 0.01]
    ) -> AppleWatchBiometrics {
        AppleWatchBiometrics(
            timestamp: Date(timeIntervalSince1970: 0),
            heartRate: hr,
            heartRateVariability: hrv,
            respiratoryRate: resp,
            environmentalAudioExposure: noise,
            bodyMotion: motion
        )
    }

    func testSmoothHeartRateDrivesTargetBPM() {
        var processor = BiometricProcessor(config: SystemConfig(hrSmoothingWindow: 3))

        _ = processor.process(profile: profile(), biometrics: biometrics(hr: 60))
        _ = processor.process(profile: profile(), biometrics: biometrics(hr: 60))
        let out = processor.process(profile: profile(), biometrics: biometrics(hr: 120))

        XCTAssertEqual(out.features.smoothedHR, 80, accuracy: 0.001)
        XCTAssertNotEqual(out.musicStrategy.tempoBPM, 102)
    }

    func testTargetBPMClampsToMinMax() {
        var processor = BiometricProcessor(config: SystemConfig(hrSmoothingWindow: 1, minBPM: 45, maxBPM: 140))

        XCTAssertEqual(processor.process(profile: profile(), biometrics: biometrics(hr: 195)).musicStrategy.tempoBPM, 140)
        XCTAssertEqual(processor.process(profile: profile(), biometrics: biometrics(hr: 40)).musicStrategy.tempoBPM, 45)
    }

    func testLowerHRVIncreasesArousal() {
        let calm = BiometricProcessor(config: SystemConfig(hrSmoothingWindow: 1))
            .process(profile: profile(), biometrics: biometrics(hrv: 90))
        let stressed = BiometricProcessor(config: SystemConfig(hrSmoothingWindow: 1))
            .process(profile: profile(), biometrics: biometrics(hrv: 15))

        XCTAssertGreaterThanOrEqual(stressed.state.arousalScore, calm.state.arousalScore)
    }

    func testAvoidInstrumentsFiltersStrategy() {
        let out = BiometricProcessor(config: SystemConfig(hrSmoothingWindow: 1))
            .process(profile: profile(avoid: ["piano"]), biometrics: biometrics(hr: 75, resp: 12))

        XCTAssertFalse(out.musicStrategy.instrumentSet.contains { $0.lowercased().contains("piano") })
    }

    func testNoiseSafeguardHysteresisRequiresTwoSamples() {
        var processor = BiometricProcessor(
            config: SystemConfig(
                hrSmoothingWindow: 1,
                noiseForbidEnterDB: 72,
                noiseForbidExitDB: 66,
                noiseForbidEnterConsecutiveSamples: 2,
                noiseForbidExitConsecutiveSamples: 2
            )
        )

        let first = processor.process(profile: profile(), biometrics: biometrics(noise: 80))
        let second = processor.process(profile: profile(), biometrics: biometrics(noise: 80))

        XCTAssertFalse(first.musicStrategy.forbidSharpTransients)
        XCTAssertTrue(second.musicStrategy.forbidSharpTransients)
    }
}
```

- [ ] **Step 2: Run processor tests to verify they fail**

Run:

```bash
cd ios/SomaCore && swift test --filter BiometricProcessorTests
```

Expected:

```text
cannot find 'BiometricProcessor' in scope
```

- [ ] **Step 3: Implement the processor**

Create `ios/SomaCore/Sources/SomaCore/BiometricProcessor.swift`:

```swift
import Foundation

public struct BiometricProcessor: Sendable {
    public var config: SystemConfig
    private var hrHistory: [Double] = []
    private var arousalHistory: [Double] = []
    private var strongMaskingLatched = false
    private var maskEnterStreak = 0
    private var maskExitStreak = 0
    private var noiseForbidLatched = false
    private var noiseEnterStreak = 0
    private var noiseExitStreak = 0

    public init(config: SystemConfig = SystemConfig()) {
        self.config = config
    }

    public mutating func process(
        profile: StaticUserProfile,
        biometrics: AppleWatchBiometrics,
        validationErrors: [String] = []
    ) -> ProcessedParams {
        let smoothedHR = smoothHeartRate(Double(biometrics.heartRate))
        let motion = motionMagnitude(biometrics.bodyMotion)
        let scores = componentScores(
            smoothedHR: smoothedHR,
            baselineHR: profile.baselineHeartRate,
            hrvMS: biometrics.heartRateVariability,
            respRate: Double(biometrics.respiratoryRate),
            noiseDB: biometrics.environmentalAudioExposure,
            motionMagnitude: motion
        )

        let trend = updateArousalTrend(scores.arousal)
        updateMaskingLatch(arousal: scores.arousal)
        updateNoiseForbidLatch(noiseDB: biometrics.environmentalAudioExposure)

        let stressState = stressBand(scores.arousal)
        let recoveryPriority = recoveryPriority(profile: profile, arousal: scores.arousal, stressState: stressState)
        let target = smoothedHR * (1 - config.rhythmReductionPct / 100)
            - (scores.arousal / 100) * config.arousalExtraBPMReductionMax
        let tempo = Int(clamp(round(target), Double(config.minBPM), Double(config.maxBPM)))
        let maskingStrength = clamp((scores.hrvRisk * 0.55 + scores.arousal * 0.45) / 100, 0, 1)

        let features = BiometricFeatures(
            rawHR: biometrics.heartRate,
            smoothedHR: smoothedHR,
            baselineHR: profile.baselineHeartRate,
            hrDeltaBPM: scores.hrDelta,
            hrDeltaPct: scores.hrDeltaPct,
            hrvMS: biometrics.heartRateVariability,
            respiratoryRate: Double(biometrics.respiratoryRate),
            ambientNoiseDB: biometrics.environmentalAudioExposure,
            motionMagnitudeG: motion,
            hrLoadScore: scores.hrLoad,
            hrvRiskScore: scores.hrvRisk,
            respiratoryLoadScore: scores.respLoad,
            noiseRiskScore: scores.noiseRisk,
            motionIntensityScore: scores.motionScore
        )

        let state = PhysiologicalState(
            arousalScore: scores.arousal,
            stressState: stressState,
            recoveryPriority: recoveryPriority,
            confidence: clamp(1.0 - 0.06 * Double(validationErrors.count), 0.5, 1.0),
            trend: trend,
            sympatheticLoadBPM: scores.hrDelta
        )

        let strategy = MusicStrategy(
            tempoBPM: tempo,
            genreStyle: resolveGenreStyle(profile),
            instrumentSet: selectInstruments(respLoadScore: scores.respLoad, avoid: profile.avoidInstruments),
            acousticTextureDescription: textureDescription(maskingStrength: maskingStrength),
            emotionalAnchorDescription: emotionalAnchor(profile: profile, sympatheticLoad: scores.hrDelta, recoveryPriority: recoveryPriority),
            forbidSharpTransients: noiseForbidLatched,
            forbidHighFreqPeaks: noiseForbidLatched,
            forbidPercussiveHits: noiseForbidLatched || strongMaskingLatched
        )

        return ProcessedParams(features: features, state: state, musicStrategy: strategy)
    }

    private mutating func smoothHeartRate(_ currentHR: Double) -> Double {
        hrHistory.append(currentHR)
        if hrHistory.count > config.hrSmoothingWindow {
            hrHistory.removeFirst()
        }
        return hrHistory.reduce(0, +) / Double(hrHistory.count)
    }

    private func motionMagnitude(_ bodyMotion: [String: Double]) -> Double {
        let x = bodyMotion["x"] ?? 0
        let y = bodyMotion["y"] ?? 0
        let z = bodyMotion["z"] ?? 0
        return sqrt(x * x + y * y + z * z)
    }

    private func componentScores(
        smoothedHR: Double,
        baselineHR: Int,
        hrvMS: Double,
        respRate: Double,
        noiseDB: Double,
        motionMagnitude: Double
    ) -> (hrDelta: Double, hrDeltaPct: Double, hrLoad: Double, hrvRisk: Double, respLoad: Double, noiseRisk: Double, motionScore: Double, arousal: Double) {
        let safeBase = max(Double(baselineHR), 1)
        let hrDelta = smoothedHR - Double(baselineHR)
        let hrDeltaPct = 100 * hrDelta / safeBase
        let hrLoad = linearScore(hrDelta, 0, config.hrLoadRefDeltaBPM)
        let hrvRisk = 100 - linearScore(
            hrvMS,
            max(5, config.hrvSafetyThreshold * 0.35),
            max(config.hrvCalmRefMS, config.hrvSafetyThreshold + 5)
        )
        let respLoad = linearScore(
            respRate,
            config.respCalmBRMin,
            max(config.respStressBRMin, config.respiratoryElevatedThreshold + 2)
        )
        let noiseRisk = linearScore(
            noiseDB,
            config.noiseCalmDB,
            max(config.noiseStressDB, config.maxNoiseDB + 10)
        )
        let motionScore = linearScore(
            motionMagnitude,
            config.motionCalmG,
            max(config.motionStressG, config.motionCalmG + 0.05)
        )

        let weightSum = config.arousalWeightHR + config.arousalWeightHRV + config.arousalWeightResp + config.arousalWeightNoise + config.arousalWeightMotion
        let weights = weightSum <= 0
            ? (0.2, 0.2, 0.2, 0.2, 0.2)
            : (
                config.arousalWeightHR / weightSum,
                config.arousalWeightHRV / weightSum,
                config.arousalWeightResp / weightSum,
                config.arousalWeightNoise / weightSum,
                config.arousalWeightMotion / weightSum
            )
        let arousal = clamp(
            weights.0 * hrLoad + weights.1 * hrvRisk + weights.2 * respLoad + weights.3 * noiseRisk + weights.4 * motionScore,
            0,
            100
        )

        return (hrDelta, hrDeltaPct, hrLoad, hrvRisk, respLoad, noiseRisk, motionScore, arousal)
    }

    private mutating func updateArousalTrend(_ arousal: Double) -> String {
        arousalHistory.append(arousal)
        let maxCount = max(4, config.temporalHistoryMaxlen)
        if arousalHistory.count > maxCount {
            arousalHistory.removeFirst(arousalHistory.count - maxCount)
        }
        if arousalHistory.count < 4 {
            return "stable"
        }
        let older = average(Array(arousalHistory.suffix(4).prefix(2)))
        let recent = average(Array(arousalHistory.suffix(2)))
        if recent < older - 3 {
            return "improving"
        }
        if recent > older + 3 {
            return "worsening"
        }
        return "stable"
    }

    private mutating func updateMaskingLatch(arousal: Double) {
        if arousal >= config.maskingEnterArousal {
            maskEnterStreak += 1
            maskExitStreak = 0
        } else if arousal <= config.maskingExitArousal {
            maskExitStreak += 1
            maskEnterStreak = 0
        } else {
            maskEnterStreak = 0
            maskExitStreak = 0
        }

        if !strongMaskingLatched && maskEnterStreak >= config.maskingEnterConsecutiveSamples {
            strongMaskingLatched = true
        }
        if strongMaskingLatched && maskExitStreak >= config.maskingExitConsecutiveSamples {
            strongMaskingLatched = false
        }
    }

    private mutating func updateNoiseForbidLatch(noiseDB: Double) {
        if noiseDB >= config.noiseForbidEnterDB {
            noiseEnterStreak += 1
            noiseExitStreak = 0
        } else if noiseDB <= config.noiseForbidExitDB {
            noiseExitStreak += 1
            noiseEnterStreak = 0
        } else {
            noiseEnterStreak = 0
            noiseExitStreak = 0
        }

        if !noiseForbidLatched && noiseEnterStreak >= config.noiseForbidEnterConsecutiveSamples {
            noiseForbidLatched = true
        }
        if noiseForbidLatched && noiseExitStreak >= config.noiseForbidExitConsecutiveSamples {
            noiseForbidLatched = false
        }
    }

    private func stressBand(_ arousal: Double) -> String {
        if arousal <= config.arousalLowMax {
            return "low"
        }
        if arousal <= config.arousalModerateMax {
            return "moderate"
        }
        return "high"
    }

    private func recoveryPriority(profile: StaticUserProfile, arousal: Double, stressState: String) -> String {
        if arousal >= config.arousalModerateMax {
            return "grounding"
        }
        let goal = profile.therapyGoal.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        if goal == "sleep" {
            return "sleep"
        }
        if goal == "grounding" {
            return "grounding"
        }
        if goal == "focus" && stressState == "low" {
            return "focus"
        }
        return "calm"
    }

    private func resolveGenreStyle(_ profile: StaticUserProfile) -> String {
        var parts = ["ambient therapeutic instrumental, soft harmonic movement, no vocals"]
        let preference = profile.musicPreference.lowercased()
        if preference.contains("minimalist") {
            parts.append("ultra-minimal arrangement, generous negative space, low melodic density")
        } else if preference.contains("ambient") {
            parts.append("warm ambient harmonic bed with slow-evolving textures")
        }
        if preference.contains("electronic") {
            parts.append("soft electronic timbres and sine-like tones without percussive attacks")
        }
        if preference.contains("classical") || preference.contains("acoustic") {
            parts.append("organic acoustic instruments with natural decay tails")
        }
        if profile.soundSensitivity.lowercased() == "high" {
            parts.append("gentle dynamics and conservative loudness peaks for sound-sensitive listeners")
        }
        if profile.preferredDensity.lowercased() == "low" {
            parts.append("very sparse layering and breathable sonic gaps")
        }
        return parts.joined(separator: "; ")
    }

    private func selectInstruments(respLoadScore: Double, avoid: [String]) -> [String] {
        let chosen: [String]
        if respLoadScore >= 58 {
            chosen = ["cello_legato", "sustained_synth"]
        } else if respLoadScore >= 32 {
            chosen = ["piano", "ambient_strings", "soft_synth_pad"]
        } else {
            chosen = ["piano", "ambient_strings"]
        }

        let loweredAvoid = avoid.map { $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() }.filter { !$0.isEmpty }
        let filtered = chosen.filter { instrument in
            let lowered = instrument.lowercased()
            return !loweredAvoid.contains { lowered.contains($0) || $0.contains(lowered) }
        }
        return filtered.isEmpty ? ["soft_synth_pad"] : filtered
    }

    private func textureDescription(maskingStrength: Double) -> String {
        let pink = maskingStrength >= 0.38
        let pad = maskingStrength >= 0.28
        if pink && pad {
            return "pink noise broadband masking foundation (1/f spectrum for threat isolation); continuous synthesizer pad (seamless harmonic grounding)"
        }
        if pad {
            return "continuous warm pad layer with soft attack and long release"
        }
        return "open ambient space with gentle decay and low density"
    }

    private func emotionalAnchor(profile: StaticUserProfile, sympatheticLoad: Double, recoveryPriority: String) -> String {
        let source = profile.chronicStressSources.first.map { " linked to \($0)" } ?? ""
        if sympatheticLoad >= config.sympatheticLoadHighBPM {
            return "deep grounding and safety restoration\(source), reduce physiological urgency without dramatic change"
        }
        if sympatheticLoad >= config.sympatheticLoadModerateBPM {
            return "steady downshift toward calm regulation\(source), supportive and contained"
        }
        return "maintain \(recoveryPriority) with stable reassurance\(source)"
    }

    private func linearScore(_ value: Double, _ lower: Double, _ upper: Double) -> Double {
        if upper <= lower {
            return 0
        }
        return clamp((value - lower) / (upper - lower) * 100, 0, 100)
    }

    private func clamp(_ value: Double, _ lower: Double, _ upper: Double) -> Double {
        max(lower, min(upper, value))
    }

    private func average(_ values: [Double]) -> Double {
        values.reduce(0, +) / Double(values.count)
    }
}
```

- [ ] **Step 4: Run processor tests**

Run:

```bash
cd ios/SomaCore && swift test --filter BiometricProcessorTests
```

Expected:

```text
Test Suite 'BiometricProcessorTests' passed
```

- [ ] **Step 5: Commit**

```bash
git add ios/SomaCore/Sources/SomaCore/BiometricProcessor.swift ios/SomaCore/Tests/SomaCoreTests/BiometricProcessorTests.swift
git commit -m "feat: port biometric processor to Swift"
```

---

### Task 5: Port The Music Prompt Compiler

**Files:**
- Create: `ios/SomaCore/Sources/SomaCore/MusicPromptCompiler.swift`
- Create: `ios/SomaCore/Tests/SomaCoreTests/MusicPromptCompilerTests.swift`
- Test: Swift package tests

- [ ] **Step 1: Write failing prompt compiler tests**

Create `ios/SomaCore/Tests/SomaCoreTests/MusicPromptCompilerTests.swift`:

```swift
import XCTest
@testable import SomaCore

final class MusicPromptCompilerTests: XCTestCase {
    func testCompileBuildsSevenSegmentPrompt() {
        let processed = ProcessedParams(
            features: BiometricFeatures(
                rawHR: 80,
                smoothedHR: 80,
                baselineHR: 65,
                hrDeltaBPM: 15,
                hrDeltaPct: 23.07,
                hrvMS: 50,
                respiratoryRate: 14,
                ambientNoiseDB: 50,
                motionMagnitudeG: 0.02,
                hrLoadScore: 37.5,
                hrvRiskScore: 45,
                respiratoryLoadScore: 10,
                noiseRiskScore: 12.5,
                motionIntensityScore: 0
            ),
            state: PhysiologicalState(
                arousalScore: 32.5,
                stressState: "moderate",
                recoveryPriority: "calm",
                confidence: 1,
                trend: "stable",
                sympatheticLoadBPM: 15
            ),
            musicStrategy: MusicStrategy(
                tempoBPM: 68,
                genreStyle: "warm ambient harmonic bed",
                instrumentSet: ["piano", "ambient_strings"],
                acousticTextureDescription: "open ambient space",
                emotionalAnchorDescription: "steady downshift toward calm regulation",
                forbidSharpTransients: false,
                forbidHighFreqPeaks: false,
                forbidPercussiveHits: false
            )
        )

        let result = MusicPromptCompiler().compile(processed)

        XCTAssertTrue(result.prompt.contains("Pure instrumental music"))
        XCTAssertTrue(result.prompt.contains("Tempo 68 BPM"))
        XCTAssertTrue(result.prompt.contains("Instruments: piano, ambient_strings"))
        XCTAssertEqual(result.metadata.targetBPM, 68)
        XCTAssertEqual(result.metadata.stressState, "moderate")
    }
}
```

- [ ] **Step 2: Run prompt compiler tests to verify they fail**

Run:

```bash
cd ios/SomaCore && swift test --filter MusicPromptCompilerTests
```

Expected:

```text
cannot find 'MusicPromptCompiler' in scope
```

- [ ] **Step 3: Implement the prompt compiler**

Create `ios/SomaCore/Sources/SomaCore/MusicPromptCompiler.swift`:

```swift
import Foundation

public struct CompiledPrompt: Codable, Equatable, Sendable {
    public var prompt: String
    public var segments: [String: String]
    public var metadata: PromptMetadata
}

public struct PromptMetadata: Codable, Equatable, Sendable {
    public var promptLengthChars: Int
    public var promptLengthTokensEstimate: Int
    public var targetBPM: Int
    public var sympatheticLoad: Double
    public var arousalScore: Double
    public var stressState: String
    public var recoveryPriority: String
    public var confidence: Double
    public var trend: String
    public var validationStatus: String
}

public struct MusicPromptCompiler: Sendable {
    public var config: SystemConfig

    public init(config: SystemConfig = SystemConfig()) {
        self.config = config
    }

    public func compile(_ processed: ProcessedParams) -> CompiledPrompt {
        let strategy = processed.musicStrategy
        let segments = buildSegments(strategy)
        let orderedKeys = [
            "music_type",
            "genre",
            "tempo",
            "instruments",
            "texture",
            "emotional_anchor",
            "constraints"
        ]
        let prompt = orderedKeys.compactMap { segments[$0] }.joined(separator: " | ")
        let tokenEstimate = Int(Double(prompt.split(separator: " ").count) * 1.3)
        let metadata = PromptMetadata(
            promptLengthChars: prompt.count,
            promptLengthTokensEstimate: tokenEstimate,
            targetBPM: strategy.tempoBPM,
            sympatheticLoad: processed.state.sympatheticLoadBPM,
            arousalScore: processed.state.arousalScore,
            stressState: processed.state.stressState,
            recoveryPriority: processed.state.recoveryPriority,
            confidence: processed.state.confidence,
            trend: processed.state.trend,
            validationStatus: prompt.count < 2000 ? "pass" : "warning"
        )
        return CompiledPrompt(prompt: prompt, segments: segments, metadata: metadata)
    }

    private func buildSegments(_ strategy: MusicStrategy) -> [String: String] {
        [
            "music_type": "Pure instrumental music, generative and continuous",
            "genre": strategy.genreStyle,
            "tempo": "Tempo \(min(config.maxBPM, max(config.minBPM, strategy.tempoBPM))) BPM",
            "instruments": "Instruments: \(strategy.instrumentSet.joined(separator: ", "))",
            "texture": "Acoustic texture: \(strategy.acousticTextureDescription)",
            "emotional_anchor": "Emotional anchor: \(strategy.emotionalAnchorDescription)",
            "constraints": constraints(strategy)
        ]
    }

    private func constraints(_ strategy: MusicStrategy) -> String {
        var items: [String] = []
        if strategy.forbidSharpTransients {
            items.append("FORBIDDEN: Sharp transient attacks or sudden envelope spikes (startle trigger prevention)")
        }
        if strategy.forbidHighFreqPeaks {
            items.append("FORBIDDEN: High-frequency peaks above 8 kHz (environmental noise summation prevents masking)")
        }
        if strategy.forbidPercussiveHits {
            items.append("FORBIDDEN: Percussive hits, drums, or impact sounds (sudden acoustic threats)")
        }
        items.append("FORBIDDEN: Sudden volume jumps or dynamic compression artifacts")
        items.append("FORBIDDEN: Dissonant intervals or tonal instability (harmonic threat detection)")
        return "Strict negative constraints: " + items.joined(separator: "; ")
    }
}
```

- [ ] **Step 4: Run prompt compiler tests**

Run:

```bash
cd ios/SomaCore && swift test --filter MusicPromptCompilerTests
```

Expected:

```text
Test Suite 'MusicPromptCompilerTests' passed
```

- [ ] **Step 5: Commit**

```bash
git add ios/SomaCore/Sources/SomaCore/MusicPromptCompiler.swift ios/SomaCore/Tests/SomaCoreTests/MusicPromptCompilerTests.swift
git commit -m "feat: port music prompt compiler to Swift"
```

---

### Task 6: Add Swift Parity Tests Against Python Fixtures

**Files:**
- Modify: `ios/SomaCore/Package.swift`
- Create: `ios/SomaCore/Tests/SomaCoreTests/ParityFixtureTests.swift`
- Test: Swift package tests and Python fixture export

- [ ] **Step 1: Confirm fixture resource is declared**

Ensure `ios/SomaCore/Package.swift` contains this test target:

```swift
.testTarget(
    name: "SomaCoreTests",
    dependencies: ["SomaCore"],
    resources: [.process("Fixtures")]
)
```

- [ ] **Step 2: Write failing parity test**

Create `ios/SomaCore/Tests/SomaCoreTests/ParityFixtureTests.swift`:

```swift
import XCTest
@testable import SomaCore

private struct ParityCase: Decodable {
    struct Expected: Decodable {
        var targetBPM: Int
        var arousalScore: Double
        var stressState: String
        var recoveryPriority: String
        var instrumentSet: [String]
        var prompt: String

        enum CodingKeys: String, CodingKey {
            case targetBPM = "target_bpm"
            case arousalScore = "arousal_score"
            case stressState = "stress_state"
            case recoveryPriority = "recovery_priority"
            case instrumentSet = "instrument_set"
            case prompt
        }
    }

    var id: String
    var profile: StaticUserProfile
    var biometrics: AppleWatchBiometrics
    var expected: Expected
}

final class ParityFixtureTests: XCTestCase {
    func testSwiftCoreMatchesPythonParityFixtures() throws {
        let url = Bundle.module.url(forResource: "ios_parity_cases", withExtension: "json")
        XCTAssertNotNil(url)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let data = try Data(contentsOf: try XCTUnwrap(url))
        let cases = try decoder.decode([ParityCase].self, from: data)

        XCTAssertEqual(cases.count, 3)

        for fixture in cases {
            var processor = BiometricProcessor(config: SystemConfig())
            let processed = processor.process(profile: fixture.profile, biometrics: fixture.biometrics)
            let compiled = MusicPromptCompiler().compile(processed)

            XCTAssertEqual(
                processed.musicStrategy.tempoBPM,
                fixture.expected.targetBPM,
                "target BPM mismatch for \(fixture.id)"
            )
            XCTAssertEqual(
                processed.state.arousalScore,
                fixture.expected.arousalScore,
                accuracy: 0.05,
                "arousal mismatch for \(fixture.id)"
            )
            XCTAssertEqual(processed.state.stressState, fixture.expected.stressState)
            XCTAssertEqual(processed.state.recoveryPriority, fixture.expected.recoveryPriority)
            XCTAssertEqual(processed.musicStrategy.instrumentSet, fixture.expected.instrumentSet)
            XCTAssertEqual(compiled.prompt, fixture.expected.prompt)
        }
    }
}
```

- [ ] **Step 3: Run parity tests to verify current mismatch**

Run:

```bash
cd ios/SomaCore && swift test --filter ParityFixtureTests
```

Expected first run:

```text
XCTAssertEqual failed
```

This failure is expected if Swift text constants differ from Python `style_maps.py` or if the Swift processor is still missing a Python branch.

- [ ] **Step 4: Align Swift constants with Python outputs**

Read these Python files and copy the exact production strings into Swift:

```text
music_ai_module/style_maps.py
music_ai_module/processor.py
music_ai_module/compiler.py
```

Update only:

```text
ios/SomaCore/Sources/SomaCore/BiometricProcessor.swift
ios/SomaCore/Sources/SomaCore/MusicPromptCompiler.swift
```

The target is exact equality for:

```text
processed.musicStrategy.tempoBPM
processed.state.arousalScore within 0.05
processed.state.stressState
processed.state.recoveryPriority
processed.musicStrategy.instrumentSet
compiled.prompt
```

- [ ] **Step 5: Regenerate fixtures and run both test suites**

Run:

```bash
python scripts/export_ios_parity_fixtures.py
python -m pytest tests/test_ios_parity_fixtures.py -q
cd ios/SomaCore && swift test
```

Expected:

```text
Wrote 3 iOS parity cases
1 passed
Test Suite 'All tests' passed
```

- [ ] **Step 6: Commit**

```bash
git add ios/SomaCore/Sources/SomaCore/BiometricProcessor.swift ios/SomaCore/Sources/SomaCore/MusicPromptCompiler.swift ios/SomaCore/Tests/SomaCoreTests/ParityFixtureTests.swift ios/SomaCore/Tests/SomaCoreTests/Fixtures/ios_parity_cases.json
git commit -m "test: verify Swift core against Python fixtures"
```

---

### Task 7: Add Migration Readiness Documentation

**Files:**
- Modify: `README.md`
- Create: `ios/README.md`
- Test: Python and Swift tests

- [ ] **Step 1: Add iOS workspace README**

Create `ios/README.md`:

```markdown
# Soma iOS Workspace

This folder contains native iOS migration work.

## Current Package

- `SomaCore`: Swift Package that ports the deterministic Python Layer 1 to Layer 3 pipeline.

## Run Tests

```bash
cd ios/SomaCore
swift test
```

## Refresh Python Parity Fixtures

```bash
python scripts/export_ios_parity_fixtures.py
python -m pytest tests/test_ios_parity_fixtures.py -q
cd ios/SomaCore && swift test --filter ParityFixtureTests
```

## Boundaries

- The iOS app may run `SomaCore` locally.
- The iOS app must not embed Suno or OpenAI API keys.
- Suno generation, LLM verification, and GraphRAG clinical audit belong behind a backend API.
- HealthKit data access belongs in the iOS app layer, not in `SomaCore`.
```

- [ ] **Step 2: Add README repository structure lines**

Modify the repository structure block in `README.md` so the `MindWave/` tree includes:

```markdown
├── ios/
│   ├── README.md              # Native iOS migration notes
│   └── SomaCore/              # Swift Package mirroring deterministic Layer 1-3 pipeline
```

Add this short section after the existing Python module smoke test:

```markdown
### iOS Migration Foundation

The native iOS migration starts with `ios/SomaCore`, a Swift Package that mirrors the deterministic Python Layer 1-3 pipeline. Refresh parity fixtures from Python before changing Swift behavior:

```bash
python scripts/export_ios_parity_fixtures.py
python -m pytest tests/test_ios_parity_fixtures.py -q
cd ios/SomaCore && swift test
```

Suno generation, LLM verification, and GraphRAG clinical audit should stay behind a backend API so third-party keys and clinical audit workflows are not bundled into the iOS app.
```

- [ ] **Step 3: Run full verification**

Run:

```bash
python -m pytest tests -q
cd ios/SomaCore && swift test
```

Expected:

```text
all Python tests pass
Test Suite 'All tests' passed
```

- [ ] **Step 4: Commit**

```bash
git add README.md ios/README.md
git commit -m "docs: add iOS migration quick start"
```

---

## Completion Criteria

- `docs/ios-migration-architecture.md` explains target boundaries and secret handling.
- `scripts/export_ios_parity_fixtures.py` generates fixtures for Python and Swift tests.
- `tests/test_ios_parity_fixtures.py` passes.
- `ios/SomaCore` builds as a Swift Package.
- `swift test` passes inside `ios/SomaCore`.
- Swift parity tests compare at least target BPM, arousal score, stress state, recovery priority, instrument set, and prompt text against Python fixtures.
- README points future iOS work to `ios/SomaCore` and warns that Suno/LLM/GraphRAG stay server-side.

## Self-Review

- Spec coverage: The user asked where to start for migrating the whole project into an iOS app. This plan covers the starting foundation and explicitly splits the whole migration into independent follow-up plans.
- Placeholder scan: The plan contains concrete file paths, code, commands, and expected outputs for the first migration foundation.
- Type consistency: Swift names map to Python fixture snake_case through `CodingKeys`; `ProcessedParams`, `MusicStrategy`, and `CompiledPrompt` are defined before they are tested.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-01-ios-migration-foundation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
