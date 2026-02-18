#!/usr/bin/env python3
"""
CONTEXT MONITOR HOOK
Fires on: UserPromptSubmit (every user message)
Purpose:  Estimate context window fill from the transcript file size and
          inject an instruction for Claude to run /compact before the
          window fills up.  Implements automated self-compaction with
          zero human involvement.

Token / size mapping:
  claude-sonnet-4-6 has a 200K token context window.
  Each token ≈ 4 bytes on average in JSON transcripts.
  Full window ≈ 800 KB.  50% threshold ≈ 400 KB.

Thresholds are read from .claude/hooks/config.json:
  context_warn_threshold_kb     (default 300 KB ≈ 37%)
  context_compact_threshold_kb  (default 400 KB ≈ 50%)
  context_full_window_kb        (default 800 KB = 100%)
"""

import json
import os
import sys
from datetime import datetime, timezone
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

    warn_kb: int = config.get("context_warn_threshold_kb", 300)
    compact_kb: int = config.get("context_compact_threshold_kb", 400)
    full_kb: int = config.get("context_full_window_kb", 800)

    transcript_path: str = input_data.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    transcript = Path(transcript_path)
    if not transcript.exists():
        sys.exit(0)

    context_kb = transcript.stat().st_size // 1024
    context_pct = (context_kb * 100) // full_kb
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Log when above warning threshold (reduce noise below it) --------
    if context_kb > warn_kb:
        context_log = learning_dir / "context_log.jsonl"
        with context_log.open("a") as f:
            f.write(json.dumps({"ts": timestamp, "kb": context_kb, "pct": context_pct}) + "\n")

    # --- At or above compact threshold: mandatory /compact instruction ---
    if context_kb >= compact_kb:
        msg = (
            f"[AUTOMATED SELF-COMPACTION TRIGGER] Context window is at approximately "
            f"{context_pct}% capacity ({context_kb}KB / {full_kb}KB estimated). "
            "Before responding to the user's request, you MUST run /compact to compress "
            "the conversation history. After compaction completes, proceed normally."
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": msg,
            }
        }))
        return

    # --- Warning zone: soft suggestion -----------------------------------
    if context_kb >= warn_kb:
        msg = (
            f"[Context Monitor] Context is at ~{context_pct}% ({context_kb}KB). "
            "Consider running /compact soon to maintain performance."
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": msg,
            }
        }))
        return


if __name__ == "__main__":
    main()
