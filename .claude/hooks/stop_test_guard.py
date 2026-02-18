#!/usr/bin/env python3
"""
STOP TEST GUARD HOOK
Fires on: Stop event (when Claude finishes responding)
Purpose:  Two-stage gate before Claude is allowed to stop:

  Stage 1 — Context size check
    Reads the transcript file size as a proxy for token usage.
    If above ~50% of the 200K token window (~400 KB), blocks stopping
    and instructs Claude to run /compact.

  Stage 2 — Test suite
    Delegates to run_tests.py.  If tests fail, blocks stopping and
    feeds the failure output back to Claude as an error message so it
    fixes the problem autonomously.

Exit codes:
  0  — all checks pass, Claude may stop
  2  — BLOCKING: stderr is fed to Claude as feedback, Claude continues
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


def main() -> None:
    input_data = json.loads(sys.stdin.read())

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    config = load_config(project_dir)
    learning_dir = project_dir / ".claude" / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    stop_hook_active: bool = input_data.get("stop_hook_active", False)
    transcript_path: str = input_data.get("transcript_path", "")

    # ── Infinite-loop guard ────────────────────────────────────────────
    # stop_hook_active=True means we are already in a stop-hook loop.
    # Allow stopping unconditionally to prevent runaway recursion.
    if stop_hook_active:
        sys.exit(0)

    # ── Stage 1: context-size check (self-compact trigger) ────────────
    compact_threshold_kb: int = config.get("context_compact_threshold_kb", 400)
    full_window_kb: int = config.get("context_full_window_kb", 800)

    if transcript_path:
        transcript = Path(transcript_path)
        if transcript.exists():
            context_kb = transcript.stat().st_size // 1024
            if context_kb >= compact_threshold_kb:
                context_pct = (context_kb * 100) // full_window_kb
                print(
                    f"AUTOMATED SELF-COMPACT: Context is ~{context_pct}% full "
                    f"({context_kb}KB / {full_window_kb}KB estimated).\n"
                    "Run /compact now to compress context before the window fills.\n"
                    "After compaction, continue your work.",
                    file=sys.stderr,
                )
                _log(learning_dir, {"event": "auto_compact_triggered", "context_kb": context_kb})
                sys.exit(2)  # Block stop → Claude sees message → runs /compact

    # ── Stage 2: test suite ───────────────────────────────────────────
    run_tests_script = project_dir / ".claude" / "hooks" / "run_tests.py"
    if not run_tests_script.exists():
        sys.exit(0)

    result = subprocess.run(
        [sys.executable, str(run_tests_script)],
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
    )

    if result.returncode != 0:
        print(
            "TEST GATE FAILED — fix failing tests before stopping.\n"
            "\n--- Test Output ---\n"
            f"{result.stdout}{result.stderr}"
            "\n-------------------\n"
            "Fix the failures above, then you will be allowed to stop.",
            file=sys.stderr,
        )
        sys.exit(2)  # Block stop → Claude reads output → fixes tests

    _log(learning_dir, {"event": "stop_allowed"})
    sys.exit(0)


def _log(learning_dir: Path, data: dict) -> None:
    from datetime import datetime, timezone

    data["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    session_log = learning_dir / "session_log.jsonl"
    with session_log.open("a") as f:
        f.write(json.dumps(data) + "\n")


if __name__ == "__main__":
    main()
