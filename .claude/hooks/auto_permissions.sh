#!/bin/bash
# ============================================================
# AUTO PERMISSIONS HOOK
# Fires on: PermissionRequest event
# Purpose:  Reduce human-in-the-loop by automatically allowing
#           safe operations and blocking known-dangerous ones.
#           Uses policy tiers: ALLOW / DENY / pass-through.
#
# Policy tiers (edit DENY_PATTERNS / SAFE_BASH_PATTERNS below):
#   DENY  → immediately blocked, reason shown to Claude
#   ALLOW → immediately approved, no user prompt shown
#   else  → normal permission dialog shown to user
# ============================================================

INPUT=$(cat)
CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')
LEARNING_DIR="$CLAUDE_PROJECT_DIR/.claude/learning"
PERM_LOG="$LEARNING_DIR/permission_log.jsonl"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

mkdir -p "$LEARNING_DIR"

deny() {
  local reason="$1"
  echo "{\"ts\":\"${TIMESTAMP}\",\"tool\":\"${TOOL_NAME}\",\"decision\":\"deny\",\"reason\":$(echo -n "$reason" | jq -Rs .)}" >> "$PERM_LOG"
  jq -n --arg reason "$reason" '{
    hookSpecificOutput: {
      hookEventName: "PermissionRequest",
      decision: {
        behavior: "deny",
        message: $reason
      }
    }
  }'
  exit 0
}

allow() {
  echo "{\"ts\":\"${TIMESTAMP}\",\"tool\":\"${TOOL_NAME}\",\"decision\":\"allow\"}" >> "$PERM_LOG"
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PermissionRequest",
      decision: { behavior: "allow" }
    }
  }'
  exit 0
}

# ── Read-only tools: always safe ──────────────────────────────
case "$TOOL_NAME" in
  "Read"|"Glob"|"Grep"|"WebSearch"|"WebFetch")
    allow
    ;;
esac

# ── Bash command policy ───────────────────────────────────────
if [ "$TOOL_NAME" = "Bash" ]; then
  CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

  # --- DENY: destructive / privilege-escalation patterns ---
  DENY_PATTERNS=(
    'rm\s+-[rfR]*f'          # rm -rf / rm -fr
    'sudo\s+rm'              # sudo rm
    ':\s*>\s*/'              # clobber root path
    'mkfs'                   # format filesystem
    'dd\s+if='               # raw disk write
    'chmod\s+-R\s+777'       # world-writable recursion
    '>>\s*/etc/'             # append to system config
    '>\s*/etc/'              # overwrite system config
    'curl.*\|\s*(ba)?sh'     # pipe curl to shell
    'wget.*\|\s*(ba)?sh'     # pipe wget to shell
    'eval\s*"\$\('           # eval with subshell (injection risk)
    '/dev/sd[a-z]'           # direct disk device access
  )

  for pattern in "${DENY_PATTERNS[@]}"; do
    if echo "$CMD" | grep -qE "$pattern"; then
      deny "Blocked by security policy (pattern: ${pattern}): ${CMD}"
    fi
  done

  # --- ALLOW: safe read-only and standard dev commands ---
  SAFE_BASH_PATTERNS=(
    '^git\s+(status|log|diff|branch|fetch|pull|add|commit|push|stash|tag)'
    '^npm\s+(install|test|run|build|ci|audit|list)'
    '^yarn\s+(install|test|run|build)'
    '^pnpm\s+(install|test|run|build)'
    '^ls(\s|$)'
    '^cat\s'
    '^echo\s'
    '^pwd$'
    '^which\s'
    '^env$'
    '^node\s'
    '^python[23]?\s'
    '^pip[23]?\s+(install|list|show|freeze)'
    '^pytest'
    '^make\s+(test|build|lint|clean|check)'
    '^go\s+(test|build|run|vet|fmt)'
    '^cargo\s+(test|build|run|check|fmt|clippy)'
    '^jq\s'
    '^curl\s+-s?[Oo]?\s+https?://'   # simple curl fetch (no pipe to shell)
    '^mkdir\s+-p\s'
    '^touch\s'
    '^cp\s'
    '^mv\s'
    '^chmod\s+[0-7][0-7][0-7]\s'     # specific numeric permissions only
    '^wc\s'
    '^head\s'
    '^tail\s'
    '^grep\s'
    '^find\s'
    '^sort\s'
    '^uniq\s'
    '^awk\s'
    '^sed\s'
    '^date\s'
    '^uname\s'
    '^du\s'
    '^df\s'
  )

  for pattern in "${SAFE_BASH_PATTERNS[@]}"; do
    if echo "$CMD" | grep -qE "$pattern"; then
      allow
    fi
  done
fi

# ── Write / Edit file policy ──────────────────────────────────
if [ "$TOOL_NAME" = "Write" ] || [ "$TOOL_NAME" = "Edit" ]; then
  FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

  # DENY writes to sensitive system paths
  SENSITIVE_PATHS=(
    '^/etc/'
    '^/sys/'
    '^/proc/'
    '^/boot/'
    '^/dev/'
    '\.env$'
    '\.ssh/'
    '\.aws/credentials'
    '\.gnupg/'
    '/id_rsa'
    '/id_ed25519'
  )

  for path_pattern in "${SENSITIVE_PATHS[@]}"; do
    if echo "$FILE" | grep -qE "$path_pattern"; then
      deny "Write to sensitive path blocked by security policy: ${FILE}"
    fi
  done

  # ALLOW writes inside the project directory
  if [[ "$FILE" == "$CLAUDE_PROJECT_DIR"/* ]] || [[ "$FILE" == ./* ]] || [[ "$FILE" != /* ]]; then
    allow
  fi
fi

# ── Task / subagent spawning: always allow ────────────────────
if [ "$TOOL_NAME" = "Task" ]; then
  allow
fi

# ── Default: pass through to normal permission dialog ─────────
exit 0
