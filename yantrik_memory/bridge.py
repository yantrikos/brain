#!/usr/bin/env python3
"""
Yantrik Memory Bridge — JSON stdin/stdout interface for hooks.

Usage:
    echo '{"command": "health_check", "args": {}}' | python3 bridge.py
"""

import sys
import json

from yantrik_memory.core import YantrikMemory


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input", "success": False}))
        return

    command = input_data.get("command", "")
    args = input_data.get("args", {})
    config = input_data.get("config", {})

    try:
        mem = YantrikMemory(config)

        if command == "health_check":
            result = mem.health_check()
            print(json.dumps({"success": True, **result}))

        elif command == "refresh_on_startup":
            agent_id = args.get("agent_id", "default")
            result = mem.refresh_on_startup(agent_id=agent_id)
            print(json.dumps(result))

        elif command == "save_session":
            agent_id = args.get("agent_id", "default")
            summary = args.get("session_summary", "Session ended")
            rid = mem.remember(
                agent_id=agent_id,
                content=summary,
                memory_kind="summary",
                importance=0.6,
                scope="session",
            )
            print(json.dumps({"success": True, "rid": rid}))

        elif command == "recall":
            agent_id = args.get("agent_id", "default")
            query = args.get("query", "")
            limit = args.get("limit", 5)
            results = mem.recall(agent_id=agent_id, query=query, limit=limit)
            print(json.dumps({
                "success": True,
                "memories": [
                    {"content": sm.memory.content, "score": sm.score, "kind": sm.memory.memory_kind}
                    for sm in results
                ],
            }))

        elif command == "remember":
            rid = mem.remember(
                agent_id=args.get("agent_id", "default"),
                content=args.get("content", ""),
                memory_kind=args.get("memory_kind", "fact"),
                importance=args.get("importance", 0.5),
            )
            print(json.dumps({"success": True, "rid": rid}))

        elif command == "get_context":
            result = mem.get_full_context(
                agent_id=args.get("agent_id", "default"),
                user_id=args.get("user_id", ""),
                message=args.get("message", ""),
            )
            print(json.dumps({"success": True, "context": result}))

        elif command == "stats":
            result = mem.stats()
            print(json.dumps({"success": True, "stats": result}))

        else:
            print(json.dumps({"error": f"Unknown command: {command}", "success": False}))

        mem.close()

    except Exception as e:
        print(json.dumps({"error": str(e), "success": False}))


if __name__ == "__main__":
    main()
