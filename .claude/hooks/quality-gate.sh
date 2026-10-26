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
# a refusal. Count it here with the same marker and decision as the runner's refuse(), so a busy gate
# blocks at most max_refusals continued Stops and then releases UNVERIFIED; never a pass, cache or receipt.
busy_stop() {
  local active=0 previous="" decision action marker max_refusals=3 failed="$root/.claude/.gate-failed" key
  active="$(printf '%s' "$input" | python3 -c 'import json, sys
print("1" if json.load(sys.stdin).get("stop_hook_active") is True else "0")' 2>/dev/null)" || active=0
  # The marker is this session's own (keyed by session_id); no session id keeps the legacy name.
  key="$(printf '%s' "$input" | python3 -B -c 'import json, sys
sys.path.insert(0, sys.argv[1]); import lean_core
k = lean_core.session_key(json.load(sys.stdin).get("session_id"))
print(k if isinstance(k, str) else "")' "$(dirname "$runner")" 2>/dev/null)" || key=""
  case "$key" in
    ????????????????) case "$key" in *[!0123456789abcdef]*) key="" ;; esac ;;
    *) key="" ;;
  esac  # only a 16-hex-digit key may become part of a file name
  [ -z "$key" ] || failed="$root/.agent-runtime/gate-failed.$key"  # keyed markers live in the ignored runtime dir
  # If .agent-runtime is unusable (a regular file, read-only) the count falls back to the legacy
  # .claude/.gate-failed, as the runner's refuse() does, so the cap still holds where a marker can be kept.
  if [ -n "$key" ] && { ! mkdir -p "$root/.agent-runtime" 2>/dev/null || [ ! -w "$root/.agent-runtime" ]; }; then
    failed="$root/.claude/.gate-failed"
  fi
  [ "$active" -eq 1 ] && [ -f "$failed" ] && previous="$(cat "$failed" 2>/dev/null)"
  if decision="$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import lean_core
action, marker = lean_core.gate_refusal(sys.argv[2], sys.argv[3] == "1", False, False)
print(action, marker)' "$(dirname "$runner")" "$previous" "$active" 2>/dev/null)" && [ -n "$decision" ]; then
    action="${decision%% *}"
    marker="${decision#* }"
  elif [ "$active" -eq 1 ]; then
    action=release_capped marker="$((max_refusals + 1))"
  else
    action=block marker=1
  fi
  # An unwritable marker cannot bound a continued Stop, so release it rather than loop.
  # (A marker path that is a directory or other non-regular file is unusable too.)
  { { [ ! -e "$failed" ] && [ ! -L "$failed" ] || [ -f "$failed" ]; } &&
    mkdir -p "$(dirname "$failed")" && printf '%s' "$marker" > "$failed"; } 2>/dev/null ||
    { [ "$active" -ne 1 ] || action=release_capped; }
  [ "$action" = block ] && block "$1"
  case "$1" in
    "Quality Gate lock unavailable"*)
      printf '{"systemMessage":"Lean Quality Gate could not take its lock (gate lock unavailable in this checkout) after %s attempts; Stop released UNVERIFIED. Validation did not run, so the work is not DONE; report BLOCKED."}\n' "$max_refusals" ;;
    *)
      printf '{"systemMessage":"Lean Quality Gate stayed busy (another gate is running in this checkout) after %s attempts; Stop released UNVERIFIED. Validation did not run, so the work is not DONE; report BLOCKED."}\n' "$max_refusals" ;;
  esac
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
