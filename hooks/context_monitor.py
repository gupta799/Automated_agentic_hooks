#!/usr/bin/env python3
"""UserPromptSubmit hook — monitors context size and triggers /compact when needed."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_config(project_dir: Path) -> dict:
    config_file = project_dir / ".claude" / "hooks" / "config.json"
    try:
        return json.loads(config_file.read_text()) if config_file.exists() else {}
    except json.JSONDecodeError:
        return {}


def hook_output(message: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": message,
        }
    })


def main() -> None:
    input_data = json.loads(sys.stdin.read())

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    config = load_config(project_dir)
    learning_dir = project_dir / ".claude" / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    warn_kb: int = config.get("context_warn_threshold_kb", 300)
    compact_kb: int = config.get("context_compact_threshold_kb", 400)
    full_kb: int = config.get("context_full_window_kb", 800)

    transcript_path = input_data.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    transcript = Path(transcript_path)
    if not transcript.exists():
        sys.exit(0)

    context_kb = transcript.stat().st_size // 1024
    context_pct = (context_kb * 100) // full_kb
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if context_kb > warn_kb:
        with (learning_dir / "context_log.jsonl").open("a") as f:
            f.write(json.dumps({"ts": timestamp, "kb": context_kb, "pct": context_pct}) + "\n")

    if context_kb >= compact_kb:
        print(hook_output(
            f"[AUTOMATED SELF-COMPACTION TRIGGER] Context window is at approximately "
            f"{context_pct}% capacity ({context_kb}KB / {full_kb}KB estimated). "
            "Before responding to the user's request, you MUST run /compact to compress "
            "the conversation history. After compaction completes, proceed normally."
        ))
        return

    if context_kb >= warn_kb:
        print(hook_output(
            f"[Context Monitor] Context is at ~{context_pct}% ({context_kb}KB). "
            "Consider running /compact soon to maintain performance."
        ))


if __name__ == "__main__":
    main()
