#!/bin/bash
# ============================================================
# LEARNING LOGGER HOOK  (async — does NOT block Claude)
# Fires on: PostToolUse for Bash, Write, Edit
# Purpose:  Accumulate structured logs of tool usage and
#           surface recurring patterns as learning insights
#           that are re-injected on the next SessionStart.
#
# Async mode: output via systemMessage is delivered to Claude
#             on the next turn if there is something notable.
# ============================================================

INPUT=$(cat)
CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LEARNING_DIR="$CLAUDE_PROJECT_DIR/.claude/learning"
TOOL_LOG="$LEARNING_DIR/tool_log.jsonl"
INSIGHTS_FILE="$LEARNING_DIR/insights.md"
PATTERN_LOG="$LEARNING_DIR/pattern_log.jsonl"

mkdir -p "$LEARNING_DIR"

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# ── Log this tool use ─────────────────────────────────────────
case "$TOOL_NAME" in
  "Bash")
    CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
    EXIT_STATUS=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0')
    echo "{\"ts\":\"${TIMESTAMP}\",\"tool\":\"Bash\",\"cmd\":$(echo "$INPUT" | jq '.tool_input.command // ""'),\"exit\":${EXIT_STATUS}}" >> "$TOOL_LOG"
    ;;
  "Write"|"Edit")
    FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')
    echo "{\"ts\":\"${TIMESTAMP}\",\"tool\":\"${TOOL_NAME}\",\"file\":$(echo "$INPUT" | jq '.tool_input.file_path // ""')}" >> "$TOOL_LOG"
    ;;
esac

# ── Keep tool log bounded (last 500 entries) ──────────────────
if [ -f "$TOOL_LOG" ]; then
  LINE_COUNT=$(wc -l < "$TOOL_LOG")
  if [ "$LINE_COUNT" -gt 500 ]; then
    tail -400 "$TOOL_LOG" > "${TOOL_LOG}.tmp" && mv "${TOOL_LOG}.tmp" "$TOOL_LOG"
  fi
fi

# ── Pattern detection and insight generation ──────────────────
# Count how many times each Bash command prefix has been run
# and surface recurring patterns as insights.

if [ -f "$TOOL_LOG" ]; then
  # Extract common command prefixes (first word of each bash command)
  TOP_CMDS=$(jq -r 'select(.tool=="Bash") | .cmd' "$TOOL_LOG" 2>/dev/null \
    | awk '{print $1}' \
    | sort | uniq -c | sort -rn \
    | head -5 \
    | awk '{print "- " $2 " (" $1 " uses)"}')

  # Count file types written/edited most
  TOP_FILES=$(jq -r 'select(.tool=="Write" or .tool=="Edit") | .file' "$TOOL_LOG" 2>/dev/null \
    | sed 's/.*\.//' \
    | sort | uniq -c | sort -rn \
    | head -5 \
    | awk '{print "- ." $2 " (" $1 " edits)"}')

  # Write aggregated insights (overwrite to keep current)
  TOTAL_BASH=$(jq -r 'select(.tool=="Bash")' "$TOOL_LOG" 2>/dev/null | wc -l)
  TOTAL_WRITES=$(jq -r 'select(.tool=="Write" or .tool=="Edit")' "$TOOL_LOG" 2>/dev/null | wc -l)

  cat > "$INSIGHTS_FILE" <<EOF
# Automated Learning Insights
_Last updated: ${TIMESTAMP}_

## Session Statistics
- Bash commands executed: ${TOTAL_BASH}
- Files written/edited: ${TOTAL_WRITES}

## Most Used Commands
${TOP_CMDS:-_No data yet_}

## Most Edited File Types
${TOP_FILES:-_No data yet_}

## Behaviour Notes
- Auto-permissions active: safe read/write operations bypass prompts
- Test gate active: tests run automatically before each Stop
- Context monitor active: /compact triggered if context > 50%
EOF
fi

exit 0
