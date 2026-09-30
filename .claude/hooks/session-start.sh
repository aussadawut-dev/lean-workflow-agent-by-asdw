#!/usr/bin/env bash
# SessionStart hook: stdout is added to Claude's context.
# Nudges toward /lean-init while PROJECT.md is still the empty template.

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
project="$root/.lean/PROJECT.md"

[ -f "$project" ] || exit 0

if grep -A2 '^## Purpose' "$project" | grep -q 'Not defined yet'; then
  echo "Lean Workflow: .lean/PROJECT.md is not filled in yet. If the repository has code, suggest running /lean-init once."
fi
exit 0
