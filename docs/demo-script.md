# Soma — 3–5 minute live demo script

Use this walkthrough when presenting the web prototype (`apps/web/index.html`, optionally served via `apps/api/main.py`). **Prefer Demo Cases + cached MP3** for a reliable room demo; reserve live Suno generation as an optional encore.

## Recommended Demo Case order

| Order | Case ID   | Narrative hook                         | Vitals clue                         |
| ----- | --------- | -------------------------------------- | ----------------------------------- |
| 1     | `case_001` | Hero path: post-work anxiety, low HRV | HR 85, HRV 38 — entrainment + pads  |
| 2     | `case_002` | Sleep + sound sensitivity           | Slow tempo narrative, elderly user  |
| 3     | `case_003` | Focus / study context                | Cleaner texture, distraction story  |
| 4     | `case_004` | High stress + burnout              | Validates safeguards language       |
| 5     | `case_005` | Reflective calm / existential load   | Ends on “depth without hype” tone  |

Cases 004 and 005 are optional if time is tight.

## Timing (≈ 4 minutes)

### 00:00–00:45 — Hook + safest playback

1. Land on **Soma**. Point to **Demo Cases**: “Five teaching scenarios — each loads profile, vitals, a pre-baked AI track, and a completed History row.”
2. Click **Case 001 (Xiao Wang)**. Mention: cached audio avoids Wi‑Fi/key risk during pitches.
3. Open **History** briefly: seeded rows prove the feedback loop (`docs/stage-1-mvp-session-flow.md`).
4. Close History; optionally show **Feedback** wording on-session-end (explain you will not force it live).

### 00:45–02:00 — Why it feels “smart”

1. Expand **Why Soma chose this** — tie bullets to check-in text + profile sensitivity + vitals.
2. When the local API is running (`uvicorn`), point to the **MindWave pipeline** line: arousal, recovery priority, BPM target, instruments, safeguards (from `music_ai_module` via `/api/healthkit/mock/run`).
3. Open **Vitals** → **Connect mock HealthKit** → **Next sample** to show live JSON bridge without a watch.

### 02:00–03:15 — Optional live generation (encore)

1. Show **API Key** modal: stress **demo-only**, browser-local storage, production would use a backend proxy (`docs/session-api-contract.md`).
2. If keys + network are stable: **Start Session** once; narrate the overlay states. If anything fails, fall back: “Timer-only session + Demo Cases still tell the full story.”

### 03:15–04:00 — Trust + scope

1. Read the **wellness disclaimer** footer: not diagnosis/treatment; adjunct listening.
2. Mention **GraphRAG** / clinical audit as optional server-side safety (`data/knowledge/README.md`) — no need to enable live.
3. Close with roadmap: native iOS + HealthKit + parity fixtures (`docs/superpowers/plans/2026-05-01-ios-migration-foundation.md`).

## Speaker notes

- **If API is down:** Reason panel still works with the on-device heuristic; say “full engine syncs when this FastAPI wrapper is running.”
- **If Suno is down:** Use **Case 001** cached track + **End Session → feedback** on a timer-only run to show the loop.
- **Privacy line:** Vitals in the demo are synthetic; real product would use HealthKit consent strings and minimise raw telemetry uploads.
