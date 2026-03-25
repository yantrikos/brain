#!/usr/bin/env python3
"""Yantrik Memory CLI."""

import os
import sys
import json


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: yantrik-memory <command>")
        print("Commands: init, health, stats, info")
        return

    command = args[0]

    if command == "init":
        _init()
    elif command == "health":
        _health()
    elif command == "stats":
        _stats()
    elif command == "info":
        _info()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


def _init():
    """Initialize Yantrik Memory — generate encryption key and verify setup."""
    from yantrik_memory.core import YantrikMemory

    print("Initializing Yantrik Memory...")
    mem = YantrikMemory()
    health = mem.health_check()

    key_path = os.path.expanduser("~/.config/yantrik-memory/.key")
    if os.path.exists(key_path):
        print(f"  Encryption key: {key_path}")
    else:
        print("  Encryption: disabled (install cryptography for encryption)")

    db_path = os.environ.get("YANTRIKDB_DB_PATH", "./yantrik_memory.db")
    print(f"  Database: {db_path}")
    print(f"  Engine: YantrikDB")
    print(f"  Health: {'OK' if health.get('healthy') else 'FAIL'}")
    print("\nYantrik Memory is ready.")
    mem.close()


def _health():
    """Check health status."""
    from yantrik_memory.core import YantrikMemory

    mem = YantrikMemory()
    health = mem.health_check()
    print(json.dumps(health, indent=2))
    mem.close()


def _stats():
    """Show memory statistics."""
    from yantrik_memory.core import YantrikMemory

    mem = YantrikMemory()
    stats = mem.stats()
    print(json.dumps(stats, indent=2))
    mem.close()


def _info():
    """Show installation info."""
    import yantrik_memory
    import yantrikdb

    print(f"Yantrik Memory v{yantrik_memory.__version__}")
    print(f"YantrikDB v{yantrikdb.__version__}")
    print(f"Database: {os.environ.get('YANTRIKDB_DB_PATH', './yantrik_memory.db')}")
    print(f"Agent ID: {os.environ.get('YANTRIK_AGENT_ID', 'default')}")

    key_path = os.path.expanduser("~/.config/yantrik-memory/.key")
    print(f"Encryption: {'enabled' if os.path.exists(key_path) else 'disabled'}")


if __name__ == "__main__":
    main()
