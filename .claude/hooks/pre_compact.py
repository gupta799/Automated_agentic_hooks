#!/usr/bin/env python3
"""
PRE-COMPACT HOOK
Fires on: PreCompact event (before /compact or auto-compact)
Purpose:  Persist a git + transcript snapshot to .claude/learning/ so
          nothing is lost during context compression.  Also writes
          compaction instructions to stdout so Claude knows what to
          prioritise when summarising the conversation.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd)] + args,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main() -> None:
    input_data = json.loads(sys.stdin.read())

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    learning_dir = project_dir / ".claude" / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    trigger: str = input_data.get("trigger", "auto")
    transcript_path: str = input_data.get("transcript_path", "")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Transcript stats ------------------------------------------------
    msg_count = 0
    transcript_kb = 0
    if transcript_path:
        t = Path(transcript_path)
        if t.exists():
            msg_count = sum(1 for _ in t.open())
            transcript_kb = t.stat().st_size // 1024

    # --- Log compaction event --------------------------------------------
    compact_log = learning_dir / "compact_log.jsonl"
    with compact_log.open("a") as f:
        f.write(
            json.dumps(
                {
                    "event": "pre_compact",
                    "trigger": trigger,
                    "msgs": msg_count,
                    "kb": transcript_kb,
                    "ts": timestamp,
                }
            )
            + "\n"
        )

    # --- Git snapshot ----------------------------------------------------
    in_repo = run_git(["rev-parse", "--is-inside-work-tree"], project_dir)
    if in_repo == "true":
        branch = run_git(["branch", "--show-current"], project_dir)
        status = run_git(["status", "--short"], project_dir)

        snapshot = (
            f"# Pre-Compact Snapshot — {timestamp}\n"
            f"Trigger: {trigger}\n"
            f"Branch: {branch}\n"
            f"Transcript: {msg_count} lines / {transcript_kb}KB\n\n"
            "## Uncommitted Changes\n"
            f"```\n{status or 'none'}\n```\n"
        )
        (learning_dir / "pre_compact_snapshot.md").write_text(snapshot)

    # --- Compaction instructions (stdout is shown as hook output) --------
    instructions = """COMPACTION INSTRUCTIONS (automated learning system):

When compacting, prioritise retaining:
  1. Current task and its acceptance criteria
  2. All decisions made and their rationale
  3. Errors encountered and how they were resolved
  4. File paths and key code structures modified
  5. Test results and remaining failures
  6. Outstanding TODOs and next steps

Discard:
  - Exploratory search results already acted on
  - Raw tool output that led to dead ends
  - Repetitive status messages
"""
    print(instructions)


if __name__ == "__main__":
    main()
