# MindWave · Soma

> **Biometric-Driven Adaptive Music Therapy** — a 4-layer architecture that converts real-time Apple Watch health data into personalised AI-generated music for mental wellness.

The single-page app brand in the UI (`apps/web/index.html`) is **Soma**; this git repository is **MindWave**.

---

## Overview

MindWave bridges physiological sensing and generative music AI. It reads live biometric signals from Apple Watch (heart rate, HRV, respiratory rate, SpO₂, and more), passes them through a neuroscience-grounded rules engine, compiles a deterministic music generation prompt, and delivers the result via the Suno AI music API — all presented through a polished, single-page therapy interface.

The system is designed around **rhythmic entrainment theory**: music tempo and texture are derived directly from a user's current physiological state, not from subjective mood tags alone. Layer 2 uses a **smoothed heart rate** (moving average), applies a configurable BPM reduction (default **15%**), optionally pulls tempo slightly lower under **high arousal**, then clamps between `min_bpm` and `max_bpm` (see `SystemConfig`).

---

## Architecture

```
Apple Watch / HealthKit
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│  Layer 1 · Input & Validation                              │
│  StaticUserProfile + AppleWatchBiometrics (dataclasses)    │
│  Physiological range validation (HR, HRV, SpO₂, temp…)     │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│  Layer 2 · BiometricProcessor                             │
│  Features → continuous scores → arousal (0–100) → state     │
│  • BiometricFeatures (HR/HRV/resp/noise/motion…)           │
│  • PhysiologicalState (stress band, recovery priority,      │
│    confidence, trend, sympathetic load on smoothed HR)       │
│  • MusicStrategy (genre text, tempo, instruments, texture, │
│    emotional anchor, safeguards) — single rendering input    │
│  • Temporal hysteresis on masking & noisy-environment bans   │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│  Layer 3 · MusicPromptCompiler                             │
│  Pure deterministic renderer for MusicStrategy              │
│  [1] Music Type  [2] Genre  [3] Tempo  [4] Instruments       │
│  [5] Texture     [6] Emotional Anchor  [7] Constraints       │
│  Optional: lazy LLM client — verification only when verify=True │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────┐
│  Layer 4 · Music Generation  (Suno API v5)                 │
│  POST /api/v1/generate → poll → stream/download MP3         │
│  Real-time progress tracking, cancellation, auto-playback   │
└────────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
MindWave/
├── apps/
│   └── web/
│       └── index.html         # Single-page therapy UI (“Soma”; all-in-one, no build)
├── music_ai_module/           # Python pipeline library (importable package)
│   ├── __init__.py
│   ├── models.py              # Layer 1 + Features / State / Strategy dataclasses
│   ├── style_maps.py          # Occupation → genre prompt (single source)
│   ├── processor.py           # Layer 2: BiometricProcessor
│   ├── compiler.py            # Layer 3: MusicPromptCompiler
│   ├── pipeline.py            # MusicAIPipeline
│   ├── config.py              # SystemConfig
│   └── example.py             # CLI smoke test
├── tests/                     # pytest regression suite (`pip install -e ".[dev]"`)
├── scripts/
│   ├── generate_cases.js      # Batch-generate 5 demo tracks → data/case_audio_urls.json
│   └── api_test.js            # Suno API smoke test
├── data/
│   ├── case_audio_urls.json   # Cached demo MP3 URLs (regenerate via scripts)
│   └── case.md                # Clinical case definitions
├── notebooks/
│   └── pipeline_demo.ipynb    # Minimal Jupyter walkthrough (imports music_ai_module)
├── docs/
│   └── mvp-prd.md             # Legacy MVP product notes (zh)
├── pyproject.toml             # pip install -e . (optional)
├── requirements.txt
├── .env.example               # Copy to .env for local keys
├── README.md
└── LICENSE
```

**Conventions:** keep **domain data** under `data/`, **automation** under `scripts/`, and the **static web client** under `apps/web/`. The Python package stays at the repository root so existing `from music_ai_module import …` and `python music_ai_module/example.py` continue to work.

---

## Features

### Therapy Interface (`apps/web/index.html`)

Open the file in a browser (double-click or “Open with Live Server”). Fully self-contained — no build step, no npm install.


| Area                  | Details                                                                                                                                 |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Mood Input**        | Free-text entry interpreted into therapy mode                                                                                           |
| **Mode Chips**        | Deep Focus · Calm Down · Drift to Sleep · Anxiety Relief · Grounding · Energy Boost · Trauma Gentle                                      |
| **Vibe Chips**        | Anxious · Overwhelmed · Creative Flow (multi-select, up to 3)                                                                           |
| **Brainwave Mapping** | Each mode maps to a clinical frequency: Gamma 40 Hz / Theta 6 Hz / Delta 2 Hz / Alpha 10 Hz / Schumann 7.83 Hz / Beta 18 Hz / Infra-Low 0.5 Hz |
| **Vinyl Player**      | Gramophone-style visualiser with EQ bars, progress scrubbing, skip ±30s                                                                 |
| **Suno Generation**   | One-click AI music generation via Suno V5 API with live status polling                                                                  |
| **Controls Drawer**   | Intensity (1–4) · Duration (15/30/45 min) · Environment (None/Rain/Noise)                                                               |


### Profile Modal

5-step therapy onboarding form:

1. **Basic Information** — Name, age, gender, contact
2. **Physical Health** — Hearing, chronic conditions, medication, sleep quality (slider)
3. **Emotional Landscape** — Current state (up to 3), treatment goals, fluctuation pattern
4. **Music Preferences** — Styles, sounds to avoid, rhythm preference (slider), volume sensitivity
5. **Treatment History** — Previous therapy, types, session count, effectiveness

Profile data persists to `localStorage` under the key `moodtune-profile` and auto-restores on reload.

### Biometric Monitor (Vitals Modal)

Displays a live Apple Watch biometric snapshot with derived clinical analysis:


| Metric               | Source        | Notes                                                                                            |
| -------------------- | ------------- | ------------------------------------------------------------------------------------------------ |
| Heart Rate           | HealthKit     | ECG-style sparkline animation                                                                    |
| HRV · SDNN           | HealthKit     | 8-bar trend chart; threshold alert at < 40 ms                                                    |
| Stress Score         | Derived       | Circular ring gauge, colour-graded (green/amber/red)                                             |
| Respiratory Rate     | HealthKit     | Instrument selection trigger at > 18 br/min                                                      |
| Blood Oxygen SpO₂    | HealthKit     | Alert styling below 94%                                                                          |
| Wrist Temperature    | HealthKit     | Warning above 37.5 °C                                                                            |
| Ambient Noise        | HealthKit     | Safeguard trigger above 70 dB                                                                    |
| Body Motion (XYZ)    | Accelerometer | Three-axis bar visualisation                                                                     |
| Sleep Stage          | HealthKit     | Awake / Core / Deep / REM                                                                        |
| **Layer 2 Analysis** | Computed      | Target BPM · Sympathetic Load · HRV Status · Acoustic Texture · Instrument Set · Noise Safeguard |


### Demo Cases

Five pre-loaded clinical demonstration cases, each with a full profile, biometric snapshot, and a pre-generated Suno V5 track (titles below are the API `returnedTitle` values stored in `data/case_audio_urls.json`):


| ID         | Patient          | Condition                                            | Track                       |
| ---------- | ---------------- | ---------------------------------------------------- | --------------------------- |
| `case_001` | Xiao Wang, 28M   | Work anxiety, post-work brain tension                | *Midnight Window Seat*      |
| `case_002` | Lao Li, 62F      | Insomnia, auditory sensitivity                       | *Moonlight Between Breaths* |
| `case_003` | Xiao Chen, 21M   | Attention deficit, study distraction                 | *Pure Function*             |
| `case_004` | Li Tongxue, 28M  | PhD thesis anxiety, late-night lab                   | *Night Shift in Soft Gold*  |
| `case_005` | Prof. Zhang, 45M | Dual research/teaching pressure, existential anxiety | *Autumn Tenure*             |


Clicking a case instantly loads: profile data into the modal, mood input and mode/vibe chips, biometric data into the Vitals monitor, and begins playing the cached MP3.

---

## Python Module (`music_ai_module`)

### Requirements

- **Python 3.10+** recommended (stdlib `dataclasses` / typing usage)
- **Packages**: `openai`, `numpy` (see Installation)

### Installation

```bash
pip install -r requirements.txt
# or: pip install -e .
# optional dev/tests: pip install -e ".[dev]"
```

Core dependencies: `openai`, `numpy` (see `pyproject.toml`).

### Quick Start

```python
from datetime import datetime
from music_ai_module import MusicAIPipeline, SystemConfig
from music_ai_module.models import StaticUserProfile, AppleWatchBiometrics

user = StaticUserProfile(
    occupation="software_engineer",
    age=28,
    height_cm=180,
    baseline_heart_rate=65,
    chronic_stress_sources=["work_deadline", "sleep_quality"],
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

pipeline = MusicAIPipeline()
result = pipeline.run(user, biometrics)

print(result["prompt"])           # → final Suno prompt string
print(result["processed_params"]) # → Layer 2 bundle (legacy rhythm/texture/… + features/state/music_strategy)
MusicAIPipeline.describe(result)  # → formatted console summary

# Optional: fail fast on implausible sensors
# result = pipeline.run(user, biometrics, strict_validation=True)
```

### Run the Smoke Test

```bash
python music_ai_module/example.py            # no API calls
python music_ai_module/example.py --verify   # optional LLM verification (~$0.0005)
python -m pytest tests -q                     # algorithm regression tests (requires `.[dev]`)
```

### Configuration

All parameters are centralised in `SystemConfig` and can be overridden via environment variables:


| Parameter              | Default                      | Description                              |
| ---------------------- | ---------------------------- | ---------------------------------------- |
| `OPENAI_API_KEY`       | —                            | LLM API key (optional verification only) |
| `LLM_BASE_URL`         | `https://api.zyai.online/v1` | OpenAI-compatible endpoint               |
| `LLM_MODEL`            | `gpt-3.5-turbo`              | Model for prompt verification            |
| `SUNO_API_KEY`         | —                            | Suno music generation key (Layer 4)      |
| `MIN_BPM`              | 45                           | Hard floor for entrainment BPM           |
| `MAX_BPM`              | 140                          | Hard ceiling for entrainment BPM         |
| `RHYTHM_REDUCTION_PCT` | 15.0                         | Entrainment reduction (%)                |
| `AROUSAL_EXTRA_BPM_REDUCTION_MAX` | 8.0                  | Extra BPM pull-down when arousal → 100    |
| `HRV_SAFETY_THRESHOLD_MS` | 40.0                      | HRV curve anchor (risk ↑ when lower)     |
| `MAX_NOISE_DB`         | 70.0 dB                      | Noise-risk curve anchor                  |
| `RESPIRATORY_ELEVATED_THRESHOLD` | 18.0              | Respiratory load curve anchor            |
| `AROUSAL_WEIGHT_HR` … `AROUSAL_WEIGHT_MOTION` | see `config.py` | Normalised arousal blend |
| `MASKING_ENTER_AROUSAL` / `MASKING_EXIT_AROUSAL` | 58 / 48 | Masking latch thresholds (0–100) |
| `NOISE_FORBID_ENTER_DB` / `NOISE_FORBID_EXIT_DB` | 72 / 66 | Safeguard latch thresholds (dB) |
| `TEMPORAL_HISTORY_MAXLEN` | 12                       | Samples remembered for trend estimation    |
| `sample_interval_s`    | 30 s                         | Biometric sampling interval              |
| `feedback_loop_s`      | 180 s                        | Duration of one intervention cycle       |
| `cycles_per_session`   | 3                            | Cycles per full therapy session          |
| `HR_SMOOTHING_WINDOW`  | 5                            | Moving-average window for HR filter      |


### Layer 2 Mapping Logic

Layer 2 now follows **Features → continuous scores → arousal → PhysiologicalState → MusicStrategy**.

```
Heart Rate → smoothed HR (moving average)
Sympathetic load (Layer 2 display) = smoothed HR − baseline HR

Component scores (each 0–100, continuous ramps — no single hard flip at 40 ms / 18 br/min)
    HR load score from ΔHR vs baseline
    HRV risk score from SDNN (lower ⇒ higher risk)
    Respiratory load score vs calm ↔ stress anchors
    Noise risk score vs calm ↔ harsh anchors
    Motion intensity score from accelerometer magnitude

arousal_score (0–100)
    weighted blend of the five scores (weights configurable)

stress_state bands on arousal_score
    low ≤ `AROUSAL_LOW_MAX` (31)
    moderate ≤ `AROUSAL_MODERATE_MAX` (66)
    high above that

recovery_priority
    High arousal forces grounding; otherwise honours `therapy_goal`
    (`focus` | `calm` | `sleep` | `grounding`)

Target BPM
    base = smoothed_HR × (1 − rhythm_reduction_pct / 100)
         − (arousal_score / 100) × arousal_extra_bpm_reduction_max
    clamp to [min_bpm, max_bpm]

Masking / pink-noise + pad strength
    blends HRV risk + arousal; hysteresis latch prevents flicker at thresholds

Instruments
    respiratory_load_score chooses piano/strings ↔ hybrid ↔ cello legato set
    respects `avoid_instruments` on StaticUserProfile

Ambient noise safeguards (startle constraints)
    hysteresis on enter/exit dB so constraints do not chatter

Emotional anchor text
    sympathetic_load breakpoints + recovery_priority + chronic_stress_sources context

StaticUserProfile personalization
    music_preference, sound_sensitivity, preferred_density, therapy_goal
    blend into genre_style resolved once in MusicStrategy
```

**SPA note:** `apps/web/index.html` still mirrors parts of Layer 2 for the Vitals demo and uses a separate prompt path for mood-based Suno generation; production integrations should treat **`music_ai_module` as the canonical physiology→prompt engine**.

---

## Demo Track Generation

**Prerequisites:** Node.js **18+** (global `fetch`).

To regenerate the five demo case tracks, copy `.env.example` → `.env`, add your Suno key, then from the **repository root**:

```bash
node scripts/generate_cases.js
```

The script submits all five prompts **sequentially** (to reduce rate-limit issues), polls until completion, and writes results to `data/case_audio_urls.json`. Merge new URLs into the `DEMO_CASES` object in `apps/web/index.html` if you want the UI to play refreshed tracks. Each generation typically takes about **1–3 minutes** per track.

Polling in this script: **6 s** interval, **7 minute** overall timeout. The in-browser UI uses **5 s** polling and a **6 minute** timeout — see below.

---

## Suno API Integration

The web interface and Node scripts use the [sunoapi.org](https://sunoapi.org) third-party wrapper. API reference: [Suno API docs](https://docs.sunoapi.org/suno-api/generate-music).

```
POST  https://api.sunoapi.org/api/v1/generate
GET   https://api.sunoapi.org/api/v1/generate/record-info?taskId=…
```

- Model: **V5** (instrumental, non-custom mode)
- Prompt cap: **500** characters
- **Web UI (`apps/web/index.html`):** poll every **5 s**, max wait **6 minutes**
- **`scripts/generate_cases.js`:** poll every **6 s**, max wait **7 minutes**
- Typical status flow: `PENDING → … → SUCCESS` (intermediate states may include `TEXT_SUCCESS`, `FIRST_SUCCESS`, depending on API version)

**Privacy:** In the browser, your API key is stored in `localStorage` under `moodtune-suno-key` and is only sent to `https://api.sunoapi.org` from your machine (not through a first-party MindWave backend).

---

## Neuroscience Basis


| Principle                         | Implementation                                                                                                                                                      |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rhythmic Entrainment**          | Music BPM set below heart rate (default 15%); repeated auditory stimuli entrain cardiovascular rhythms via baroreflex modulation                                    |
| **HRV & Vagal Tone**              | SDNN < 40 ms indicates sympathetic dominance; acoustic masking (pink noise) reduces perceived threat and supports parasympathetic re-engagement                   |
| **Respiratory Synchronisation**   | Sustained legato instruments at slow tempos naturally extend exhalation cycles, activating the parasympathetic nervous system                                       |
| **Brainwave Entrainment**         | Binaural beat frequencies embedded at clinically relevant bands: Delta (2 Hz, sleep), Theta (6 Hz, relaxation), Alpha (10 Hz), Gamma (40 Hz, focus), etc.        |
| **Environmental Acoustic Safety** | Above 70 dB ambient, sharp transients risk startle responses; constraints are applied automatically                                                                  |


---

## Design System

The UI is built on a dark glass-morphism aesthetic:

- **Fonts**: Cormorant Garamond (display) · Outfit (body) · JetBrains Mono (data)
- **Colour palette**: Deep space black `#030305`, layered white-alpha glass surfaces
- **Animations**: Organic morphing background (UnicornStudio), EQ bar waveforms, vinyl record rotation, floating music notes, CSS entrances with staggered blur-up reveals
- **Framework**: Tailwind CSS (CDN) · Iconify icons · No build toolchain required

---

## Environment Setup

Create a `.env` file in the project root for **Node** scripts (`scripts/generate_cases.js`, `scripts/api_test.js`). See `.env.example`.

```env
API_KEY=your_suno_api_key_here
```

You can alternatively set `SUNO_API_KEY` — both are read by the Node utilities.

For the Python module's **optional** LLM verification:

```env
OPENAI_API_KEY=your_llm_key
LLM_BASE_URL=https://api.zyai.online/v1
LLM_MODEL=gpt-3.5-turbo
```

Suno generation inside Python (`SUNO_API_KEY`) is only needed if you call Layer 4 from code paths that use it.

---

## License

See [LICENSE](LICENSE) for details.
