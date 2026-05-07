# Stage 1 — MVP session flow (Web)

## Goal

Users complete one **therapy session**: check-in → recommendation → play (Suno, cached demo, or timer-only fallback) → **feedback** → **history** for replay/template.

## User flow

1. Enter mood text, choose **Mode** / **Vibe**, optionally open **Profile** / load **Demo case** / open **Vitals**.
2. **Reason** panel shows up to three bullets + strategy pills (profile + vitals + check-in).
3. **Start Session** runs Suno if an API key is set; otherwise a **timer-only** session uses the drawer duration with the existing player ticker.
4. **End Session** (or audio/timer end) opens **feedback**: calm now (1–5), helpfulness, sound fit, optional note.
5. **History** lists recent sessions; actions: **Replay** (audio URL), **Use as template**, **Delete**.

## Local storage

| Key | Purpose |
|-----|---------|
| `moodtune-profile` | Existing therapy profile (also snapshotted on session) |
| `moodtune-suno-key` | Existing Suno key (demo only; production = proxy) |
| `soma-active-session-v1` | Current unfinished session or `null` |
| `soma-sessions-v1` | Last 50 completed sessions (with feedback) |

## Demo history (showcase)

On each load of `apps/web/index.html`, the **Demo Cases** script **silently merges** five sample **completed** sessions (one per case, ids `sess_seed_case_001` … `sess_seed_case_005`) into `soma-sessions-v1` if they are not already present. Open **History** to see them (filters, Replay, template, Delete work as usual).

To **re-apply** the seed after editing or deleting those rows, use the browser console:

```js
somaSeedDemoHistory({ resetDemo: true })  // removes sess_seed_* then re-adds; opens History + toast
somaSeedDemoHistory()                     // append missing seed ids only; opens History + toast
```

## Fallback behaviour

- **No API key**: timer-only `guided_fallback`; user can still submit feedback.
- **Suno error**: toast + optional switch to timer session (manual End still works).
- **No vitals**: copy explains recommendations use check-in + profile only.

## UI consistency

New surfaces use shared `soma-*` utility classes (glass panel, pills, section labels) to match **Profile** / **Vitals** / **API Key** modals.

## Wellness scope

Copy treats Soma as **wellness support**, not diagnosis or treatment. See product disclaimers in UI where appropriate.

## Manual QA checklist

- [ ] Fresh load: Reason panel updates when changing mode / vibe / mood / drawer.
- [ ] Demo case: profile + vitals + cached track + reason + History after feedback.
- [ ] With Suno key: generation → play → audio end → feedback modal.
- [ ] Without Suno key: Start Session → timer runs → End Session → feedback.
- [ ] History: filter All / Calm / Focus / Sleep / Helped; Replay; Use as template; Delete.
- [ ] Fresh load: **History** includes five `sess_seed_*` demo rows (unless user cleared store).
- [ ] Reload mid-session: active session restored when appropriate (draft/generating/playing).
- [ ] Reset Aura: does not corrupt session store (optional: clear active — current product choice documented in code).
