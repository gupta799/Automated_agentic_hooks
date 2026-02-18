#!/bin/bash
# ============================================================
# RUN TESTS — Project-aware test runner
# Called by: stop_test_guard.sh
# Purpose:   Detect the project's test framework and execute
#            tests. Exits 0 on pass, non-zero on failure.
#
# Customize the "CUSTOM TEST COMMAND" section below for your
# specific project if auto-detection is insufficient.
# ============================================================

CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$CLAUDE_PROJECT_DIR" || exit 1

# ── CUSTOM TEST COMMAND (optional override) ────────────────────
# Uncomment and edit ONE of the lines below to pin a specific
# test command instead of relying on auto-detection:
#
# TEST_CMD="npm test"
# TEST_CMD="pytest -q"
# TEST_CMD="make test"
# TEST_CMD="go test ./..."
# TEST_CMD="cargo test"
# TEST_CMD="python -m unittest discover"
# ─────────────────────────────────────────────────────────────

run_cmd() {
  echo "[test-runner] $ $*"
  eval "$@"
  return $?
}

# If custom command is set, use it exclusively
if [ -n "${TEST_CMD:-}" ]; then
  run_cmd "$TEST_CMD"
  exit $?
fi

# ── Auto-detection ────────────────────────────────────────────

# Node / npm
if [ -f "package.json" ]; then
  if jq -e '.scripts.test' package.json >/dev/null 2>&1; then
    # Skip if the test script is just a placeholder
    TEST_SCRIPT=$(jq -r '.scripts.test' package.json)
    if [ "$TEST_SCRIPT" != "echo \"Error: no test specified\" && exit 1" ]; then
      run_cmd npm test
      exit $?
    fi
  fi
fi

# Python / pytest
if [ -f "pytest.ini" ] || [ -f "setup.cfg" ] || \
   ([ -f "pyproject.toml" ] && grep -q "\[tool.pytest" pyproject.toml 2>/dev/null); then
  run_cmd python -m pytest -q
  exit $?
fi

# Python / unittest (fallback)
if find . -name "test_*.py" -o -name "*_test.py" 2>/dev/null | grep -q .; then
  run_cmd python -m pytest -q 2>/dev/null || python -m unittest discover -q
  exit $?
fi

# Makefile with test target
if [ -f "Makefile" ] && grep -q "^test:" Makefile; then
  run_cmd make test
  exit $?
fi

# Go
if [ -f "go.mod" ]; then
  run_cmd go test ./...
  exit $?
fi

# Rust / cargo
if [ -f "Cargo.toml" ]; then
  run_cmd cargo test
  exit $?
fi

# Ruby / rspec
if [ -f "Gemfile" ] && command -v rspec >/dev/null 2>&1; then
  run_cmd bundle exec rspec
  exit $?
fi

# Shell tests (bats or custom)
if [ -f "tests/run.sh" ]; then
  run_cmd bash tests/run.sh
  exit $?
fi

# No test suite found → pass silently (don't block Claude)
echo "[test-runner] No test suite detected, skipping validation."
exit 0
