#!/usr/bin/env bash
# SessionStart hook: stdout is added to Claude's context.
# Nudges toward /lean-init while PROJECT.md is still the empty template, and
# records a change baseline; seeding never means validation passed.

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
project="$root/.lean/PROJECT.md"
config="$root/.lean/config.json"

# Kept quiet on purpose: this hook's stdout becomes Claude's context.
"$(dirname "$0")/quality-gate.sh" --seed >/dev/null 2>&1 || true

if [ -e "$root/.agent-runtime/active-target.json" ] || [ -L "$root/.agent-runtime/active-target.json" ]; then
  echo "Lean target context (start from the Lean root; application commands use project_root):"
  python3 "$root/.lean/scripts/submodule.py" --root "$root" context || exit 2
  echo "Read the selected project_file and target instructions. Workflow records stay in record_root. Run the target gate as well as the Lean gate."
  exit 0
fi

if [ ! -f "$config" ] || grep -q '"configured"[[:space:]]*:[[:space:]]*false' "$config"; then
  echo "Lean Workflow: choose standard, tracker, or full with /lean-init; direct execution is the default, delegated is optional."
fi

if [ ! -f "$project" ] || ! awk '
  /<!-- gate:start -->/ { on=1; next }
  /<!-- gate:end -->/ { on=0 }
  on && !/^```/ && !/^[[:space:]]*(#|$)/ { found=1 }
  END { exit !found }
' "$project"; then
  echo "Lean Quality Gate undefined: configure checks in .lean/PROJECT.md with /lean-init; no validation is enforced yet."
fi
[ -f "$project" ] || exit 0

if grep -A2 '^## Purpose' "$project" | grep -q 'Not defined yet'; then
  echo "Lean Workflow: .lean/PROJECT.md is not filled in yet. If the repository has code, suggest running /lean-init once."
fi
exit 0
