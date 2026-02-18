# Automated Agentic Hooks

A suite of Claude Code hooks that turn Claude Code into a self-managing, persistent agent. The hooks work together as a system: context is monitored continuously, state survives compaction, test quality is enforced before stopping, and learning accumulates across sessions.

## Hooks

| Hook | Trigger | What it does |
|------|---------|-------------|
| `session_start.py` | `SessionStart` | Restores git branch, pending todos, and learning insights from previous sessions |
| `context_monitor.py` | `UserPromptSubmit` | Warns when context exceeds 50 % and injects a `/compact` instruction to prevent silent truncation |
| `pre_compact.py` | `PreCompact` | Saves current working state to `.claude/learning/` before compaction so it can be restored |
| `stop_test_guard.py` | `Stop` | Runs the configured test command; blocks Claude from stopping if tests fail and feeds results back |
| `learning_logger.py` | `PostToolUse` (Bash/Write/Edit) | Persists a structured log of commands, edited files, and patterns to `.claude/learning/insights.md` |
| `auto_permissions.py` | `PermissionRequest` | Auto-approves safe read/write operations; flags destructive operations for explicit approval |

## Install (plugin)

```bash
claude /plugin install gupta799/Automated_agentic_hooks
```

## Install (manual)

```bash
# Clone into any project that uses Claude Code
git clone https://github.com/gupta799/Automated_agentic_hooks /tmp/aah
cp -r /tmp/aah/.claude ./
```

Then merge the `hooks` block from `.claude/settings.json` into your project's `.claude/settings.json`.

## Configuration

Edit `.claude/hooks/config.json` to set your test command and thresholds:

```json
{
  "test_command": "npm test",
  "context_threshold_percent": 50,
  "auto_approve_patterns": ["cat", "ls", "grep", "rg", "find", "Read", "Glob"],
  "block_patterns": ["rm -rf", "DROP TABLE", "git push --force"]
}
```

## Requirements

- Python 3.8+
- No external dependencies

## License

MIT
