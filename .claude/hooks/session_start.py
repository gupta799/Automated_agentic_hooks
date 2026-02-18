#!/usr/bin/env python3
"""
SESSION START HOOK
Fires on: startup, resume, compact
Purpose:  Inject git state, accumulated learning insights, and autonomy
          guidelines so Claude operates with full context from turn one.
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

    source = input_data.get("source", "startup")
    model = input_data.get("model", "unknown")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: list[str] = [
        f"# Automated Session Context ({source})",
        f"Session started: {timestamp} | Model: {model}",
        "",
    ]

    # --- Git state -------------------------------------------------------
    in_repo = run_git(["rev-parse", "--is-inside-work-tree"], project_dir)
    if in_repo == "true":
        branch = run_git(["branch", "--show-current"], project_dir)
        status = run_git(["status", "--short"], project_dir)
        log = run_git(["log", "--oneline", "-5"], project_dir)

        lines += ["## Git State", f"Branch: {branch}"]
        if status:
            lines += [f"Uncommitted changes:\n```\n{status}\n```"]
        else:
            lines.append("Working tree: clean")
        lines += [f"Recent commits:\n```\n{log}\n```", ""]

    # --- Accumulated learning insights -----------------------------------
    insights_file = learning_dir / "insights.md"
    if insights_file.exists() and insights_file.stat().st_size > 0:
        lines += ["## Accumulated Learning Insights", insights_file.read_text(), ""]

    # --- Autonomy guidelines ---------------------------------------------
    lines += [
        "## Autonomous Operation Guidelines",
        "- Tests MUST pass before you stop (enforced by Stop hook)",
        "- Safe operations are auto-approved; no permission prompts needed",
        "- Run /compact if context approaches 50% (context_monitor will warn)",
        "- Learning insights are auto-saved to .claude/learning/insights.md",
    ]

    # --- Log session start -----------------------------------------------
    session_log = learning_dir / "session_log.jsonl"
    with session_log.open("a") as f:
        f.write(
            json.dumps({"event": "session_start", "source": source, "model": model, "ts": timestamp})
            + "\n"
        )

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": "\n".join(lines),
                }
            }
        )
    )


if __name__ == "__main__":
    main()
