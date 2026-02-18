#!/bin/bash
# ============================================================
# CONTEXT MONITOR HOOK
# Fires on: UserPromptSubmit (every user message)
# Purpose:  Estimate context window usage from the transcript
#           file size. If usage exceeds 50%, inject an urgent
#           instruction for Claude to run /compact before
#           processing the user's request. This implements
#           automated self-compaction with no human needed.
#
# Thresholds (tunable):
#   WARN_THRESHOLD_KB  = 300 KB  ≈ 37% of 200K token window
#   COMPACT_THRESHOLD_KB = 400 KB ≈ 50% of 200K token window
#
# How token/size mapping works:
#   claude-sonnet-4-6 has a 200K token context window.
#   Each token ≈ 4 bytes on average in JSON transcripts.
#   200K tokens × 4 bytes = ~800 KB for a full transcript.
#   50% = ~400 KB.
# ============================================================

INPUT=$(cat)
CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""')
LEARNING_DIR="$CLAUDE_PROJECT_DIR/.claude/learning"
CONTEXT_LOG="$LEARNING_DIR/context_log.jsonl"

WARN_THRESHOLD_KB=300
COMPACT_THRESHOLD_KB=400
FULL_WINDOW_KB=800   # reference for % calculation

mkdir -p "$LEARNING_DIR"

# No transcript yet → nothing to check
if [ ! -f "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

CONTEXT_KB=$(du -k "$TRANSCRIPT_PATH" 2>/dev/null | cut -f1)
CONTEXT_KB="${CONTEXT_KB:-0}"
CONTEXT_PCT=$(( CONTEXT_KB * 100 / FULL_WINDOW_KB ))
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Log periodically (only when above warning threshold to reduce noise)
if [ "$CONTEXT_KB" -gt "$WARN_THRESHOLD_KB" ]; then
  echo "{\"ts\":\"${TIMESTAMP}\",\"kb\":${CONTEXT_KB},\"pct\":${CONTEXT_PCT}}" >> "$CONTEXT_LOG"
fi

# ── At or above compact threshold → instruct Claude to compact ──
if [ "$CONTEXT_KB" -ge "$COMPACT_THRESHOLD_KB" ]; then
  MSG="[AUTOMATED SELF-COMPACTION TRIGGER] Context window is at approximately ${CONTEXT_PCT}% capacity (${CONTEXT_KB}KB / ${FULL_WINDOW_KB}KB estimated). Before responding to the user's request, you MUST run /compact to compress the conversation history. After compaction completes, then proceed with the user's request normally."

  jq -n --arg msg "$MSG" '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: $msg
    }
  }'
  exit 0
fi

# ── Warning zone → softer suggestion ─────────────────────────
if [ "$CONTEXT_KB" -ge "$WARN_THRESHOLD_KB" ]; then
  MSG="[Context Monitor] Context is at ~${CONTEXT_PCT}% (${CONTEXT_KB}KB). Consider running /compact soon to maintain performance."

  jq -n --arg msg "$MSG" '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: $msg
    }
  }'
  exit 0
fi

exit 0
