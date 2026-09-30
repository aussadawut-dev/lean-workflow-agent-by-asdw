#!/usr/bin/env bash
# Quality Gate hook (Stop event).
# Runs the commands between the gate markers in .lean/PROJECT.md.
# No commands defined -> no-op. Failure -> exit 2, which blocks Claude
# from finishing and returns the output to it. A command the shell cannot find
# exits 2 as well, because a gate that could not run is not a gate that passed,
# but it says so in its own words: the answer to it is to report the environment,
# not to repair code that nothing has actually found fault with.
#
# `--seed` records the current state and runs nothing. The SessionStart hook
# calls it, so a session that changes nothing does not run the gate at its
# first turn end. Skipping is decided by that recorded state, never by whether
# the working tree is dirty: committing makes a tree clean without making it
# validated, and the commit is part of the state, so committed work is gated.

set -u

seed=0
[ "${1:-}" = "--seed" ] && seed=1

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
project="$root/.lean/PROJECT.md"
cache="$root/.claude/.gate-cache"
failed="$root/.claude/.gate-failed"

if [ "$seed" -eq 0 ]; then
  input="$(cat)"

  # Already continuing because of this hook: do not loop.
  if printf '%s' "$input" | grep -Eq '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
    exit 0
  fi
fi

[ -f "$project" ] || exit 0

commands="$(awk '
  /<!-- gate:start -->/ { on = 1; next }
  /<!-- gate:end -->/   { on = 0 }
  on && !/^```/ && !/^[[:space:]]*(#|$)/ { print }
' "$project")"

[ -n "$commands" ] || exit 0

cd "$root" || exit 0

# Everything the gate's verdict depends on: the commands, the commit, the
# uncommitted diff, and the content of untracked files.
state=""
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  state="$( {
    printf '%s\n' "$commands"
    git rev-parse HEAD 2>/dev/null
    git diff HEAD 2>/dev/null
    git status --porcelain
    git ls-files --others --exclude-standard -z |
      while IFS= read -r -d '' f; do cat "$f" 2>/dev/null; done
  } | cksum)"
fi

# Seeding records a baseline for a session that changes nothing. It must never
# bless a state the gate has already refused: a failing run leaves the marker
# below, and until a run passes, seeding declines and the gate keeps running.
if [ "$seed" -eq 1 ]; then
  [ -f "$failed" ] && exit 0
  [ -n "$state" ] && printf '%s' "$state" > "$cache"
  exit 0
fi

# Skip when nothing has changed since the last passing run, or since this
# session began, and no refusal is outstanding. Anything else runs, including a
# tree whose changes are all committed. The marker is checked here as well as in
# seed mode so that "never skip while a refusal stands" lives in one place.
if [ -n "$state" ] && [ ! -f "$failed" ] &&
   [ -f "$cache" ] && [ "$(cat "$cache")" = "$state" ]; then
  exit 0
fi

while IFS= read -r cmd; do
  output="$(bash -c "$cmd" 2>&1)" && continue
  status=$?

  # Why a command failed decides what to do about it, so the two cases say
  # different things. Both block: a gate that could not run has not passed, and
  # neither message may read as "carry on". Exit 127 is the shell reporting it
  # found nothing to execute. A bare first word is a PATH lookup for a tool the
  # environment is meant to provide; a first word holding a slash names a file
  # this repository points at, and a missing one of those is the change's
  # business, not the machine's. 126 (found, not executable) stays an ordinary
  # failure for the same reason -- a dropped exec bit is usually in the diff.
  # Everything else falls to the ordinary message, which sends the agent to
  # look: "not your change" is the verdict that can wave a real failure through,
  # so it is the narrow one.
  read -r first _ <<< "$cmd"
  case "$status:$first" in
    127:*/*) missing=0 ;;
    127:*)   missing=1 ;;
    *)       missing=0 ;;
  esac

  {
    if [ "$missing" -eq 1 ]; then
      echo "Quality Gate could not run: $cmd"
      printf '%s\n' "$output" | tail -n 40
      echo "'$first' is not available in this environment, so this check never ran. That is a missing tool, not a failure your change caused. Do not edit code, the gate, or the tests to get past it: report BLOCKED, name the gate command that could not run and the tool it needs, say the change is unverified by that command, and do not declare DONE."
    else
      echo "Quality Gate failed: $cmd"
      printf '%s\n' "$output" | tail -n 40
      echo "If your change caused this, fix it. If it was already failing or is outside the task, do not touch it: report BLOCKED and ask. Do not declare DONE."
    fi
  } >&2
  rm -f "$cache"
  : > "$failed"
  exit 2
done <<< "$commands"

rm -f "$failed"
[ -n "$state" ] && printf '%s' "$state" > "$cache"
exit 0
