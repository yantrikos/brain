/**
 * Yantrik Memory — OpenClaw Plugin Entry Point
 *
 * Bridges OpenClaw's plugin runtime to the Python YantrikMemory engine
 * via the brain bridge script (yantrik_memory/bridge.py).
 */

import { spawn, spawnSync } from "node:child_process";
import path from "node:path";
import fs from "node:fs";

const PLUGIN_DIR = path.resolve(__dirname, "..");
const BRIDGE_SCRIPT = path.join(PLUGIN_DIR, "yantrik_memory", "bridge.py");

interface BridgeResult {
  success: boolean;
  error?: string;
  [key: string]: unknown;
}

/**
 * Execute a command via the Python bridge.
 */
function runBridge(
  command: string,
  args: Record<string, unknown> = {},
  config: Record<string, unknown> = {}
): Promise<BridgeResult> {
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
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (data: Buffer) => (stdout += data.toString()));
    proc.stderr.on("data", (data: Buffer) => (stderr += data.toString()));

    proc.on("close", (code: number | null) => {
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

/**
 * Check if Python and yantrik-memory are available.
 */
function checkDependencies(): { ok: boolean; error?: string } {
  try {
    const result = spawnSync("python3", ["-c", "import yantrik_memory"], {
      encoding: "utf-8",
      timeout: 10000,
    });
    if (result.status !== 0) {
      return {
        ok: false,
        error:
          "yantrik-memory Python package not found. Run: pip install yantrik-memory",
      };
    }
    return { ok: true };
  } catch {
    return { ok: false, error: "Python 3 not found" };
  }
}

/**
 * Plugin lifecycle: called on gateway startup.
 */
export async function onStartup(context: {
  config: Record<string, unknown>;
  agentId?: string;
}): Promise<void> {
  const deps = checkDependencies();
  if (!deps.ok) {
    console.error(`[yantrik-memory] ${deps.error}`);
    return;
  }

  const agentId =
    (context.config?.agentId as string) ||
    context.agentId ||
    process.env.YANTRIK_AGENT_ID ||
    "default";

  try {
    const result = await runBridge(
      "refresh_on_startup",
      { agent_id: agentId },
      context.config
    );
    if (result.success) {
      const stats = result.stats as Record<string, number> | undefined;
      console.log(
        `[yantrik-memory] Ready: ${stats?.active_memories ?? 0} memories loaded for agent "${agentId}"`
      );
    } else {
      console.error(`[yantrik-memory] Startup failed: ${result.error}`);
    }
  } catch (err) {
    console.error(`[yantrik-memory] Startup error: ${(err as Error).message}`);
  }
}

/**
 * Plugin lifecycle: called on session end (/new command).
 */
export async function onSessionEnd(context: {
  config: Record<string, unknown>;
  agentId?: string;
  sessionSummary?: string;
  sessionId?: string;
}): Promise<void> {
  const agentId =
    (context.config?.agentId as string) ||
    context.agentId ||
    process.env.YANTRIK_AGENT_ID ||
    "default";

  try {
    const result = await runBridge(
      "save_session",
      {
        agent_id: agentId,
        session_summary: context.sessionSummary || "Session ended",
        session_id: context.sessionId || null,
      },
      context.config
    );
    if (result.success) {
      console.log("[yantrik-memory] Session saved");
    }
  } catch (err) {
    console.error(
      `[yantrik-memory] Session save error: ${(err as Error).message}`
    );
  }
}

/**
 * Plugin lifecycle: health check.
 */
export async function healthCheck(
  config: Record<string, unknown>
): Promise<BridgeResult> {
  return runBridge("health_check", {}, config);
}

/**
 * Get full agent context for a message.
 */
export async function getContext(
  agentId: string,
  userId: string,
  message: string,
  config: Record<string, unknown> = {}
): Promise<BridgeResult> {
  return runBridge(
    "get_context",
    { agent_id: agentId, user_id: userId, message },
    config
  );
}

/**
 * Store a memory.
 */
export async function remember(
  agentId: string,
  content: string,
  options: {
    memoryKind?: string;
    importance?: number;
    config?: Record<string, unknown>;
  } = {}
): Promise<BridgeResult> {
  return runBridge(
    "remember",
    {
      agent_id: agentId,
      content,
      memory_kind: options.memoryKind || "fact",
      importance: options.importance || 0.5,
    },
    options.config || {}
  );
}

/**
 * Recall memories.
 */
export async function recall(
  agentId: string,
  query: string,
  options: { limit?: number; config?: Record<string, unknown> } = {}
): Promise<BridgeResult> {
  return runBridge(
    "recall",
    {
      agent_id: agentId,
      query,
      limit: options.limit || 5,
    },
    options.config || {}
  );
}

/**
 * Get memory stats.
 */
export async function stats(
  config: Record<string, unknown> = {}
): Promise<BridgeResult> {
  return runBridge("stats", {}, config);
}
