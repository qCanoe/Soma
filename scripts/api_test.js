/**
 * Suno API 测试脚本
 * 文档: https://docs.sunoapi.org/suno-api/generate-music
 *
 * 使用前请设置环境变量: SUNO_API_KEY=你的API密钥
 * 获取 API Key: https://sunoapi.org/api-key
 */

const fs   = require('fs');
const path = require('path');

const SUNO_BASE = 'https://api.sunoapi.org';

// Load .env from project root (run: node scripts/api_test.js)
function loadEnv() {
  const envPath = path.join(__dirname, '..', '.env');
  if (!fs.existsSync(envPath)) return;
  fs.readFileSync(envPath, 'utf8')
    .split('\n')
    .forEach(line => {
      const [key, ...rest] = line.trim().split('=');
      if (key && rest.length) process.env[key.trim()] = rest.join('=').trim();
    });
}
loadEnv();

const API_KEY = process.env.API_KEY || process.env.SUNO_API_KEY;

if (!API_KEY) {
  console.error('❌ 未找到 API Key');
  console.error('   请在 .env 文件中设置: API_KEY=your-key');
  process.exit(1);
}

console.log(`🔑 已读取 API Key: ${API_KEY.slice(0, 8)}...`);

const headers = {
  'Authorization': `Bearer ${API_KEY}`,
  'Content-Type': 'application/json',
};

/**
 * 1. 发起音乐生成请求（非自定义模式，最简单）
 */
async function generateMusic() {
  const body = {
    customMode: false,
    instrumental: true,
    prompt: 'A short relaxing piano tune',
    model: 'V5',
    callBackUrl: 'https://example.com/callback',
  };

  console.log('   请求体:', JSON.stringify(body, null, 2));

  const res = await fetch(`${SUNO_BASE}/api/v1/generate`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });

  const data = await res.json();
  console.log('   原始响应:', JSON.stringify(data, null, 2));

  if (data.code !== 200) {
    throw new Error(`生成失败: ${data.msg || JSON.stringify(data)}`);
  }
  return data.data.taskId;
}

/**
 * 2. 轮询获取任务状态和结果
 */
async function getTaskDetails(taskId) {
  const res = await fetch(
    `${SUNO_BASE}/api/v1/generate/record-info?taskId=${taskId}`,
    { headers }
  );
  const data = await res.json();
  if (data.code !== 200) {
    throw new Error(`查询失败: ${data.msg || JSON.stringify(data)}`);
  }
  return data.data;
}

async function pollUntilComplete(taskId, maxWait = 300000) {
  const start = Date.now();
  const interval = 5000;

  while (Date.now() - start < maxWait) {
    const details = await getTaskDetails(taskId);
    const status = details.status;
    const elapsed = Math.round((Date.now() - start) / 1000);

    console.log(`  [${elapsed}s] 状态: ${status}`);

    if (status === 'SUCCESS') {
      console.log('\n  完整轮询响应:');
      console.log(JSON.stringify(details, null, 2));
      return details;
    }
    if (['CREATE_TASK_FAILED', 'GENERATE_AUDIO_FAILED', 'SENSITIVE_WORD_ERROR', 'CALLBACK_EXCEPTION'].includes(status)) {
      console.log('\n  失败响应详情:');
      console.log(JSON.stringify(details, null, 2));
      throw new Error(`任务失败: ${status} - ${details.errorMessage || ''}`);
    }

    await new Promise((r) => setTimeout(r, interval));
  }
  throw new Error('等待超时（5分钟）');
}

async function main() {
  console.log('🎵 Suno API 测试\n');

  try {
    // Step 1: 发起生成
    console.log('1️⃣ 发起音乐生成请求...');
    const taskId = await generateMusic();
    console.log(`   Task ID: ${taskId}\n`);

    // Step 2: 轮询结果
    console.log('2️⃣ 轮询任务状态（约 30–180 秒）...');
    const result = await pollUntilComplete(taskId);

    // Step 3: 输出结果
    console.log('\n3️⃣ 生成完成！');
    // 兼容 camelCase 和 snake_case 两种返回格式
    const tracks = result.response?.sunoData || result.data || [];
    if (tracks.length === 0) {
      console.log('⚠️  未找到曲目，完整响应见上方');
    }
    tracks.forEach((t, i) => {
      console.log(`\n   曲目 ${i + 1}:`);
      console.log(`     标题: ${t.title || '-'}`);
      console.log(`     时长: ${t.duration ? Math.round(t.duration) + 's' : '-'}`);
      console.log(`     流媒体: ${t.stream_audio_url || t.streamAudioUrl || '-'}`);
      console.log(`     下载:   ${t.audio_url || t.audioUrl || '-'}`);
    });
  } catch (err) {
    console.error('\n❌ 错误:', err.message);
    process.exit(1);
  }
}

main();
