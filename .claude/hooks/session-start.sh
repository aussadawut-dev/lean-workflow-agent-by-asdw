#!/usr/bin/env bash
# SessionStart hook: stdout is added to Claude's context.
# Nudges toward /lean-init while PROJECT.md is still the empty template, and
# seeds the Quality Gate cache so a session that changes nothing does not run
# the gate at its first turn end.

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
project="$root/.lean/PROJECT.md"
config="$root/.lean/config.json"

# Kept quiet on purpose: this hook's stdout becomes Claude's context.
"$(dirname "$0")/quality-gate.sh" --seed >/dev/null 2>&1 || true

if [ ! -f "$config" ] || grep -q '"configured"[[:space:]]*:[[:space:]]*false' "$config"; then
  echo "Lean Workflow: choose standard, tracker, or full with /lean-init; direct execution is the default, delegated is optional."
fi

[ -f "$project" ] || exit 0

if grep -A2 '^## Purpose' "$project" | grep -q 'Not defined yet'; then
  echo "Lean Workflow: .lean/PROJECT.md is not filled in yet. If the repository has code, suggest running /lean-init once."
fi
exit 0
