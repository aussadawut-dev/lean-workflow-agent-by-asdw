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

# busy_stop <reason>: the gate lock is held (or unusable), so the runner exited before it could count
# a refusal. Count it here with the runner's refuse() arithmetic and marker, so a busy gate blocks at
# most max_refusals continued Stops and then releases UNVERIFIED; never a pass, cache or receipt.
busy_stop() {
  local active=0 n=0 action=block max_refusals=3 failed="$root/.claude/.gate-failed"
  active="$(printf '%s' "$input" | python3 -c 'import json, sys
print("1" if json.load(sys.stdin).get("stop_hook_active") is True else "0")' 2>/dev/null)" || active=0
  if [ "$active" -eq 1 ]; then
    n="$(cat "$failed" 2>/dev/null)"
    n="${n#c}"
    case "$n" in ''|*[!0-9]*) n=0 ;; esac
  fi
  n=$((n + 1))
  [ "$n" -le "$max_refusals" ] || action=release
  # An unwritable marker cannot bound a continued Stop, so release it rather than loop.
  { mkdir -p "$root/.claude" && printf '%s' "$n" > "$failed"; } 2>/dev/null ||
    { [ "$active" -ne 1 ] || action=release; }
  [ "$action" = block ] && block "$1"
  printf '{"systemMessage":"Lean Quality Gate stayed busy (another gate is running in this checkout) after %s attempts; Stop released UNVERIFIED. Validation did not run, so the work is not DONE; report BLOCKED."}\n' "$max_refusals"
  exit 0
}

input="$(cat)"
errors="$(mktemp)" || block "Lean Quality Gate could not create a temporary file; validation NOT_RUN."
"$runner" --claude-hook --root "$root" "$@" 2>"$errors" <<<"$input"
status=$?
reason="$(cat "$errors")"
rm -f "$errors"
if [ "$status" -eq 2 ]; then
  case "$reason" in
    "Quality Gate busy"*|"Quality Gate lock unavailable"*) busy_stop "$reason" ;;
  esac
  block "$reason"
fi
[ -z "$reason" ] || printf '%s\n' "$reason" >&2
exit "$status"
