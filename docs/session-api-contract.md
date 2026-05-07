# Session API Contract (Soma / MindWave)

Backend-ready JSON contract aligned with the stage-1 Web client (`localStorage` keys `soma-sessions-v1`, `soma-active-session-v1`). Future `RemoteSessionStore` should map 1:1 to these shapes.

## Session object

| Field | Type | Notes |
|-------|------|--------|
| `id` | string | Unique, e.g. `sess_<timestamp>_<rand>` |
| `createdAt` | ISO string | |
| `updatedAt` | ISO string | Optional; set on each transition |
| `status` | enum | `draft`, `generating`, `playing`, `completed`, `abandoned`, `failed` |
| `input` | object | See below |
| `profileSnapshot` | object | Subset of therapy profile at session time |
| `vitalsSnapshot` | object \| null | Apple Watch–style snapshot; null if unavailable |
| `demoCaseId` | string \| null | e.g. `case_001` when loaded from demo |
| `recommendation` | object | See below |
| `track` | object \| null | See below |
| `feedback` | object \| null | Present when `status === completed` |

### `input`

```json
{
  "freeText": "",
  "mode": "focus",
  "vibes": ["anxious", "creative"],
  "durationMin": 45,
  "intensity": 3,
  "environment": "Rain"
}
```

### `profileSnapshot`

Optional fields: `name`, `sleep`, `goals`, `styles`, `sensitive`, `rhythm`, `volume`.

### `vitalsSnapshot`

Flat fields: `heartRate`, `hrv`, `respiratoryRate`, `bloodOxygen`, `wristTemperature`, `ambientNoise`, `bodyMotion`, `sleepStage`, `stressScore`, `baselineHR`.

### `recommendation`

```json
{
  "title": "Soma recommends …",
  "reasonBullets": ["…", "…", "…"],
  "strategyPills": ["72 BPM", "soft texture"],
  "prompt": "Final Suno prompt string (≤500 chars)"
}
```

### `track`

```json
{
  "source": "suno",
  "title": "",
  "audioUrl": "",
  "streamUrl": "",
  "taskId": ""
}
```

`source` is one of: `suno`, `cached_demo`, `guided_fallback`.

### `feedback`

```json
{
  "calmAfter": 4,
  "helpfulness": "helped",
  "soundFit": "good",
  "notes": "",
  "submittedAt": "ISO string"
}
```

`helpfulness`: `helped` \| `neutral` \| `worse`  
`soundFit`: `good` \| `too_fast` \| `too_busy` \| `too_sharp` \| `disliked`

---

## REST endpoints (future)

### `POST /api/sessions`

Body: partial session (typically `input` + client `id` optional).  
Response: `{ "session": Session }` with `status: draft`.

### `PATCH /api/sessions/:id`

Body: partial update (`status`, `recommendation`, `track`, …).  
Response: `{ "session": Session }`.

### `POST /api/sessions/:id/feedback`

Body: `feedback` object (without `submittedAt`; server sets time).  
Response: `{ "session": Session }` with `status: completed`.

### `GET /api/sessions`

Query: `limit`, `cursor`, optional `mode`, `helpfulness`.  
Response: `{ "sessions": Session[], "nextCursor": string | null }`.

### `POST /api/generate` (future Suno proxy)

Body: `{ "sessionId": string, "prompt": string }` or server looks up session by id.  
Response: `{ "taskId": string }` → poll until URLs available, then `PATCH` session `track`.

---

## Auth (future)

Short-lived bearer token; no third-party music API keys on device.
