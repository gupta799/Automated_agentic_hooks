#!/usr/bin/env python3
"""
LEARNING LOGGER HOOK  (async — does NOT block Claude)
Fires on: PostToolUse for Bash, Write, Edit
Purpose:  Build a rolling log of tool usage and regenerate
          .claude/learning/insights.md with pattern summaries.
          Insights are re-injected on the next SessionStart so
          Claude accumulates knowledge across sessions.
"""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


MAX_LOG_LINES = 500
KEEP_LINES = 400


def main() -> None:
    input_data = json.loads(sys.stdin.read())

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    learning_dir = project_dir / ".claude" / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    tool_log = learning_dir / "tool_log.jsonl"
    insights_file = learning_dir / "insights.md"

    tool_name: str = input_data.get("tool_name", "unknown")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Append this tool use to the log ---------------------------------
    entry: dict = {"ts": timestamp, "tool": tool_name}

    if tool_name == "Bash":
        entry["cmd"] = input_data.get("tool_input", {}).get("command", "")
        entry["exit"] = input_data.get("tool_response", {}).get("exit_code", 0)
    elif tool_name in ("Write", "Edit"):
        entry["file"] = input_data.get("tool_input", {}).get("file_path", "")

    with tool_log.open("a") as f:
        f.write(json.dumps(entry) + "\n")

    # --- Keep log bounded ------------------------------------------------
    lines = tool_log.read_text().splitlines()
    if len(lines) > MAX_LOG_LINES:
        tool_log.write_text("\n".join(lines[-KEEP_LINES:]) + "\n")

    # --- Regenerate insights ---------------------------------------------
    all_entries = [json.loads(l) for l in tool_log.read_text().splitlines() if l.strip()]

    bash_cmds = [e["cmd"].split()[0] for e in all_entries if e.get("tool") == "Bash" and e.get("cmd")]
    file_exts = [
        Path(e["file"]).suffix.lstrip(".") or "no-ext"
        for e in all_entries
        if e.get("tool") in ("Write", "Edit") and e.get("file")
    ]

    top_cmds = Counter(bash_cmds).most_common(5)
    top_exts = Counter(file_exts).most_common(5)

    total_bash = sum(1 for e in all_entries if e.get("tool") == "Bash")
    total_writes = sum(1 for e in all_entries if e.get("tool") in ("Write", "Edit"))

    cmd_lines = "\n".join(f"- `{cmd}` ({count} uses)" for cmd, count in top_cmds) or "_No data yet_"
    ext_lines = "\n".join(f"- `.{ext}` ({count} edits)" for ext, count in top_exts) or "_No data yet_"

    insights_file.write_text(
        f"# Automated Learning Insights\n"
        f"_Last updated: {timestamp}_\n\n"
        f"## Session Statistics\n"
        f"- Bash commands executed: {total_bash}\n"
        f"- Files written/edited: {total_writes}\n\n"
        f"## Most Used Commands\n{cmd_lines}\n\n"
        f"## Most Edited File Types\n{ext_lines}\n\n"
        f"## Active Hook Policies\n"
        f"- Auto-permissions: safe read/write ops bypass prompts\n"
        f"- Test gate: tests run automatically before each Stop\n"
        f"- Context monitor: /compact triggered if context > 50%\n"
    )


if __name__ == "__main__":
    main()
