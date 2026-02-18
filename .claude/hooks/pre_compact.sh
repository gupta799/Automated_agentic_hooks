#!/bin/bash
# ============================================================
# PRE-COMPACT HOOK
# Fires on: PreCompact event (before /compact or auto-compact)
# Purpose:  Save a summary of current work and key insights
#           to persistent storage so nothing is lost during
#           context compression. Also injects compaction
#           instructions to guide what Claude retains.
# ============================================================

INPUT=$(cat)
CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LEARNING_DIR="$CLAUDE_PROJECT_DIR/.claude/learning"
INSIGHTS_FILE="$LEARNING_DIR/insights.md"
COMPACT_LOG="$LEARNING_DIR/compact_log.jsonl"
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""')
TRIGGER=$(echo "$INPUT" | jq -r '.trigger // "auto"')
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

mkdir -p "$LEARNING_DIR"

# ── Snapshot transcript stats before compaction ───────────────
MSG_COUNT=0
TRANSCRIPT_KB=0
if [ -f "$TRANSCRIPT_PATH" ]; then
  MSG_COUNT=$(wc -l < "$TRANSCRIPT_PATH" 2>/dev/null || echo 0)
  TRANSCRIPT_KB=$(du -k "$TRANSCRIPT_PATH" 2>/dev/null | cut -f1 || echo 0)
fi

# ── Log compaction event ──────────────────────────────────────
echo "{\"event\":\"pre_compact\",\"trigger\":\"${TRIGGER}\",\"msgs\":${MSG_COUNT},\"kb\":${TRANSCRIPT_KB},\"ts\":\"${TIMESTAMP}\"}" >> "$COMPACT_LOG"

# ── Persist git snapshot ──────────────────────────────────────
if git -C "$CLAUDE_PROJECT_DIR" rev-parse --is-inside-work-tree 2>/dev/null; then
  GIT_BRANCH=$(git -C "$CLAUDE_PROJECT_DIR" branch --show-current 2>/dev/null)
  GIT_STATUS=$(git -C "$CLAUDE_PROJECT_DIR" status --short 2>/dev/null)

  SNAPSHOT_FILE="$LEARNING_DIR/pre_compact_snapshot.md"
  cat > "$SNAPSHOT_FILE" <<EOF
# Pre-Compact Snapshot — ${TIMESTAMP}
Trigger: ${TRIGGER}
Branch: ${GIT_BRANCH}
Transcript: ${MSG_COUNT} lines / ${TRANSCRIPT_KB}KB

## Uncommitted Changes
\`\`\`
${GIT_STATUS:-none}
\`\`\`
EOF
fi

# ── Output compaction instructions via stdout ─────────────────
# Plain stdout is shown as hook output; also used as context.
cat <<'INSTRUCTIONS'
COMPACTION INSTRUCTIONS (automated learning system):
When compacting, prioritise retaining:
1. Current task description and acceptance criteria
2. All decisions made and their rationale
3. Errors encountered and how they were resolved
4. File paths and key code structures modified
5. Test results and remaining failures
6. Outstanding TODOs and next steps

Discard:
- Exploratory search results already acted on
- Raw tool output that led to dead ends
- Repetitive status messages
INSTRUCTIONS

exit 0
