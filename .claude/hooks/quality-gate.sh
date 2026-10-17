#!/usr/bin/env bash
# Claude Stop adapter; execution and verdicts live in the shared runner.
# A Stop refusal is reported as JSON {"decision":"block"} on exit 0: headless
# `claude -p` only feeds a Stop reason back to the model in that form, and treats
# exit 2 as a hook error. SessionStart seeding keeps the runner's exit codes.
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
seed=0
for option in "$@"; do
  [ "$option" != "--seed" ] || seed=1
done

# block <reason>: refuse this Stop with a reason the model sees.
block() {
  printf '%s' "$1" | python3 -c 'import json, sys
reason = sys.stdin.read()[-12000:].strip() or "Lean Quality Gate refused; report BLOCKED and do not declare DONE."
print(json.dumps({"decision": "block", "reason": reason}))' && exit 0
  printf '%s\n' "$1" >&2
  exit 2
}

if [ "$seed" -eq 0 ]; then
  policy="$(python3 "$(dirname "$0")/../../.lean/scripts/gate_mode.py" --root "$root" --check-auto 2>&1)"
  status=$?
  case "$status" in
    0) ;;
    3) if [ -z "${CLAUDE_GATE_FORCE:-}" ]; then printf '%s\n' "$policy" >&2; exit 0; fi ;;
    *) block "$policy" ;;
  esac
fi
runner="$(dirname "$0")/../../.lean/scripts/quality-gate.sh"
[ "$seed" -eq 0 ] || exec "$runner" --claude-hook --root "$root" "$@"

errors="$(mktemp)" || block "Lean Quality Gate could not create a temporary file; validation NOT_RUN."
"$runner" --claude-hook --root "$root" "$@" 2>"$errors"
status=$?
reason="$(cat "$errors")"
rm -f "$errors"
[ "$status" -ne 2 ] || block "$reason"
[ -z "$reason" ] || printf '%s\n' "$reason" >&2
exit "$status"
