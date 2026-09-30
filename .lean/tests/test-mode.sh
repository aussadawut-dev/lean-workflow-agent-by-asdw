#!/usr/bin/env bash
# Tests for .lean/bin/mode.sh, the workflow mode config.
# Usage: .lean/tests/test-mode.sh

set -u

repo="$(cd "$(dirname "$0")/../.." && pwd)"
mode="$repo/.lean/bin/mode.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

pass=0
fail=0

ok()  { pass=$((pass + 1)); echo "ok   $1"; }
bad() { fail=$((fail + 1)); echo "FAIL $1"; }

expect() { # expect <label> <got> <want>
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (got '$2', want '$3')"; fi
}

# A PROJECT.md holding the given lines between the mode markers. "none" ships no
# block at all, which is what an install that skipped the upgrade step looks like.
fixture() {
  local dir
  dir="$(mktemp -d "$work/repo.XXXX")"
  mkdir -p "$dir/.lean"
  {
    echo "# Project Context"
    echo
    if [ "${1:-}" != "none" ]; then
      echo "## Workflow mode"
      echo
      echo "<!-- mode:start -->"
      [ "$#" -gt 0 ] && printf '%s\n' "$@"
      echo "<!-- mode:end -->"
      echo
    fi
    echo "## Purpose"
    echo
    echo "Not defined yet."
    echo
    echo "<!-- gate:start -->"
    echo '```sh'
    echo "true"
    echo '```'
    echo "<!-- gate:end -->"
  } > "$dir/.lean/PROJECT.md"
  echo "$dir"
}

run() { CLAUDE_PROJECT_DIR="$1" bash "$mode" "${@:2}"; }

# 1. The shipped value asks rather than picking a mode.
dir="$(fixture unset)"
expect "get: the shipped value reads as unset" "$(run "$dir" get)" "unset"

# 2. A recorded value is read back.
dir="$(fixture tracker)"
expect "get: reads a recorded mode" "$(run "$dir" get)" "tracker"

# 3. No block at all is unset, not an error: the hook asks instead.
dir="$(fixture none)"
run "$dir" get >/dev/null 2>&1
expect "get: no mode block exits 0" "$?" "0"
expect "get: no mode block reads as unset" "$(run "$dir" get)" "unset"

# 4. An empty block is unset too.
dir="$(fixture)"
expect "get: an empty block reads as unset" "$(run "$dir" get)" "unset"

# 5. Decoration around the value is not part of it: a hand-edited block is the
# supported way to switch modes, so a backticked or indented value must read.
# shellcheck disable=SC2016 # literal backticks are the point of the case
dir="$(fixture '   `full`  ')"
expect "get: strips backticks and spaces" "$(run "$dir" get)" "full"

# 6. Comments and fences inside the block are skipped.
dir="$(fixture '# standard | tracker | full' '```' 'tracker' '```')"
expect "get: skips comments and fences" "$(run "$dir" get)" "tracker"

# 7. set records the choice, and get reads it back.
dir="$(fixture unset)"
run "$dir" set full >/dev/null
expect "set: records the mode" "$(run "$dir" get)" "full"

# 8. set replaces the value rather than stacking a second one, and leaves the
# rest of the file alone -- the same file carries the Quality Gate commands.
run "$dir" set standard >/dev/null
expect "set: replaces the previous value" "$(run "$dir" get)" "standard"
expect "set: leaves one value in the block" \
  "$(awk '/mode:start/ {on=1; next} /mode:end/ {on=0} on' "$dir/.lean/PROJECT.md" | grep -c .)" "1"
if grep -q '<!-- gate:start -->' "$dir/.lean/PROJECT.md" &&
   grep -q '^true$' "$dir/.lean/PROJECT.md" &&
   grep -q '^## Purpose$' "$dir/.lean/PROJECT.md"; then
  ok "set: leaves the rest of PROJECT.md intact"
else
  bad "set: leaves the rest of PROJECT.md intact"
fi

# 9. PROJECT.md keeps its permissions: it is written in place, not replaced by a
# temporary file created private to the agent that ran mode.sh.
chmod 644 "$dir/.lean/PROJECT.md"
run "$dir" set tracker >/dev/null
perm="$(stat -c '%A' "$dir/.lean/PROJECT.md" 2>/dev/null ||
  stat -f '%Sp' "$dir/.lean/PROJECT.md")"
expect "set: keeps the file's permissions" "$perm" "-rw-r--r--"

# 10. A value that is not a mode is refused, and nothing is written.
dir="$(fixture standard)"
run "$dir" set paranoid >/dev/null 2>&1
expect "set: refuses a value that is not a mode" "$?" "1"
expect "set: a refused value leaves the recorded one" "$(run "$dir" get)" "standard"

# 11. So is no value at all.
run "$dir" set >/dev/null 2>&1
expect "set: refuses an empty value" "$?" "1"

# 12. Without the markers there is nowhere to record it: say so instead of
# appending a value nothing will read.
dir="$(fixture none)"
err="$(run "$dir" set full 2>&1 >/dev/null)"
expect "set: refuses when the markers are missing" "$?" "1"
case "$err" in
  *"mode:start"*) ok "set: names the missing marker" ;;
  *) bad "set: names the missing marker (got: $err)" ;;
esac

# 13. check passes for every mode and for unset.
for value in standard tracker full unset; do
  dir="$(fixture "$value")"
  run "$dir" check >/dev/null 2>&1
  expect "check: passes for $value" "$?" "0"
done

# 14. check fails for anything else, naming the value -- a typo in the block
# would otherwise run the project in a mode nobody chose.
dir="$(fixture 'trackerr')"
err="$(run "$dir" check 2>&1 >/dev/null)"
expect "check: fails for a value that is not a mode" "$?" "1"
case "$err" in
  *"'trackerr'"*) ok "check: names the invalid value" ;;
  *) bad "check: names the invalid value (got: $err)" ;;
esac

# 15. An unknown subcommand is a usage error, not a silent success.
dir="$(fixture standard)"
run "$dir" frobnicate >/dev/null 2>&1
expect "usage: an unknown subcommand exits 1" "$?" "1"

# 16. A malformed block is the expected input, not an exotic one: hand-editing it
# is the documented way to switch modes. PROJECT.md also carries the Quality Gate
# commands the Stop hook runs, so a rewrite that misreads the block would take
# the gate and the project's own notes with it. These three cases pin that
# nothing is written unless the block is a start line and a separate end line.
malformed() { # malformed <block lines...>; prints the repo path
  local dir
  dir="$(mktemp -d "$work/bad.XXXX")"
  mkdir -p "$dir/.lean"
  {
    echo "# Project Context"
    echo
    printf '%s\n' "$@"
    echo
    echo "## Commands"
    echo
    echo "<!-- gate:start -->"
    echo "true"
    echo "<!-- gate:end -->"
    echo
    echo "## High-risk areas"
  } > "$dir/.lean/PROJECT.md"
  echo "$dir"
}

intact() { # intact <label> <dir> <line count>
  local dir="$2"
  if [ "$(grep -c '' "$dir/.lean/PROJECT.md")" = "$3" ] &&
     [ "$(grep -c '<!-- gate:start -->' "$dir/.lean/PROJECT.md")" = "1" ] &&
     [ "$(grep -c '<!-- gate:end -->' "$dir/.lean/PROJECT.md")" = "1" ] &&
     grep -q '^## High-risk areas$' "$dir/.lean/PROJECT.md"; then
    ok "$1"
  else
    bad "$1 ($(grep -c '' "$dir/.lean/PROJECT.md") lines, wanted $3)"
  fi
}

dir="$(malformed '<!-- mode:start --> tracker <!-- mode:end -->')"
lines="$(grep -c '' "$dir/.lean/PROJECT.md")"
expect "collapsed block: the value between the markers still reads" "$(run "$dir" get)" "tracker"
run "$dir" set standard >/dev/null 2>&1
expect "collapsed block: set refuses it" "$?" "1"
intact "collapsed block: the rest of PROJECT.md survives the refusal" "$dir" "$lines"

# 17. Markers in the wrong order: there is no block, so there is nothing to read
# and nothing to write.
dir="$(malformed '<!-- mode:end -->' 'tracker' '<!-- mode:start -->')"
lines="$(grep -c '' "$dir/.lean/PROJECT.md")"
expect "reversed markers: read as unset" "$(run "$dir" get)" "unset"
run "$dir" set full >/dev/null 2>&1
expect "reversed markers: set refuses" "$?" "1"
intact "reversed markers: the rest of PROJECT.md survives the refusal" "$dir" "$lines"

# 18. A duplicated marker is ambiguous, and guessing which one bounds the value
# is how the wrong region gets rewritten.
dir="$(malformed '<!-- mode:start -->' 'tracker' '<!-- mode:start -->' 'full' '<!-- mode:end -->')"
lines="$(grep -c '' "$dir/.lean/PROJECT.md")"
expect "duplicate marker: read as unset" "$(run "$dir" get)" "unset"
run "$dir" set full >/dev/null 2>&1
expect "duplicate marker: set refuses" "$?" "1"
intact "duplicate marker: the rest of PROJECT.md survives the refusal" "$dir" "$lines"

# 19. The write a well-formed block does get: same line count, same gate block,
# only the value between the markers replaced.
dir="$(malformed '<!-- mode:start -->' 'unset' '<!-- mode:end -->')"
lines="$(grep -c '' "$dir/.lean/PROJECT.md")"
run "$dir" set tracker >/dev/null
expect "set: the recorded value changes" "$(run "$dir" get)" "tracker"
intact "set: nothing outside the block moves" "$dir" "$lines"

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
