// src/index.ts
import { spawn, spawnSync } from "node:child_process";
import path from "node:path";
import fs from "node:fs";
var PLUGIN_DIR = path.resolve(__dirname, "..");
var BRIDGE_SCRIPT = path.join(PLUGIN_DIR, "yantrik_memory", "bridge.py");
function runBridge(command, args = {}, config = {}) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(BRIDGE_SCRIPT)) {
      return reject(
        new Error(
          `bridge.py not found at ${BRIDGE_SCRIPT}. Run: pip install yantrik-memory`
        )
      );
    }
    const input = JSON.stringify({ command, args, config });
    const proc = spawn("python3", [BRIDGE_SCRIPT], {
      cwd: PLUGIN_DIR,
      stdio: ["pipe", "pipe", "pipe"]
    });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (data) => stdout += data.toString());
    proc.stderr.on("data", (data) => stderr += data.toString());
    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`Bridge exited with code ${code}: ${stderr}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch {
        reject(new Error(`Invalid JSON from bridge: ${stdout}`));
      }
    });
    proc.stdin.write(input);
    proc.stdin.end();
  });
}
function checkDependencies() {
  try {
    const result = spawnSync("python3", ["-c", "import yantrik_memory"], {
      encoding: "utf-8",
      timeout: 1e4
    });
    if (result.status !== 0) {
      return {
        ok: false,
        error: "yantrik-memory Python package not found. Run: pip install yantrik-memory"
      };
    }
    return { ok: true };
  } catch {
    return { ok: false, error: "Python 3 not found" };
  }
}
async function onStartup(context) {
  const deps = checkDependencies();
  if (!deps.ok) {
    console.error(`[yantrik-memory] ${deps.error}`);
    return;
  }
  const agentId = context.config?.agentId || context.agentId || process.env.YANTRIK_AGENT_ID || "default";
  try {
    const result = await runBridge(
      "refresh_on_startup",
      { agent_id: agentId },
      context.config
    );
    if (result.success) {
      const stats2 = result.stats;
      console.log(
        `[yantrik-memory] Ready: ${stats2?.active_memories ?? 0} memories loaded for agent "${agentId}"`
      );
    } else {
      console.error(`[yantrik-memory] Startup failed: ${result.error}`);
    }
  } catch (err) {
    console.error(`[yantrik-memory] Startup error: ${err.message}`);
  }
}
async function onSessionEnd(context) {
  const agentId = context.config?.agentId || context.agentId || process.env.YANTRIK_AGENT_ID || "default";
  try {
    const result = await runBridge(
      "save_session",
      {
        agent_id: agentId,
        session_summary: context.sessionSummary || "Session ended",
        session_id: context.sessionId || null
      },
      context.config
    );
    if (result.success) {
      console.log("[yantrik-memory] Session saved");
    }
  } catch (err) {
    console.error(
      `[yantrik-memory] Session save error: ${err.message}`
    );
  }
}
async function healthCheck(config) {
  return runBridge("health_check", {}, config);
}
async function getContext(agentId, userId, message, config = {}) {
  return runBridge(
    "get_context",
    { agent_id: agentId, user_id: userId, message },
    config
  );
}
async function remember(agentId, content, options = {}) {
  return runBridge(
    "remember",
    {
      agent_id: agentId,
      content,
      memory_kind: options.memoryKind || "fact",
      importance: options.importance || 0.5
    },
    options.config || {}
  );
}
async function recall(agentId, query, options = {}) {
  return runBridge(
    "recall",
    {
      agent_id: agentId,
      query,
      limit: options.limit || 5
    },
    options.config || {}
  );
}
async function stats(config = {}) {
  return runBridge("stats", {}, config);
}
export {
  getContext,
  healthCheck,
  onSessionEnd,
  onStartup,
  recall,
  remember,
  stats
};
