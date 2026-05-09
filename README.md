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

Optional **clinical music knowledge graph** (GraphRAG) can run *between* Layer 2 and Layer 3: it retrieves evidence-backed constraints from `data/knowledge/` (chunks + `graph.json`), merges safety rules, and attaches `clinical_audit` metadata — enable with `use_knowledge_graph=True` on `MusicAIPipeline.run()` (see [Medical music knowledge graph](#medical-music-knowledge-graph-graphrag)).

---

## Repository Structure

```
MindWave/
├── apps/
│   ├── api/
│   │   └── main.py            # Local FastAPI wrapper for Layer 1-3 + static SPA hosting
│   └── web/
│       └── index.html         # Single-page therapy UI ("Soma"; all-in-one, no build)
├── music_ai_module/           # Python pipeline library (importable package)
│   ├── __init__.py
│   ├── models.py              # Layer 1 + Features / State / Strategy dataclasses
│   ├── style_maps.py          # Occupation → genre prompt (single source)
│   ├── processor.py           # Layer 2: BiometricProcessor
│   ├── compiler.py            # Layer 3: MusicPromptCompiler
│   ├── pipeline.py            # MusicAIPipeline
│   ├── config.py              # SystemConfig
│   ├── knowledge/             # GraphRAG: ingest, graph store, retriever, clinical auditor
│   └── example.py             # CLI smoke test
├── tests/                     # pytest regression suite (`pip install -e ".[dev]"`)
├── scripts/
│   ├── generate_cases.js      # Batch-generate 5 demo tracks → data/case_audio_urls.json
│   └── api_test.js            # Suno API smoke test
├── data/
│   ├── case_audio_urls.json   # Cached demo MP3 URLs (regenerate via scripts)
│   ├── case.md                # Clinical case definitions
│   └── knowledge/             # GraphRAG sources, seed chunks/graph, ingest output
├── notebooks/
│   └── pipeline_demo.ipynb    # Minimal Jupyter walkthrough (imports music_ai_module)
├── PRODUCT.md                 # Product/design context for Soma
├── pyproject.toml             # pip install -e . (optional)
├── requirements.txt
├── .env.example               # Copy to .env for local keys
├── README.md
└── LICENSE
```

**Conventions:** keep **domain data** under `data/`, **automation** under `scripts/`, the **static web client** under `apps/web/`, and the **local HTTP wrapper** under `apps/api/`. The Python package stays at the repository root so existing `from music_ai_module import …` and `python music_ai_module/example.py` continue to work.

---

## Features

### Therapy Interface (`apps/web/index.html`)

Open the file in a browser (double-click or "Open with Live Server") for the static demo. To enable the authoritative Python biometric pipeline from the UI, run the local FastAPI app and open the served page at `http://127.0.0.1:8000/`.


| Area                  | Details                                                                                                                                        |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mood Input**        | Free-text entry interpreted into therapy mode                                                                                                  |
| **Mode Chips**        | Deep Focus · Calm Down · Drift to Sleep · Anxiety Relief · Grounding · Energy Boost · Trauma Gentle                                            |
| **Vibe Chips**        | Anxious · Overwhelmed · Creative Flow (multi-select, up to 3)                                                                                  |
| **Brainwave Mapping** | Each mode maps to a clinical frequency: Gamma 40 Hz / Theta 6 Hz / Delta 2 Hz / Alpha 10 Hz / Schumann 7.83 Hz / Beta 18 Hz / Infra-Low 0.5 Hz |
| **Vinyl Player**      | Gramophone-style visualiser with EQ bars, progress scrubbing, skip ±30s                                                                        |
| **Suno Generation**   | One-click AI music generation via Suno V5 API with live status polling                                                                         |
| **Controls Drawer**   | Intensity (1–4) · Duration (15/30/45 min) · Environment (None/Rain/Noise)                                                                      |

**Session flow (stage 1, current implementation):** Primary action is **Start guided session** (timer + UI) without an API key, or **Start session · live AI** once a Suno key is saved. Cached **Demo Cases** give instant playback for pitches. Each visit can end with **feedback**; **History** persists to browser `localStorage` (`soma-sessions-v1`). Server-side session CRUD is not implemented yet.

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
| `case_001` | Xiao Wang, 28M   | Work anxiety, post-work brain tension                | *Rain on Velvet*       |
| `case_002` | Lao Li, 62F      | Insomnia, auditory sensitivity                       | *Moonlit Reedfield*    |
| `case_003` | Xiao Chen, 21M   | Attention deficit, study distraction                 | *Pulse Chamber*        |
| `case_004` | Li Tongxue, 28M  | PhD thesis anxiety, late-night lab                   | *Late Lab Calm*        |
| `case_005` | Prof. Zhang, 45M | Dual research/teaching pressure, existential anxiety | *Paper Lantern Years*  |


Clicking a case instantly loads: profile data into the modal, mood input and mode/vibe chips, biometric data into the Vitals monitor, and begins playing the cached MP3.

---

### Local FastAPI Wrapper (`apps/api/main.py`)

The local API wraps `MusicAIPipeline` for JSON clients and can also serve the static SPA:

```bash
pip install -e ".[api]"
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /health` — local health check.
- `POST /api/pipeline/run` — full `StaticUserProfile` + `AppleWatchBiometrics` payload.
- `POST /api/healthkit/mock/run` — camelCase mock vitals shape used by the web prototype.

> [!NOTE]
> This API is intended for local development and demos. It currently has no authentication, no rate limiting, and no server-side session store.

---

## Python Module (`music_ai_module`)

### Requirements

- **Python 3.10+** recommended (stdlib `dataclasses` / typing usage)
- **Packages**: `openai`, `numpy`, `beautifulsoup4`, `networkx`, `pyyaml` (see Installation)

### Installation

```bash
pip install -r requirements.txt
# or install the package directly:
pip install -e .
# optional local API + tests:
pip install -e ".[api,dev]"
```

Core dependencies: `openai`, `numpy`, `beautifulsoup4`, `networkx`, `pyyaml` (see `pyproject.toml`).

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

# Optional: clinical music knowledge graph (Layer 2.5) — evidence-aware safety merge
# result = pipeline.run(user, biometrics, use_knowledge_graph=True, user_intent="exam anxiety")
```

### Medical music knowledge graph (GraphRAG)

The `music_ai_module/knowledge/` package maintains **local** files under `data/knowledge/`:

| File | Purpose |
|------|---------|
| `sources.yaml` | Registry of fetchable URLs (NCCIH, WHO ICD license page, etc.) |
| `README.md` | Seed corpus coverage, validation rules, and update workflow |
| `chunks.jsonl` | Text chunks + offsets (ingest appends; repo ships curated **seed** excerpts) |
| `graph.json` | Nodes/edges with `evidence.chunk_id` + verbatim `quote` when extracted |
| `raw/` | Optional HTML snapshots from ingest (gitignored by default) |

**CLI** (module entry point):

```bash
python -m music_ai_module.knowledge ingest --sources data/knowledge/sources.yaml
python -m music_ai_module.knowledge ingest --sources data/knowledge/sources.yaml --extract  # needs LLM key
python -m music_ai_module.knowledge query "anxiety sleep music intervention"
python -m music_ai_module.knowledge audit --case case_003
```

- Without `OPENAI_API_KEY`, retrieval falls back to **keyword overlap** on chunks (good for tests/offline demos).
- With a key + `EMBEDDING_MODEL`, retrieval uses **embedding cosine similarity** on chunks; `--extract` calls an OpenAI-compatible chat model to populate `graph.json` (every relation must quote text that appears in the chunk).

**Scope & disclaimer:** this layer supports **wellness music planning** only. It does **not** diagnose or treat medical conditions. Seed content cites public-domain / openly licensed pages (credit NCCIH and WHO as applicable). Do not ship proprietary manuals (e.g. full DSM-5 text) inside the repo.

### Run the Smoke Test

```bash
python music_ai_module/example.py            # no API calls
python music_ai_module/example.py --verify   # optional LLM verification (~$0.0005)
python -m pytest tests -q                     # algorithm regression tests (requires `.[dev]`)
```

### Configuration

All parameters are centralised in `SystemConfig` and can be overridden via environment variables:


| Parameter                                        | Default                      | Description                              |
| ------------------------------------------------ | ---------------------------- | ---------------------------------------- |
| `OPENAI_API_KEY`                                 | —                            | LLM API key (optional verification + GraphRAG extract/embed) |
| `LLM_BASE_URL`                                   | `https://api.openai.com/v1` | OpenAI-compatible endpoint               |
| `LLM_MODEL`                                      | `gpt-3.5-turbo`              | Model for prompt verification + KG extract |
| `EMBEDDING_MODEL`                                  | `text-embedding-3-small`     | Embedding model for chunk retrieval       |
| `KNOWLEDGE_DATA_DIR`                             | *(repo)* `data/knowledge`   | Override path for graph/chunks/cache      |
| `KNOWLEDGE_CHUNK_SIZE`                           | 1200                         | Ingest chunk character length             |
| `KNOWLEDGE_CHUNK_OVERLAP`                       | 200                          | Ingest chunk overlap                      |
| `KNOWLEDGE_MAX_ANCHOR_CHARS`                     | 200                          | Max extra emotional-anchor suffix text    |
| `KNOWLEDGE_ENABLED_DEFAULT`                      | false                        | If `true`, pipeline always runs KG audit  |
| `SUNO_API_KEY`                                   | —                            | Suno music generation key (Layer 4)      |
| `MIN_BPM`                                        | 45                           | Hard floor for entrainment BPM           |
| `MAX_BPM`                                        | 140                          | Hard ceiling for entrainment BPM         |
| `RHYTHM_REDUCTION_PCT`                           | 15.0                         | Entrainment reduction (%)                |
| `AROUSAL_EXTRA_BPM_REDUCTION_MAX`                | 8.0                          | Extra BPM pull-down when arousal → 100   |
| `HRV_SAFETY_THRESHOLD_MS`                        | 40.0                         | HRV curve anchor (risk ↑ when lower)     |
| `MAX_NOISE_DB`                                   | 70.0 dB                      | Noise-risk curve anchor                  |
| `RESPIRATORY_ELEVATED_THRESHOLD`                 | 18.0                         | Respiratory load curve anchor            |
| `AROUSAL_WEIGHT_HR` … `AROUSAL_WEIGHT_MOTION`    | see `config.py`              | Normalised arousal blend                 |
| `MASKING_ENTER_AROUSAL` / `MASKING_EXIT_AROUSAL` | 58 / 48                      | Masking latch thresholds (0–100)         |
| `NOISE_FORBID_ENTER_DB` / `NOISE_FORBID_EXIT_DB` | 72 / 66                      | Safeguard latch thresholds (dB)          |
| `TEMPORAL_HISTORY_MAXLEN`                        | 12                           | Samples remembered for trend estimation  |
| `sample_interval_s`                              | 30 s                         | Biometric sampling interval              |
| `feedback_loop_s`                                | 180 s                        | Duration of one intervention cycle       |
| `cycles_per_session`                             | 3                            | Cycles per full therapy session          |
| `HR_SMOOTHING_WINDOW`                            | 5                            | Moving-average window for HR filter      |


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


| Principle                         | Implementation                                                                                                                                            |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rhythmic Entrainment**          | Music BPM set below heart rate (default 15%); repeated auditory stimuli entrain cardiovascular rhythms via baroreflex modulation                          |
| **HRV & Vagal Tone**              | SDNN < 40 ms indicates sympathetic dominance; acoustic masking (pink noise) reduces perceived threat and supports parasympathetic re-engagement           |
| **Respiratory Synchronisation**   | Sustained legato instruments at slow tempos naturally extend exhalation cycles, activating the parasympathetic nervous system                             |
| **Brainwave Entrainment**         | Binaural beat frequencies embedded at clinically relevant bands: Delta (2 Hz, sleep), Theta (6 Hz, relaxation), Alpha (10 Hz), Gamma (40 Hz, focus), etc. |
| **Environmental Acoustic Safety** | Above 70 dB ambient, sharp transients risk startle responses; constraints are applied automatically                                                       |


---

## Environment Setup

Copy [`.env.example`](.env.example) to `.env` and fill in secrets. **Do not commit `.env`.**

- **Node** (`scripts/generate_cases.js`, `scripts/api_test.js`): these load `.env` from the repo root. They accept **`API_KEY`** or **`SUNO_API_KEY`** (same Suno key).
- **Python** (`music_ai_module`): reads **process environment variables only** — it does not load `.env` automatically. Set `OPENAI_API_KEY`, `SUNO_API_KEY`, etc. in your shell, IDE, or a small wrapper that calls `load_dotenv`. For Suno from Python, use **`SUNO_API_KEY`** (Python does not read `API_KEY`).

See commented sections in `.env.example` for GraphRAG (`EMBEDDING_MODEL`, `KNOWLEDGE_*`, …) and optional biometric tuning variables.

---

## License

See [LICENSE](LICENSE) for details.