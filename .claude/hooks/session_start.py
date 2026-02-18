#!/usr/bin/env python3
"""SessionStart hook — injects git state and learning insights into context."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", "-C", str(cwd)] + args, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def build_git_section(project_dir: Path) -> list[str]:
    if run_git(["rev-parse", "--is-inside-work-tree"], project_dir) != "true":
        return []

    branch = run_git(["branch", "--show-current"], project_dir)
    status = run_git(["status", "--short"], project_dir)
    recent_commits = run_git(["log", "--oneline", "-5"], project_dir)

    lines = ["## Git State", f"Branch: {branch}"]
    lines += [f"Uncommitted changes:\n```\n{status}\n```"] if status else ["Working tree: clean"]
    lines += [f"Recent commits:\n```\n{recent_commits}\n```", ""]
    return lines


def build_insights_section(learning_dir: Path) -> list[str]:
    insights_file = learning_dir / "insights.md"
    if not insights_file.exists() or insights_file.stat().st_size == 0:
        return []
    return ["## Accumulated Learning Insights", insights_file.read_text(), ""]


def autonomy_guidelines() -> list[str]:
    return [
        "## Autonomous Operation Guidelines",
        "- Tests MUST pass before you stop (enforced by Stop hook)",
        "- Safe operations are auto-approved; no permission prompts needed",
        "- Run /compact if context approaches 50% (context_monitor will warn)",
        "- Learning insights are auto-saved to .claude/learning/insights.md",
    ]


def main() -> None:
    input_data = json.loads(sys.stdin.read())

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    learning_dir = project_dir / ".claude" / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    source = input_data.get("source", "startup")
    model = input_data.get("model", "unknown")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    context_lines = [
        f"# Automated Session Context ({source})",
        f"Session started: {timestamp} | Model: {model}",
        "",
        *build_git_section(project_dir),
        *build_insights_section(learning_dir),
        *autonomy_guidelines(),
    ]

    session_log = learning_dir / "session_log.jsonl"
    with session_log.open("a") as f:
        f.write(json.dumps({"event": "session_start", "source": source, "model": model, "ts": timestamp}) + "\n")

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(context_lines),
        }
    }))


if __name__ == "__main__":
    main()
