#!/usr/bin/env python3
"""PostToolUse hook (async) — logs tool usage and regenerates insights.md."""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


MAX_LOG_LINES = 500
KEEP_LINES = 400


def build_log_entry(input_data: dict, timestamp: str) -> dict:
    tool_name = input_data.get("tool_name", "unknown")
    entry = {"ts": timestamp, "tool": tool_name}

    if tool_name == "Bash":
        entry["cmd"] = input_data.get("tool_input", {}).get("command", "")
        entry["exit"] = input_data.get("tool_response", {}).get("exit_code", 0)
    elif tool_name in ("Write", "Edit"):
        entry["file"] = input_data.get("tool_input", {}).get("file_path", "")

    return entry


def trim_log_if_needed(tool_log: Path) -> None:
    lines = tool_log.read_text().splitlines()
    if len(lines) > MAX_LOG_LINES:
        tool_log.write_text("\n".join(lines[-KEEP_LINES:]) + "\n")


def generate_insights(tool_log: Path, insights_file: Path, timestamp: str) -> None:
    entries = [json.loads(line) for line in tool_log.read_text().splitlines() if line.strip()]

    bash_executables = [e["cmd"].split()[0] for e in entries if e.get("tool") == "Bash" and e.get("cmd")]
    edited_extensions = [
        Path(e["file"]).suffix.lstrip(".") or "no-ext"
        for e in entries
        if e.get("tool") in ("Write", "Edit") and e.get("file")
    ]

    top_commands = Counter(bash_executables).most_common(5)
    top_extensions = Counter(edited_extensions).most_common(5)

    total_bash = sum(1 for e in entries if e.get("tool") == "Bash")
    total_file_ops = sum(1 for e in entries if e.get("tool") in ("Write", "Edit"))

    cmd_list = "\n".join(f"- `{cmd}` ({n} uses)" for cmd, n in top_commands) or "_No data yet_"
    ext_list = "\n".join(f"- `.{ext}` ({n} edits)" for ext, n in top_extensions) or "_No data yet_"

    insights_file.write_text(
        f"# Automated Learning Insights\n"
        f"_Last updated: {timestamp}_\n\n"
        f"## Session Statistics\n"
        f"- Bash commands executed: {total_bash}\n"
        f"- Files written/edited: {total_file_ops}\n\n"
        f"## Most Used Commands\n{cmd_list}\n\n"
        f"## Most Edited File Types\n{ext_list}\n\n"
        f"## Active Hook Policies\n"
        f"- Auto-permissions: safe read/write ops bypass prompts\n"
        f"- Test gate: tests run automatically before each Stop\n"
        f"- Context monitor: /compact triggered if context > 50%\n"
    )


def main() -> None:
    input_data = json.loads(sys.stdin.read())

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    learning_dir = project_dir / ".claude" / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tool_log = learning_dir / "tool_log.jsonl"
    insights_file = learning_dir / "insights.md"

    entry = build_log_entry(input_data, timestamp)
    with tool_log.open("a") as f:
        f.write(json.dumps(entry) + "\n")

    trim_log_if_needed(tool_log)
    generate_insights(tool_log, insights_file, timestamp)


if __name__ == "__main__":
    main()
