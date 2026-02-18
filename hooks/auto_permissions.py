#!/usr/bin/env python3
"""PermissionRequest hook — auto-allows safe operations, auto-denies destructive ones.

Edit DENY_PATTERNS, SAFE_BASH_PATTERNS, and SENSITIVE_PATHS to suit your project.
Anything not matched falls through to Claude's normal permission dialog.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


DENY_PATTERNS: list[str] = [
    r"rm\s+-[rfRF]*[fF]",
    r"sudo\s+rm",
    r":\s*>\s*/",
    r"mkfs",
    r"dd\s+if=",
    r"chmod\s+-R\s+777",
    r">>\s*/etc/",
    r">\s*/etc/",
    r"curl\b.+\|\s*(ba)?sh",
    r"wget\b.+\|\s*(ba)?sh",
    r"/dev/sd[a-z]",
]

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
    r"^curl\s+-s?[Oo]?\s+https?://[^\|]+$",
    r"^mkdir\s+-p\s",
    r"^touch\s",
    r"^cp\s",
    r"^mv\s",
    r"^chmod\s+[0-7]{3}\s",
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
    r"^python3\s+.*\.py",
]

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

READ_ONLY_TOOLS = {"Read", "Glob", "Grep", "WebSearch", "WebFetch"}


def permission_response(behavior: str, message: str = "") -> dict:
    decision = {"behavior": behavior}
    if message:
        decision["message"] = message
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}


def log_decision(learning_dir: Path, tool: str, decision: str, reason: str = "") -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with (learning_dir / "permission_log.jsonl").open("a") as f:
        f.write(json.dumps({"ts": ts, "tool": tool, "decision": decision, "reason": reason}) + "\n")


def main() -> None:
    input_data = json.loads(sys.stdin.read())

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    learning_dir = project_dir / ".claude" / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)

    tool_name: str = input_data.get("tool_name", "")
    tool_input: dict = input_data.get("tool_input", {})

    if tool_name in READ_ONLY_TOOLS or tool_name == "Task":
        log_decision(learning_dir, tool_name, "allow")
        print(json.dumps(permission_response("allow")))
        return

    if tool_name == "Bash":
        cmd: str = tool_input.get("command", "")

        for pattern in DENY_PATTERNS:
            if re.search(pattern, cmd):
                reason = f"Blocked by security policy (pattern: {pattern!r}): {cmd}"
                log_decision(learning_dir, tool_name, "deny", reason)
                print(json.dumps(permission_response("deny", reason)))
                return

        for pattern in SAFE_BASH_PATTERNS:
            if re.match(pattern, cmd):
                log_decision(learning_dir, tool_name, "allow")
                print(json.dumps(permission_response("allow")))
                return

    if tool_name in ("Write", "Edit"):
        file_path: str = tool_input.get("file_path", "")

        for pattern in SENSITIVE_PATHS:
            if re.search(pattern, file_path):
                reason = f"Write to sensitive path blocked: {file_path}"
                log_decision(learning_dir, tool_name, "deny", reason)
                print(json.dumps(permission_response("deny", reason)))
                return

        try:
            Path(file_path).resolve().relative_to(project_dir.resolve())
            log_decision(learning_dir, tool_name, "allow")
            print(json.dumps(permission_response("allow")))
            return
        except ValueError:
            pass


if __name__ == "__main__":
    main()
