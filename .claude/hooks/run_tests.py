#!/usr/bin/env python3
"""
RUN TESTS — Configurable test runner
Called by: stop_test_guard.py
Purpose:   Execute the developer-configured test command and return its
           exit code.  Configure the command in .claude/hooks/config.json:

             { "test_command": "npm test" }

           Or set the CLAUDE_TEST_COMMAND environment variable (takes
           precedence over config.json).

           When test_command is null / unset the runner exits 0 (no-op)
           so that the Stop gate does not block projects without tests.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def load_config(project_dir: Path) -> dict:
    config_file = project_dir / ".claude" / "hooks" / "config.json"
    if config_file.exists():
        try:
            return json.loads(config_file.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def get_test_command(project_dir: Path) -> str | None:
    """Return the test command to run, or None if not configured."""
    # Environment variable takes priority over config file
    if cmd := os.environ.get("CLAUDE_TEST_COMMAND", "").strip():
        return cmd
    config = load_config(project_dir)
    cmd = config.get("test_command")
    return cmd if cmd else None


def main() -> int:
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    config = load_config(project_dir)
    timeout = config.get("test_timeout_seconds", 120)

    test_cmd = get_test_command(project_dir)

    if not test_cmd:
        print(
            "[test-runner] No test command configured.\n"
            "  Set 'test_command' in .claude/hooks/config.json or the\n"
            "  CLAUDE_TEST_COMMAND environment variable to enable the test gate.",
            file=sys.stderr,
        )
        return 0  # No tests configured → pass silently, don't block Claude

    print(f"[test-runner] $ {test_cmd}", flush=True)

    try:
        result = subprocess.run(
            test_cmd,
            shell=True,
            cwd=str(project_dir),
            timeout=timeout,
        )
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"[test-runner] Timed out after {timeout}s", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
