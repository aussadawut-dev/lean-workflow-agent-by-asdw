#!/usr/bin/env bash
# Claude Stop adapter; execution and verdicts live in the shared runner.
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
seed=0
for option in "$@"; do
  [ "$option" != "--seed" ] || seed=1
done
if [ "$seed" -eq 0 ]; then
  policy="$(python3 "$(dirname "$0")/../../.lean/scripts/gate_mode.py" --root "$root" --check-auto)"
  status=$?
  case "$status" in
    0) ;;
    3) if [ -z "${CLAUDE_GATE_FORCE:-}" ]; then printf '%s\n' "$policy" >&2; exit 0; fi ;;
    *) exit 2 ;;
  esac
fi
exec "$(dirname "$0")/../../.lean/scripts/quality-gate.sh" \
  --claude-hook --root "$root" "$@"
