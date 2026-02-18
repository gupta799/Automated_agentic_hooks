#!/bin/bash
# ============================================================
# SESSION START HOOK
# Fires on: startup, resume, compact
# Purpose:  Inject rich context (git state, learned insights,
#           environment) so Claude operates autonomously with
#           full awareness from the first turn.
# ============================================================

CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LEARNING_DIR="$CLAUDE_PROJECT_DIR/.claude/learning"
INSIGHTS_FILE="$LEARNING_DIR/insights.md"
SESSION_LOG="$LEARNING_DIR/session_log.jsonl"

mkdir -p "$LEARNING_DIR"

INPUT=$(cat)
SOURCE=$(echo "$INPUT" | jq -r '.source // "startup"')
MODEL=$(echo "$INPUT" | jq -r '.model // "unknown"')
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

CONTEXT="# Automated Session Context (${SOURCE})\n"
CONTEXT+="Session started: ${TIMESTAMP} | Model: ${MODEL}\n\n"

# --- Git state ---
if git -C "$CLAUDE_PROJECT_DIR" rev-parse --is-inside-work-tree 2>/dev/null; then
  GIT_BRANCH=$(git -C "$CLAUDE_PROJECT_DIR" branch --show-current 2>/dev/null)
  GIT_STATUS=$(git -C "$CLAUDE_PROJECT_DIR" status --short 2>/dev/null | head -20)
  GIT_LOG=$(git -C "$CLAUDE_PROJECT_DIR" log --oneline -5 2>/dev/null)
  STASH_COUNT=$(git -C "$CLAUDE_PROJECT_DIR" stash list 2>/dev/null | wc -l)

  CONTEXT+="## Git State\n"
  CONTEXT+="Branch: ${GIT_BRANCH}\n"
  if [ -n "$GIT_STATUS" ]; then
    CONTEXT+="Uncommitted changes:\n\`\`\`\n${GIT_STATUS}\n\`\`\`\n"
  else
    CONTEXT+="Working tree: clean\n"
  fi
  CONTEXT+="Recent commits:\n\`\`\`\n${GIT_LOG}\n\`\`\`\n"
  [ "$STASH_COUNT" -gt 0 ] && CONTEXT+="Stashes: ${STASH_COUNT}\n"
  CONTEXT+="\n"
fi

# --- Test suite status ---
if [ -f "$CLAUDE_PROJECT_DIR/package.json" ] && jq -e '.scripts.test' "$CLAUDE_PROJECT_DIR/package.json" >/dev/null 2>&1; then
  CONTEXT+="## Project\nTest runner: npm test\n\n"
elif [ -f "$CLAUDE_PROJECT_DIR/Makefile" ] && grep -q "^test:" "$CLAUDE_PROJECT_DIR/Makefile"; then
  CONTEXT+="## Project\nTest runner: make test\n\n"
elif [ -f "$CLAUDE_PROJECT_DIR/pytest.ini" ] || [ -f "$CLAUDE_PROJECT_DIR/pyproject.toml" ]; then
  CONTEXT+="## Project\nTest runner: pytest\n\n"
fi

# --- Accumulated learning insights ---
if [ -f "$INSIGHTS_FILE" ] && [ -s "$INSIGHTS_FILE" ]; then
  CONTEXT+="## Accumulated Learning Insights\n"
  CONTEXT+=$(cat "$INSIGHTS_FILE")
  CONTEXT+="\n\n"
fi

# --- Autonomy reminders ---
CONTEXT+="## Autonomous Operation Guidelines\n"
CONTEXT+="- Tests MUST pass before you stop (enforced by Stop hook)\n"
CONTEXT+="- Permissions for safe operations are auto-approved (no need to ask)\n"
CONTEXT+="- Run /compact if context usage approaches 50% (context_monitor will warn)\n"
CONTEXT+="- Learning insights are auto-saved to .claude/learning/insights.md\n"

# --- Log session start ---
echo "{\"event\":\"session_start\",\"source\":\"${SOURCE}\",\"model\":\"${MODEL}\",\"ts\":\"${TIMESTAMP}\"}" >> "$SESSION_LOG"

# Output additionalContext for Claude
jq -n --arg ctx "$CONTEXT" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'
