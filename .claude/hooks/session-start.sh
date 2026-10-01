#!/usr/bin/env bash
# SessionStart hook: stdout is added to Claude's context.
# States the workflow mode when it asks for more than the baseline, and asks for
# one when none is recorded. Nudges toward /lean-init while PROJECT.md is still
# the empty template, and seeds the Quality Gate cache so a session that changes
# nothing does not run the gate at its first turn end.

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
project="$root/.lean/PROJECT.md"
mode_script="$root/.lean/bin/mode.sh"

# Kept quiet on purpose: this hook's stdout becomes Claude's context.
"$(dirname "$0")/quality-gate.sh" --seed >/dev/null 2>&1 || true

[ -f "$project" ] || exit 0

# `standard` says nothing: it is the workflow as written, and every line here is
# context every session pays for. An empty reading means mode.sh is gone -- a
# project that removed it is not asked about a mode it cannot record.
mode=""
[ -x "$mode_script" ] && mode="$("$mode_script" get 2>/dev/null)"

case "$mode" in
  "" | standard) ;;
  tracker)
    echo "Lean Workflow mode: tracker. Every non-trivial task also gets a tracking record under .lean/tracker/. See .lean/policy/MODES.md."
    ;;
  full)
    echo "Lean Workflow mode: full. Every non-trivial task is a claimed queue item (.lean/bin/queue.sh) plus a tracking record under .lean/tracker/. See .lean/policy/MODES.md."
    ;;
  unset)
    echo "Lean Workflow: no workflow mode is recorded. Before changing any file, ask the user which one this project runs -- standard (the workflow as written), tracker (adds one tracking record per task), full (adds a claimed task queue on top) -- then record the answer with .lean/bin/mode.sh set <mode>. Ask once: after that it is config, changed by editing .lean/PROJECT.md. What each mode adds: .lean/policy/MODES.md."
    ;;
  *)
    echo "Lean Workflow: the workflow mode recorded in .lean/PROJECT.md is '$mode', which is not standard, tracker, or full. Ask the user which one is meant and record it with .lean/bin/mode.sh set <mode>."
    ;;
esac

if grep -A2 '^## Purpose' "$project" | grep -q 'Not defined yet'; then
  echo "Lean Workflow: .lean/PROJECT.md is not filled in yet. If the repository has code, suggest running /lean-init once."
fi
exit 0
