# Brain

Persistent cognitive memory for AI agents, powered by [YantrikDB](https://github.com/yantrikos/yantrikdb) ([docs](https://yantrikdb.com)).

## Install

```bash
pip install yantrik-memory
yantrik-memory init
```

## What it does

Gives your AI agent persistent memory that survives across conversations:

- **Remember & Recall** — Store and retrieve memories with hybrid search (semantic + graph + temporal + keyword)
- **Personality Traits** — 9 evolving traits that adapt to each user
- **Bond Evolution** — Relationships grow from stranger to bonded over time
- **Knowledge Graph** — Entity relationships for context-aware retrieval
- **Context Assembly** — One call to get everything an LLM needs

## Quick Start

```python
from yantrik_memory import YantrikMemory

mem = YantrikMemory()

# Single entry point for agents
context = mem.process_turn(
    agent_id="assistant",
    user_id="user123",
    message="I prefer dark mode and concise answers",
)

# Returns: memories, traits, bond state, personality guidance, mood, intent
print(context["traits"])       # {'conciseness': 0.55, 'humor': 0.5, ...}
print(context["bond"]["level"])  # 'acquaintance'
```

## Real Conversation Demo

Here's Cortex running inside [OpenClaw](https://github.com/openclaw/openclaw) — an open-source AI agent platform. The agent remembers context across turns, learns preferences, and builds a profile over time.

**Turn 1** — Alex introduces himself:

> **Alex:** Hey! I'm Alex. I'm a backend engineer at a startup. We're building a task management app and I need help setting up the API.

> **Agent:** Hi Alex. What stack are you using? What API help do you need?

**Turn 2** — Alex shares preferences, agent adapts:

> **Alex:** We're using Python with FastAPI. I prefer keeping things simple — no over-engineering. Can you suggest a basic project structure?

> **Agent:**
> ```
> taskapp/
> ├── app/
> │   ├── main.py          # FastAPI app
> │   ├── api/
> │   │   ├── tasks.py     # /tasks endpoints
> │   │   └── users.py     # /users endpoints
> │   ├── core/
> │   │   ├── config.py    # Settings
> │   │   └── security.py  # Auth utils
> │   ├── models/
> │   │   ├── task.py      # Pydantic models
> │   │   └── user.py
> │   └── db/
> │       └── database.py  # DB connection
> ├── requirements.txt
> └── README.md
> ```

**Turn 3** — Agent remembers the database preference:

> **Alex:** That's perfect, thanks! Oh and remember — I always use PostgreSQL for production and SQLite for local dev. What about the database layer?

> **Agent:**
> ```python
> from sqlalchemy import create_engine
> from sqlalchemy.orm import sessionmaker
> from app.core.config import settings
>
> # Use SQLite for dev, PostgreSQL for prod
> engine = create_engine(settings.DATABASE_URL)
> SessionLocal = sessionmaker(bind=engine)
> ```

**Turn 4** — Alex asks what the agent remembers:

> **Alex:** Great work! You're really helpful. One more thing — what do you remember about me and my project so far?

> **Agent:**
> - Backend engineer at a startup
> - Building a task management app
> - Using Python with FastAPI
> - Prefer simple solutions, no over-engineering
> - Always use PostgreSQL for production, SQLite for local dev

Behind the scenes, Cortex tracked:
- **Traits evolved:** `helpfulness: 0.55` (from "really helpful"), `conciseness: 0.55` (from "keeping things simple")
- **Bond level:** `acquaintance` (score: 0.08 after 4 interactions)
- **Memories stored:** 5 facts about Alex, preferences, and project context
- **Knowledge graph:** `Alex → works_at → Startup`, `TaskApp → uses → FastAPI`

## OpenClaw / ClawDBot Plugin

Cortex is a ClawHub plugin. Install via:

```bash
openclaw plugins install cortex
```

Or add to your skills directory:

```bash
cd ~/.openclaw/skills
git clone https://github.com/yantrikos/cortex.git
pip install -e cortex
```

## Powered by [YantrikDB](https://github.com/yantrikos/yantrikdb)

5 unified indexes on a single SQLite file:

| Index | Purpose |
|-------|---------|
| Vector (HNSW) | Semantic similarity |
| Graph | Entity relationships |
| Temporal | Time-aware retrieval |
| Decay Heap | Memory lifecycle |
| KV | Fast lookups |

<60ms latency. Zero config. No external databases.

## License

MIT
