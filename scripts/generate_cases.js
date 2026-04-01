/**
 * Batch-generate 5 demo case music tracks via Suno API.
 * Reads API_KEY from .env, submits all 5 prompts, polls until done,
 * then prints the audioUrl for each so they can be merged into apps/web/index.html (DEMO_CASES).
 */

const fs   = require('fs');
const path = require('path');

const REPO_ROOT = path.join(__dirname, '..');

// ── Load .env ─────────────────────────────────────────────────────────────
function loadEnv() {
  const envPath = path.join(REPO_ROOT, '.env');
  if (!fs.existsSync(envPath)) return;
  fs.readFileSync(envPath, 'utf8')
    .split('\n')
    .forEach(line => {
      const [key, ...rest] = line.trim().split('=');
      if (key && rest.length) process.env[key.trim()] = rest.join('=').trim();
    });
}
loadEnv();

const API_KEY   = process.env.API_KEY || process.env.SUNO_API_KEY;
const SUNO_BASE = 'https://api.sunoapi.org';
const POLL_MS   = 6000;
const MAX_WAIT  = 420000; // 7 min

if (!API_KEY) {
  console.error('❌ No API Key found. Set API_KEY in .env');
  process.exit(1);
}
console.log(`🔑 API Key: ${API_KEY.slice(0, 8)}...\n`);

const HEADERS = {
  'Authorization': `Bearer ${API_KEY}`,
  'Content-Type':  'application/json',
};

// ── Case prompts ──────────────────────────────────────────────────────────
const CASES = [
  {
    id:     'case_001',
    name:   'Xiao Wang — Work Anxiety',
    title:  'Urban Night — Neo Soul Groove',
    prompt: 'Instrumental, Neo-Soul groove, 70 BPM, warm analog synthesizer and deep smooth bass, lo-fi hip hop beat with vinyl crackle, urban night rain atmosphere, relaxing jazzy chords, no lead vocal',
  },
  {
    id:     'case_002',
    name:   'Lao Li — Insomnia',
    title:  'Cello Lullaby — Ambient Classical',
    prompt: 'Instrumental, ambient classical, 50 BPM, soft cello legato and warm flute, continuous sustained notes and pure acoustic resonance, highly peaceful and sleep inducing, absolutely no drums and no sharp attacks',
  },
  {
    id:     'case_003',
    name:   'Xiao Chen — Attention Deficit',
    title:  'Minimal IDM — Focus Pulse',
    prompt: 'Instrumental, minimal IDM, 90 BPM, crisp clean electronic texture, steady repetitive pulse with binaural ambient, focused energy and pure concentration, no distracting melodies',
  },
  {
    id:     'case_004',
    name:   'Li Tongxue — PhD Anxiety',
    title:  'Late Night Lab — Neo Soul Meditation',
    prompt: 'Instrumental, Neo-Soul meditation, 65 BPM, warm analog synth with soft humming textures, gentle lo-fi groove, supportive and encouraging mood, reduce PhD anxiety, academic stress relief, peaceful lab night atmosphere, no vocals',
  },
  {
    id:     'case_005',
    name:   'Prof. Zhang — Existential Anxiety',
    title:  'Cinematic Memoir — Orchestral Ambient',
    prompt: 'Instrumental, cinematic memoir, 55 BPM, warm piano with soft strings, nostalgic orchestral ambient, bittersweet reflection, middle-aged wisdom, reduce tenure anxiety, accept life complexity, gentle catharsis, hopeful resolution',
  },
];

// ── API helpers ───────────────────────────────────────────────────────────
async function submit(prompt) {
  const res = await fetch(`${SUNO_BASE}/api/v1/generate`, {
    method:  'POST',
    headers: HEADERS,
    body: JSON.stringify({
      customMode:   false,
      instrumental: true,
      prompt:       prompt.slice(0, 500),
      model:        'V5',
      callBackUrl:  'https://example.com/callback',
    }),
  });
  const data = await res.json();
  if (data.code !== 200) throw new Error(`Submit failed: ${data.msg || JSON.stringify(data)}`);
  return data.data.taskId;
}

async function poll(taskId) {
  const res = await fetch(
    `${SUNO_BASE}/api/v1/generate/record-info?taskId=${encodeURIComponent(taskId)}`,
    { headers: HEADERS }
  );
  const data = await res.json();
  if (data.code !== 200) throw new Error(`Poll failed: ${data.msg || JSON.stringify(data)}`);
  return data.data;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function waitForTask(taskId, label) {
  const start = Date.now();
  const FATAL = ['CREATE_TASK_FAILED','GENERATE_AUDIO_FAILED','SENSITIVE_WORD_ERROR','CALLBACK_EXCEPTION'];
  while (Date.now() - start < MAX_WAIT) {
    const d = await poll(taskId);
    const elapsed = Math.round((Date.now() - start) / 1000);
    process.stdout.write(`\r  [${label}] ${elapsed}s — ${d.status}            `);
    if (d.status === 'SUCCESS') { process.stdout.write('\n'); return d; }
    if (FATAL.includes(d.status)) throw new Error(`Fatal: ${d.status} — ${d.errorMessage || ''}`);
    await sleep(POLL_MS);
  }
  throw new Error('Timeout (7 min)');
}

function extractUrl(d) {
  const tracks = d.response?.sunoData || d.data || [];
  if (!tracks.length) return { audioUrl: null, streamUrl: null, title: null };
  const t = tracks[0];
  return {
    audioUrl:  t.audioUrl  || t.audio_url  || null,
    streamUrl: t.streamAudioUrl || t.stream_audio_url || null,
    title:     t.title || null,
  };
}

// ── Main ──────────────────────────────────────────────────────────────────
async function main() {
  console.log('🎵 Generating 5 demo case tracks\n');
  console.log('Note: submitting one at a time to avoid rate limits.\n');

  const results = [];

  for (let i = 0; i < CASES.length; i++) {
    const c = CASES[i];
    console.log(`\n[${i+1}/5] ${c.id} · ${c.name}`);
    console.log(`  Prompt: ${c.prompt.slice(0, 80)}…`);

    let taskId;
    try {
      taskId = await submit(c.prompt);
      console.log(`  TaskId: ${taskId}`);
    } catch (err) {
      console.error(`  ❌ Submit failed: ${err.message}`);
      results.push({ ...c, audioUrl: null, streamUrl: null, error: err.message });
      continue;
    }

    let trackData;
    try {
      trackData = await waitForTask(taskId, c.id);
    } catch (err) {
      console.error(`  ❌ Poll failed: ${err.message}`);
      results.push({ ...c, audioUrl: null, streamUrl: null, error: err.message });
      continue;
    }

    const { audioUrl, streamUrl, title } = extractUrl(trackData);
    console.log(`  ✅ Done! Audio URL: ${audioUrl || streamUrl || 'N/A'}`);
    results.push({ ...c, audioUrl, streamUrl, returnedTitle: title });
  }

  // ── Print summary ─────────────────────────────────────────────────────
  console.log('\n\n════════════════════════════════════════════');
  console.log('  RESULTS — copy these into DEMO_CASES in apps/web/index.html');
  console.log('════════════════════════════════════════════\n');

  results.forEach(r => {
    console.log(`${r.id}: {`);
    console.log(`  audioUrl:  '${r.audioUrl || ''}',`);
    console.log(`  streamUrl: '${r.streamUrl || ''}',`);
    console.log(`  title:     '${r.returnedTitle || r.title}',`);
    if (r.error) console.log(`  // ERROR: ${r.error}`);
    console.log('}');
    console.log('');
  });

  // Also write to results.json for easy copy-paste
  const outPath = path.join(REPO_ROOT, 'data', 'case_audio_urls.json');
  fs.writeFileSync(outPath, JSON.stringify(results, null, 2), 'utf8');
  console.log(`\n📄 Full results also saved to: ${outPath}`);
}

main().catch(err => { console.error('\n❌', err.message); process.exit(1); });
