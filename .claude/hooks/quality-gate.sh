#!/usr/bin/env bash
# Quality Gate hook (Stop event).
# Runs the commands between the gate markers in .lean/PROJECT.md.
# No commands defined -> no-op. Failure -> exit 2, which blocks Claude
# from finishing and returns the output to it.

set -u

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
project="$root/.lean/PROJECT.md"
cache="$root/.claude/.gate-cache"

input="$(cat)"

# Already continuing because of this hook: do not loop.
if printf '%s' "$input" | grep -Eq '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
  exit 0
fi

[ -f "$project" ] || exit 0

commands="$(awk '
  /<!-- gate:start -->/ { on = 1; next }
  /<!-- gate:end -->/   { on = 0 }
  on && !/^```/ && !/^[[:space:]]*(#|$)/ { print }
' "$project")"

[ -n "$commands" ] || exit 0

cd "$root" || exit 0

# Skip when nothing changed since the last passing run.
state=""
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ -z "$(git status --porcelain)" ]; then
    exit 0
  fi
  state="$( { printf '%s\n' "$commands"; git rev-parse HEAD 2>/dev/null; git diff HEAD 2>/dev/null; git status --porcelain; git ls-files --others --exclude-standard -z | xargs -0 cat 2>/dev/null; } | cksum)"
  if [ -f "$cache" ] && [ "$(cat "$cache")" = "$state" ]; then
    exit 0
  fi
fi

while IFS= read -r cmd; do
  if ! output="$(bash -c "$cmd" 2>&1)"; then
    {
      echo "Quality Gate failed: $cmd"
      printf '%s\n' "$output" | tail -n 40
      echo "If your change caused this, fix it. If it was already failing or is outside the task, do not touch it: report BLOCKED and ask. Do not declare DONE."
    } >&2
    rm -f "$cache"
    exit 2
  fi
done <<< "$commands"

[ -n "$state" ] && printf '%s' "$state" > "$cache"
exit 0
