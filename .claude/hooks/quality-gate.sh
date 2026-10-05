#!/usr/bin/env bash
# Quality Gate hook (Stop event).
# Runs the commands between the gate markers in .lean/PROJECT.md.
# No commands defined -> no-op. Failure -> exit 2, which blocks Claude
# from finishing and returns the output to it. A command the shell cannot find
# exits 2 as well, because a gate that could not run is not a gate that passed,
# but it says so in its own words: the answer is to report the environment, not
# to repair code that nothing has actually found fault with.
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
      while IFS= read -r -d '' f; do
        # Frame each file independently: A + BC must differ from AB + C.
        printf '%s\0' "$f"
        cksum < "$f" 2>/dev/null
      done
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
  # neither message may read as "carry on". 127 is the only status that can mean
  # the shell found nothing to run, but it is not proof of it: a wrapper hands
  # back the 127 of the program it ran, so `bash lint.sh` whose script calls a
  # tool the diff never added comes back as 127 with bash plainly installed, and
  # reading the command's shape alone would blame the environment for that and
  # name bash as the thing to install. So three things have to hold before the
  # gate says the environment is at fault: that status, a word the shell would
  # have looked up that is a plain command name, and that name failing to
  # resolve here. A word holding a slash names a file this repository points at,
  # a word holding a quote or a dollar is a fragment the line was parsed into,
  # and a word opening with a dash is an option, which is nobody's package to
  # install -- a gate command wrapped over two lines hands its continuation here
  # as a command of its own. None of the three earns the excuse; all three take
  # the ordinary message, as do 126 (found, will not execute -- usually an exec
  # bit missing from the diff) and every other status: "not your change" is the
  # verdict that can wave a real failure through, so it stays the narrow one.
  #
  # Leading VAR=VALUE words are the shell's own business rather than the
  # program, so step past them -- the lookup for `CI=1 npm test` is `npm`, and
  # left in they would decide the verdict by whether `CI=1` resolves as a
  # command, which nothing does. That strip is a regex over the line and cannot
  # see quoting, so `FOO="a b" cmd` leaves `b"` behind: the fragment the name
  # test exists to catch rather than trust.
  lookup="$cmd"
  while [[ "$lookup" =~ ^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+(.*)$ ]]; do
    lookup="${BASH_REMATCH[1]}"
  done
  read -r first _ <<< "$lookup"

  missing=0
  if [ "$status" -eq 127 ] &&
     [[ "$first" =~ ^[A-Za-z0-9_][A-Za-z0-9_.+:@-]*$ ]] &&
     ! command -v -- "$first" >/dev/null 2>&1; then
    missing=1
  fi

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
