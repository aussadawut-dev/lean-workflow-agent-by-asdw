#!/usr/bin/env bash
# Claude Stop adapter; execution and verdicts live in the shared runner.
exec "$(dirname "$0")/../../.lean/scripts/quality-gate.sh" \
  --claude-hook --root "${CLAUDE_PROJECT_DIR:-$(pwd)}" "$@"
