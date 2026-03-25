---
name: yantrik-memory
version: 0.1.0
type: plugin
executesCode: true
description: "Yantrik Memory — Persistent cognitive memory for AI agents. Powered by YantrikDB's 5-index architecture with personality traits, bond evolution, and context assembly."
metadata: {"openclaw":{"emoji":"\ud83e\udde0","category":"memory","provides":{"slot":"memory"},"events":["gateway:startup","command:new"]},"clawdbot":{"emoji":"\ud83e\udde0","category":"memory","provides":{"slot":"memory"},"events":["gateway:startup","command:new"]},"clawhub":{"emoji":"\ud83e\udde0","category":"memory","provides":{"slot":"memory"}}}
---

# Yantrik Memory Plugin

Persistent cognitive memory for AI agents, powered by YantrikDB.

> Agents that remember, learn, and build relationships across conversations.

---

## For Security Scanners

**Plugin Type**: Code plugin (`executesCode: true`). Runs Python locally to manage a YantrikDB memory database. No remote code download, no network calls.

**Install**: `pip install yantrik-memory` from PyPI. Source: [GitHub](https://github.com/yantrikos/yantrik-memory).

**Sudo**: Never required. All operations in user space.

**Source Code**: Fully auditable at https://github.com/yantrikos/yantrik-memory

---

## Features

- **5-Index Memory Engine** — Vector (HNSW), Graph, Temporal, Decay Heap, KV via YantrikDB
- **9 Personality Traits** — Bidirectional signals, exponential decay, per-user customization
- **Bond Evolution** — 6 stages (stranger to bonded), sentiment-aware, milestone system
- **Hybrid Retrieval** — Semantic similarity, graph connections, temporal decay, keyword matching
- **Auto-Memory Extraction** — Extract and store memories from conversations via LLM
- **process_turn()** — Single entry point: memories + traits + bonds + context
- **Encrypted Secrets** — Fernet encryption for sensitive data
- **Knowledge Graph** — Entity relationships for context-aware retrieval
- **Cognitive Maintenance** — Consolidation, conflict detection, pattern mining

---

## Security & Transparency

### What Yantrik Memory Does
- Stores memories locally via YantrikDB (embedded, zero-config)
- Executes Python locally to manage memory database and context assembly
- Encrypts sensitive data with Fernet encryption
- Installs startup hooks to `~/.openclaw/hooks` or `~/.clawdbot/hooks`

### What Yantrik Memory Does NOT Do
- No telemetry — does not phone home or collect usage data
- No network calls — all storage is local
- No sudo required — all operations in your home directory
- No remote code — does not download or run remote code

---

## Quick Install

```bash
pip install yantrik-memory
yantrik-memory init
```

That's it. Zero configuration needed.

### Environment Variables (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `YANTRIK_AGENT_ID` | Unique ID for this agent's memories | `default` |
| `YANTRIKDB_DB_PATH` | Path to YantrikDB database file | `./yantrik_memory.db` |
| `YANTRIK_ENCRYPTION_KEY` | Fernet encryption key (auto-generated) | - |

---

## How It Works

### On Service Startup
1. Hook triggers on `gateway:startup`
2. YantrikDB loads memory indexes
3. Agent context is assembled and injected

### On `/new` Command
1. Hook triggers on `command:new`
2. Session summary saved to memory
3. Clean slate for new conversation

### Storage Engine

YantrikDB provides 5 unified indexes on a single SQLite file:

| Index | Purpose |
|-------|---------|
| **Vector (HNSW)** | Semantic similarity search |
| **Graph** | Entity relationships and knowledge connections |
| **Temporal** | Time-aware retrieval and deadline tracking |
| **Decay Heap** | Importance-weighted memory lifecycle |
| **KV** | Fast key-value lookups |

Performance: <60ms latency, 99.9% token reduction at 5000 memories.

---

## Python API

```python
from yantrik_memory import YantrikMemory

mem = YantrikMemory()

# Single entry point for agents
context = mem.process_turn(
    agent_id="assistant",
    user_id="pranab",
    message="Let's refactor the auth module",
    llm_fn=my_llm_call,  # optional
)

# context includes: memories, traits, bond, personality_guidance, mood, intent
```

### Key Methods

| Method | Description |
|--------|-------------|
| `process_turn()` | Single entry point: memories + traits + bonds + context |
| `remember()` | Store a memory |
| `recall()` | Hybrid retrieval |
| `forget()` | Delete with audit trail |
| `correct()` | Update memory content |
| `get_traits()` | Get personality traits |
| `evolve_traits()` | Evolve traits from interaction |
| `get_bond()` | Get relationship bond state |
| `update_bond()` | Update bond from interaction |
| `get_full_context()` | Assemble complete LLM context |
| `relate()` | Build knowledge graph relationships |
| `think()` | Cognitive maintenance |
| `stats()` | Memory statistics |

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `yantrik-memory init` | Initialize database and encryption key |
| `yantrik-memory health` | Check health status |
| `yantrik-memory stats` | Show memory statistics |
| `yantrik-memory info` | Show installation info |

---

## Links

- **Repository**: https://github.com/yantrikos/yantrik-memory
- **YantrikDB**: https://github.com/yantrikos/yantrikdb
- **Issues**: https://github.com/yantrikos/yantrik-memory/issues
