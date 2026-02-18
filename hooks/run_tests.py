#!/usr/bin/env python3
"""Configurable test runner — set test_command in .claude/hooks/config.json.

    { "test_command": "npm test" }

CLAUDE_TEST_COMMAND environment variable takes precedence over config.json.
Exits 0 with no output when unconfigured so projects without tests are not blocked.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def load_config(project_dir: Path) -> dict:
    config_file = project_dir / ".claude" / "hooks" / "config.json"
    try:
        return json.loads(config_file.read_text()) if config_file.exists() else {}
    except json.JSONDecodeError:
        return {}


def resolve_test_command(project_dir: Path) -> str | None:
    env_cmd = os.environ.get("CLAUDE_TEST_COMMAND", "").strip()
    if env_cmd:
        return env_cmd
    configured = load_config(project_dir).get("test_command")
    return configured if configured else None


def main() -> int:
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    config = load_config(project_dir)
    timeout = config.get("test_timeout_seconds", 120)

    test_cmd = resolve_test_command(project_dir)
    if not test_cmd:
        return 0

    print(f"[test-runner] $ {test_cmd}", flush=True)
    try:
        return subprocess.run(test_cmd, shell=True, cwd=str(project_dir), timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        print(f"[test-runner] Timed out after {timeout}s", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
