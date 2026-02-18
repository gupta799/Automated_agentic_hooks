#!/usr/bin/env python3
"""PreCompact hook — snapshots git state and emits compaction retention instructions."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", "-C", str(cwd)] + args, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def transcript_stats(transcript_path: str) -> tuple[int, int]:
    if not transcript_path:
        return 0, 0
    t = Path(transcript_path)
    if not t.exists():
        return 0, 0
    return sum(1 for _ in t.open()), t.stat().st_size // 1024


def write_git_snapshot(learning_dir: Path, project_dir: Path, trigger: str, msg_count: int, transcript_kb: int, timestamp: str) -> None:
    if run_git(["rev-parse", "--is-inside-work-tree"], project_dir) != "true":
        return
    branch = run_git(["branch", "--show-current"], project_dir)
    status = run_git(["status", "--short"], project_dir)
    snapshot = (
        f"# Pre-Compact Snapshot — {timestamp}\n"
        f"Trigger: {trigger}\n"
        f"Branch: {branch}\n"
        f"Transcript: {msg_count} lines / {transcript_kb}KB\n\n"
        f"## Uncommitted Changes\n```\n{status or 'none'}\n```\n"
    )
    (learning_dir / "pre_compact_snapshot.md").write_text(snapshot)


COMPACTION_RETENTION_INSTRUCTIONS = """\
COMPACTION INSTRUCTIONS (automated learning system):

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


def main() -> None:
    input_data = json.loads(sys.stdin.read())

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    learning_dir = project_dir / ".claude" / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    trigger = input_data.get("trigger", "auto")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    msg_count, transcript_kb = transcript_stats(input_data.get("transcript_path", ""))

    with (learning_dir / "compact_log.jsonl").open("a") as f:
        f.write(json.dumps({"event": "pre_compact", "trigger": trigger, "msgs": msg_count, "kb": transcript_kb, "ts": timestamp}) + "\n")

    write_git_snapshot(learning_dir, project_dir, trigger, msg_count, transcript_kb, timestamp)

    print(COMPACTION_RETENTION_INSTRUCTIONS)


if __name__ == "__main__":
    main()
