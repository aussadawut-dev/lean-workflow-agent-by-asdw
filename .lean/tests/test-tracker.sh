#!/usr/bin/env bash
# Tests for .lean/bin/tracker.sh, the tracking records of the `tracker` and
# `full` workflow modes.
# Usage: .lean/tests/test-tracker.sh

set -u

repo="$(cd "$(dirname "$0")/../.." && pwd)"
tracker="$repo/.lean/bin/tracker.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

pass=0
fail=0

ok()  { pass=$((pass + 1)); echo "ok   $1"; }
bad() { fail=$((fail + 1)); echo "FAIL $1"; }

expect() { # expect <label> <got> <want>
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (got '$2', want '$3')"; fi
}

contains() { # contains <label> <haystack> <needle>
  case "$2" in
    *"$3"*) ok "$1" ;;
    *) bad "$1 (got: $2)" ;;
  esac
}

today="$(date -u '+%Y-%m-%d')"

# A project root with nothing in it: the records directory is the tool's to
# create, since a `standard` project has none.
fixture() { mktemp -d "$work/repo.XXXX"; }

# t <root> <args...>; sets $out and $code
t() {
  local root="$1"
  shift
  out="$(CLAUDE_PROJECT_DIR="$root" bash "$tracker" "$@" 2>&1)"
  code=$?
}

# 1. A record is named by date and slug, under .lean/tracker/, and the directory
# is created on demand.
dir="$(fixture)"
t "$dir" new "Add the login flow"
expect "new: exits 0" "$code" "0"
expect "new: prints the record path" "$out" "$dir/.lean/tracker/$today-add-the-login-flow.md"
if [ -f "$out" ]; then ok "new: the record exists"; else bad "new: the record exists"; fi

# 2. The record is the shape MODES.md documents: the header a later session reads,
# then the Result Contract's sections for whoever did the work.
record="$out"
for line in "# Add the login flow" "state: IN_PROGRESS" "contract: -" "started: $today" "queue: -"; do
  if grep -qxF "$line" "$record"; then
    ok "new: the record has '$line'"
  else
    bad "new: the record has '$line' (got: $(head -6 "$record" | tr '\n' '/'))"
  fi
done
for section in "## Changes" "## Evidence" "## Not verified" "## Follow-ups"; do
  grep -qxF "$section" "$record" || bad "new: the record has $section"
done
ok "new: the record has the Result Contract's sections"

# 3. A contract line is full of characters a rewrite could mistake for syntax:
# `=`, `&`, `|`, `/` and a backslash all appear in real acceptance checks. They
# are recorded verbatim or the header is worse than none.
dir="$(fixture)"
line='risk=HIGH quality=HIGH acceptance=go test ./... && printf "a\1b" | tally'
t "$dir" new "Escape the contract" --contract "$line" --queue "escape-the-contract"
record="$out"
expect "new: the contract line is recorded verbatim" "$(grep '^contract: ' "$record")" "contract: $line"
expect "new: the queue id is recorded" "$(grep '^queue: ' "$record")" "queue: escape-the-contract"

# 4. Two tasks with one title on one day are two records, and the first is not
# touched by the second.
dir="$(fixture)"
t "$dir" new "Same title"
first="$out"
echo "## Changes" >> "$first"
before="$(cksum < "$first")"
t "$dir" new "Same title"
expect "new: a repeated title gets its own record" "$out" "$dir/.lean/tracker/$today-same-title-2.md"
expect "new: the first record is untouched" "$(cksum < "$first")" "$before"

# 5. A title is not a path. One shaped like an escape must not write outside the
# records directory.
dir="$(fixture)"
t "$dir" new "../../etc/passwd"
expect "new: a path-shaped title exits 0" "$code" "0"
case "$out" in
  "$dir/.lean/tracker/"*) ok "new: the record stays under .lean/tracker/" ;;
  *) bad "new: the record stays under .lean/tracker/ (got: $out)" ;;
esac
expect "new: the escape is slugged away" "$(basename "$out")" "$today-etc-passwd.md"
resolved="$(cd "$(dirname "$out")" && pwd -P)"
expect "new: the record's real directory is the records directory" \
  "$resolved" "$(cd "$dir/.lean/tracker" && pwd -P)"

# 6. One header line per field. A value spanning lines would push the fields
# below it into the body, where nothing reads them.
t "$dir" new "$(printf 'two\nlines')"
expect "new: a multi-line title makes a one-line name" "$(basename "$out")" "$today-two-lines.md"
t "$dir" new "Control chars" --contract "$(printf 'a\nb')"
expect "new: a multi-line contract is refused" "$code" "1"
contains "new: the refusal says why" "$out" "may not contain control characters"

# 7. `state` sets the state and nothing else: the sections below it are the
# session's own writing.
dir="$(fixture)"
t "$dir" new "Close me" --queue close-me
record="$out"
printf '\nEvidence: the gate passed.\n' >> "$record"
t "$dir" state close-me DONE
expect "state: exits 0" "$code" "0"
expect "state: the state is set" "$(grep '^state: ' "$record")" "state: DONE"
expect "state: the rest of the record survives" \
  "$(grep -c 'Evidence: the gate passed.' "$record")" "1"
expect "state: the header is intact" "$(grep -c '^queue: close-me$' "$record")" "1"

# 8. A state that is not one of the four is refused, and nothing is written: a
# record claiming a state the workflow does not define is worse than an open one.
before="$(cksum < "$record")"
t "$dir" state close-me FINISHED
expect "state: an undefined state is refused" "$code" "1"
contains "state: the refusal lists the states" "$out" "IN_PROGRESS DONE BLOCKED FAILED"
expect "state: a refused state leaves the record alone" "$(cksum < "$record")" "$before"

# 9. The record keeps its permissions: it is rewritten in place, not replaced by
# a file private to whoever ran the tool.
chmod 644 "$record"
t "$dir" state close-me BLOCKED
perm="$(stat -c '%A' "$record" 2>/dev/null || stat -f '%Sp' "$record")"
expect "state: the record keeps its permissions" "$perm" "-rw-r--r--"

# 10. A record is found by path, by file name, or by slug -- a session that only
# knows what it called the task can still close it.
expect "resolve: by slug" "$(CLAUDE_PROJECT_DIR="$dir" bash "$tracker" show close-me | head -1)" \
  "# Close me"
expect "resolve: by file name" \
  "$(CLAUDE_PROJECT_DIR="$dir" bash "$tracker" show "$(basename "$record")" | head -1)" "# Close me"
expect "resolve: by path" \
  "$(CLAUDE_PROJECT_DIR="$dir" bash "$tracker" show "$record" | head -1)" "# Close me"
t "$dir" show no-such-task
expect "resolve: nothing matched exits 2" "$code" "2"
contains "resolve: the miss names what was asked" "$out" "no-such-task"

# 11. `current` is the open record, so the Quality Gate step does not have to
# carry a path around. When nothing is open it says so rather than guessing.
dir="$(fixture)"
t "$dir" new "First task"
first="$out"
t "$dir" state "$first" DONE
t "$dir" current
expect "current: a closed record is not current" "$code" "2"
t "$dir" new "Second task"
second="$out"
t "$dir" current
expect "current: the open record is current" "$out" "$second"
expect "current: exits 0 when one is open" "$code" "0"

# 12. `list` is one row per record with the state and queue item.
t "$dir" list
expect "list: one row per record plus a header" "$(printf '%s\n' "$out" | grep -c .)" "3"
contains "list: the closed record shows DONE" "$out" "DONE"
contains "list: the open record shows IN_PROGRESS" "$out" "IN_PROGRESS"

# 13. A task learns its contract and its queue item as it goes, so those two
# fields can be set after the fact. A contract line is the value most likely to
# hold `&`, `|` or a backslash, and it must land verbatim rather than as whatever
# a pattern rewrite makes of it.
dir="$(fixture)"
t "$dir" new "Set me later"
record="$out"
line='risk=HIGH quality=HIGH acceptance=make test && printf "a\1b" | tally'
t "$dir" set "set-me-later" contract "$line"
expect "set: exits 0" "$code" "0"
expect "set: the contract lands verbatim" "$(grep '^contract: ' "$record")" "contract: $line"
t "$dir" set "set-me-later" queue "rotate-the-keys"
expect "set: the queue id is set" "$(grep '^queue: ' "$record")" "queue: rotate-the-keys"
expect "set: the state is untouched" "$(grep '^state: ' "$record")" "state: IN_PROGRESS"
t "$dir" set "set-me-later" state DONE
expect "set: the state is not settable here" "$code" "1"
contains "set: the refusal points at the state command" "$out" "use 'state' for the state"
t "$dir" set "set-me-later" contract "$(printf 'a\nb')"
expect "set: a multi-line value is refused" "$code" "1"

# 14. Usage errors are usage errors, not empty records.
dir="$(fixture)"
t "$dir" new
expect "usage: new without a title exits 1" "$code" "1"
t "$dir" state
expect "usage: state without arguments exits 1" "$code" "1"
t "$dir" frobnicate
expect "usage: an unknown subcommand exits 1" "$code" "1"
if [ -d "$dir/.lean/tracker" ] && [ -n "$(ls -A "$dir/.lean/tracker" 2>/dev/null)" ]; then
  bad "usage: a refused command writes no record"
else
  ok "usage: a refused command writes no record"
fi

# 15. Header values are checked for control characters, not for being ASCII: a
# title or a contract line may hold anything printable, in any locale.
dir="$(fixture)"
out="$(LC_ALL=C CLAUDE_PROJECT_DIR="$dir" bash "$tracker" new "Rétablir le café" \
  --contract "risk=LOW quality=STANDARD acceptance=café tests pass" 2>&1)"
code=$?
expect "locale: a non-ASCII record is created under LC_ALL=C" "$code" "0"
contains "locale: the contract keeps its accents" "$(cat "$out")" "acceptance=café tests pass"

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
