#!/bin/bash
# ============================================================
# STOP TEST GUARD HOOK
# Fires on: Stop event (when Claude finishes responding)
# Purpose:  Run the test suite before allowing Claude to stop.
#           If tests fail, exit 2 to block stopping and feed
#           the failure output back to Claude as an error so
#           it automatically fixes the issue.
#
# Also checks: context size, triggering /compact if > 50%.
#
# Exit codes:
#   0  - allow Claude to stop (all checks pass)
#   2  - BLOCK stopping; stderr is fed to Claude as feedback
# ============================================================

INPUT=$(cat)
CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""')
LEARNING_DIR="$CLAUDE_PROJECT_DIR/.claude/learning"

mkdir -p "$LEARNING_DIR"

# ── Infinite-loop guard ───────────────────────────────────────
# stop_hook_active=true means we are ALREADY in a stop-hook
# continuation. Allow stopping to avoid runaway loops.
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# ── Context-size check (self-compact at ~50%) ─────────────────
# Heuristic: transcript file size as proxy for token usage.
# claude-sonnet-4-6 has a 200K token context window.
# 200K tokens ≈ 800 KB of raw JSON transcript.
# 50% threshold ≈ 400 KB.
COMPACT_TRIGGERED=false
CONTEXT_KB=0
if [ -f "$TRANSCRIPT_PATH" ]; then
  CONTEXT_KB=$(du -k "$TRANSCRIPT_PATH" 2>/dev/null | cut -f1)
  COMPACT_THRESHOLD_KB=400   # ~50% of 200K token window

  if [ "${CONTEXT_KB:-0}" -gt "$COMPACT_THRESHOLD_KB" ]; then
    COMPACT_TRIGGERED=true
    CONTEXT_PCT=$(( CONTEXT_KB * 100 / 800 ))
    echo "AUTOMATED SELF-COMPACT: Context is approximately ${CONTEXT_PCT}% full (${CONTEXT_KB}KB transcript). Run /compact now to compress context before the window fills. After compacting, continue your work." >&2
    # Log the event
    echo "{\"event\":\"auto_compact_triggered\",\"context_kb\":${CONTEXT_KB},\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >> "$LEARNING_DIR/session_log.jsonl"
    exit 2  # Block stopping → Claude sees message → runs /compact
  fi
fi

# ── Test suite runner ─────────────────────────────────────────
cd "$CLAUDE_PROJECT_DIR" || exit 0

RAN_TESTS=false
TEST_FAILED=false
TEST_OUTPUT=""

# Delegate to the project-aware test runner script
if [ -f "$CLAUDE_PROJECT_DIR/.claude/hooks/run_tests.sh" ]; then
  TEST_OUTPUT=$(bash "$CLAUDE_PROJECT_DIR/.claude/hooks/run_tests.sh" 2>&1)
  TEST_EXIT=$?
  RAN_TESTS=true
  [ $TEST_EXIT -ne 0 ] && TEST_FAILED=true
fi

# ── Block on failure ──────────────────────────────────────────
if [ "$TEST_FAILED" = "true" ]; then
  {
    echo "TEST GATE FAILED — fix before stopping."
    echo ""
    echo "--- Test Output ---"
    echo "$TEST_OUTPUT"
    echo "-------------------"
    echo ""
    echo "Address the failures above, then you will be allowed to stop."
  } >&2
  exit 2
fi

# ── Log successful stop ───────────────────────────────────────
echo "{\"event\":\"stop_allowed\",\"ran_tests\":${RAN_TESTS},\"context_kb\":${CONTEXT_KB:-0},\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >> "$LEARNING_DIR/session_log.jsonl"

exit 0
