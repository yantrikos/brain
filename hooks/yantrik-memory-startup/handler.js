/**
 * Yantrik Memory Startup Hook
 *
 * Refreshes memory on gateway startup and saves session on /new command.
 */
import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
import fs from 'node:fs';

function findBridgeScript() {
  // Try Python package resolution first
  try {
    const result = spawnSync('python3', ['-c', `
import yantrik_memory
import os
print(os.path.join(os.path.dirname(yantrik_memory.__file__), 'bridge.py'))
`], { encoding: 'utf-8', timeout: 5000 });

    if (result.status === 0 && result.stdout.trim()) {
      const p = result.stdout.trim();
      if (fs.existsSync(p)) return p;
    }
  } catch (e) {}

  // Fallback: check common skill install locations
  const home = os.homedir();
  const locations = [
    path.join(home, '.openclaw', 'skills', 'yantrik-memory', 'yantrik_memory', 'bridge.py'),
    path.join(home, '.clawdbot', 'skills', 'yantrik-memory', 'yantrik_memory', 'bridge.py'),
  ];
  for (const p of locations) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

const BRIDGE_SCRIPT = findBridgeScript();
const AGENT_ID = process.env.YANTRIK_AGENT_ID || 'default';

async function runCommand(command, args = {}) {
  return new Promise((resolve, reject) => {
    if (!BRIDGE_SCRIPT) {
      return reject(new Error('bridge.py not found. Run: pip install yantrik-memory'));
    }

    const input = JSON.stringify({ command, args, config: {} });
    const proc = spawn('python3', [BRIDGE_SCRIPT], {
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => (stdout += data.toString()));
    proc.stderr.on('data', (data) => (stderr += data.toString()));

    proc.on('close', (code) => {
      if (code !== 0) {
        console.error('[yantrik-memory] Bridge error:', stderr);
        reject(new Error('Bridge exited with code ' + code));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (e) {
        reject(new Error('Invalid JSON: ' + stdout));
      }
    });

    proc.stdin.write(input);
    proc.stdin.end();
  });
}

async function handleGatewayStartup(event) {
  console.log(`[yantrik-memory] Gateway startup, refreshing agent "${AGENT_ID}"...`);
  try {
    const result = await runCommand('refresh_on_startup', { agent_id: AGENT_ID });
    if (result.success) {
      const count = result.stats?.active_memories || 0;
      console.log(`[yantrik-memory] Ready: ${count} memories loaded`);
    } else {
      console.error('[yantrik-memory] Refresh failed:', result.error);
    }
  } catch (err) {
    console.error('[yantrik-memory] Error:', err.message);
  }
}

async function handleNewCommand(event) {
  console.log(`[yantrik-memory] Saving session for agent "${AGENT_ID}"...`);
  const context = event.context || {};
  const sessionEntry = context.previousSessionEntry || context.sessionEntry || {};

  try {
    const result = await runCommand('save_session', {
      agent_id: AGENT_ID,
      session_summary: sessionEntry.summary || 'Session ended by user',
      session_id: sessionEntry.sessionId || null,
    });
    if (result.success) {
      console.log('[yantrik-memory] Session saved');
    } else {
      console.error('[yantrik-memory] Save failed:', result.error);
    }
  } catch (err) {
    console.error('[yantrik-memory] Error:', err.message);
  }
}

const yantrikMemoryHook = async (event) => {
  if (event.type === 'gateway' && event.action === 'startup') {
    await handleGatewayStartup(event);
    return;
  }
  if (event.type === 'command' && event.action === 'new') {
    await handleNewCommand(event);
    return;
  }
};

export default yantrikMemoryHook;
