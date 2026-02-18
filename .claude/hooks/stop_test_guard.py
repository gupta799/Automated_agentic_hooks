#!/usr/bin/env python3
"""Stop hook — blocks Claude from stopping until context is compact and tests pass.

Exit 0 allows stopping. Exit 2 with stderr blocks stopping and feeds Claude feedback.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_config(project_dir: Path) -> dict:
    config_file = project_dir / ".claude" / "hooks" / "config.json"
    try:
        return json.loads(config_file.read_text()) if config_file.exists() else {}
    except json.JSONDecodeError:
        return {}


def append_session_log(learning_dir: Path, event: dict) -> None:
    event["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with (learning_dir / "session_log.jsonl").open("a") as f:
        f.write(json.dumps(event) + "\n")


def context_is_oversized(transcript_path: str, compact_threshold_kb: int) -> tuple[bool, int, int]:
    if not transcript_path:
        return False, 0, 0
    transcript = Path(transcript_path)
    if not transcript.exists():
        return False, 0, 0
    size_kb = transcript.stat().st_size // 1024
    return size_kb >= compact_threshold_kb, size_kb, compact_threshold_kb


def run_tests(project_dir: Path) -> subprocess.CompletedProcess:
    run_tests_script = project_dir / ".claude" / "hooks" / "run_tests.py"
    return subprocess.run(
        [sys.executable, str(run_tests_script)],
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
    )


def main() -> None:
    input_data = json.loads(sys.stdin.read())

    if input_data.get("stop_hook_active", False):
        sys.exit(0)

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    config = load_config(project_dir)
    learning_dir = project_dir / ".claude" / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    compact_threshold_kb = config.get("context_compact_threshold_kb", 400)
    full_window_kb = config.get("context_full_window_kb", 800)

    oversized, context_kb, _ = context_is_oversized(
        input_data.get("transcript_path", ""), compact_threshold_kb
    )
    if oversized:
        context_pct = (context_kb * 100) // full_window_kb
        print(
            f"AUTOMATED SELF-COMPACT: Context is ~{context_pct}% full "
            f"({context_kb}KB / {full_window_kb}KB estimated).\n"
            "Run /compact now to compress context before the window fills.\n"
            "After compaction, continue your work.",
            file=sys.stderr,
        )
        append_session_log(learning_dir, {"event": "auto_compact_triggered", "context_kb": context_kb})
        sys.exit(2)

    result = run_tests(project_dir)
    if result.returncode != 0:
        print(
            "TEST GATE FAILED — fix failing tests before stopping.\n"
            "\n--- Test Output ---\n"
            f"{result.stdout}{result.stderr}"
            "\n-------------------\n"
            "Fix the failures above, then you will be allowed to stop.",
            file=sys.stderr,
        )
        sys.exit(2)

    append_session_log(learning_dir, {"event": "stop_allowed"})
    sys.exit(0)


if __name__ == "__main__":
    main()
