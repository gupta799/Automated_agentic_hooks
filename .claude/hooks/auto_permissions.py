#!/usr/bin/env python3
"""
AUTO PERMISSIONS HOOK
Fires on: PermissionRequest event
Purpose:  Reduce human-in-the-loop by automatically:
            DENY  — destructive / privilege-escalation commands
            ALLOW — safe read-only and standard dev operations
            pass  — everything else falls through to the normal dialog

Policy tables (DENY_PATTERNS, SAFE_BASH_PATTERNS, SENSITIVE_PATHS)
can be edited below to suit your project's security requirements.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# ── Security policy tables ────────────────────────────────────────────────

# Bash commands that are ALWAYS blocked
DENY_PATTERNS: list[str] = [
    r"rm\s+-[rfRF]*[fF]",           # rm -rf / rm -fr
    r"sudo\s+rm",                   # sudo rm
    r":\s*>\s*/",                   # clobber root path
    r"mkfs",                        # format filesystem
    r"dd\s+if=",                    # raw disk write
    r"chmod\s+-R\s+777",            # world-writable recursion
    r">>\s*/etc/",                  # append to system config
    r">\s*/etc/",                   # overwrite system config
    r"curl\b.+\|\s*(ba)?sh",        # pipe curl to shell
    r"wget\b.+\|\s*(ba)?sh",        # pipe wget to shell
    r"/dev/sd[a-z]",                # direct disk device access
]

# Bash command prefixes/patterns that are ALWAYS allowed
SAFE_BASH_PATTERNS: list[str] = [
    r"^git\s+(status|log|diff|branch|fetch|pull|add|commit|push|stash|tag|show|remote)",
    r"^npm\s+(install|test|run|build|ci|audit|list|pack)",
    r"^yarn\s+(install|test|run|build)",
    r"^pnpm\s+(install|test|run|build)",
    r"^ls(\s|$)",
    r"^cat\s",
    r"^echo\s",
    r"^pwd$",
    r"^which\s",
    r"^env$",
    r"^node\s",
    r"^python[23]?\s",
    r"^pip[23]?\s+(install|list|show|freeze)",
    r"^pytest(\s|$)",
    r"^make\s+(test|build|lint|clean|check|install)",
    r"^go\s+(test|build|run|vet|fmt|mod)",
    r"^cargo\s+(test|build|run|check|fmt|clippy)",
    r"^jq\s",
    r"^curl\s+-s?[Oo]?\s+https?://[^\|]+$",  # simple curl fetch, no pipe to shell
    r"^mkdir\s+-p\s",
    r"^touch\s",
    r"^cp\s",
    r"^mv\s",
    r"^chmod\s+[0-7]{3}\s",         # specific numeric permissions only
    r"^wc\s",
    r"^head\s",
    r"^tail\s",
    r"^grep\s",
    r"^find\s",
    r"^sort\s",
    r"^uniq\s",
    r"^awk\s",
    r"^sed\s",
    r"^date(\s|$)",
    r"^uname\s",
    r"^du\s",
    r"^df\s",
    r"^python3\s+.*\.py",           # run python scripts
]

# File paths that are NEVER writable
SENSITIVE_PATHS: list[str] = [
    r"^/etc/",
    r"^/sys/",
    r"^/proc/",
    r"^/boot/",
    r"^/dev/",
    r"\.env$",
    r"\.env\.",
    r"\.ssh/",
    r"\.aws/credentials",
    r"\.gnupg/",
    r"/id_rsa$",
    r"/id_ed25519$",
]


# ── Output helpers ────────────────────────────────────────────────────────

def _allow() -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "allow"},
        }
    }))


def _deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "deny", "message": reason},
        }
    }))


def _log(learning_dir: Path, tool: str, decision: str, reason: str = "") -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    perm_log = learning_dir / "permission_log.jsonl"
    with perm_log.open("a") as f:
        f.write(json.dumps({"ts": ts, "tool": tool, "decision": decision, "reason": reason}) + "\n")


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    input_data = json.loads(sys.stdin.read())

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    learning_dir = project_dir / ".claude" / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    tool_name: str = input_data.get("tool_name", "")
    tool_input: dict = input_data.get("tool_input", {})

    # --- Read-only tools: always safe ------------------------------------
    if tool_name in ("Read", "Glob", "Grep", "WebSearch", "WebFetch"):
        _log(learning_dir, tool_name, "allow")
        _allow()
        return

    # --- Task / subagent spawning: always allow --------------------------
    if tool_name == "Task":
        _log(learning_dir, tool_name, "allow")
        _allow()
        return

    # --- Bash policy -----------------------------------------------------
    if tool_name == "Bash":
        cmd: str = tool_input.get("command", "")

        for pattern in DENY_PATTERNS:
            if re.search(pattern, cmd):
                reason = f"Blocked by security policy (pattern: {pattern!r}): {cmd}"
                _log(learning_dir, tool_name, "deny", reason)
                _deny(reason)
                return

        for pattern in SAFE_BASH_PATTERNS:
            if re.match(pattern, cmd):
                _log(learning_dir, tool_name, "allow")
                _allow()
                return

    # --- Write / Edit policy ---------------------------------------------
    if tool_name in ("Write", "Edit"):
        file_path: str = tool_input.get("file_path", "")

        for pattern in SENSITIVE_PATHS:
            if re.search(pattern, file_path):
                reason = f"Write to sensitive path blocked: {file_path}"
                _log(learning_dir, tool_name, "deny", reason)
                _deny(reason)
                return

        # Allow writes inside the project directory
        try:
            Path(file_path).resolve().relative_to(project_dir.resolve())
            _log(learning_dir, tool_name, "allow")
            _allow()
            return
        except ValueError:
            pass  # Outside project dir → fall through to dialog

    # --- Default: pass through to normal permission dialog ---------------
    # (do not print anything, exit 0)


if __name__ == "__main__":
    main()
