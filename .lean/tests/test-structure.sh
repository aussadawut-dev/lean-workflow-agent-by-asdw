#!/usr/bin/env bash
# Tests for .lean/scripts/check-structure.sh: the model registry rules, and the
# workflow mode rules below them. Each case runs the script inside a throwaway copy
# of this repository, over a registry the case writes itself -- never one the host
# .lean/PROJECT.md happens to carry, so the suite holds in an install that never
# adopted a registry.
# Usage: .lean/tests/test-structure.sh

set -u

repo="$(cd "$(dirname "$0")/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

pass=0
fail=0

ok()  { pass=$((pass + 1)); echo "ok   $1"; }
bad() { fail=$((fail + 1)); echo "FAIL $1"; }

# Replaces the whole registry block, or appends one where there is none, so a case
# gets the registry it asked for either way. Body on $MODELS_BODY; empty removes it.
cat > "$work/setreg.py" <<'PY'
import os, re, sys

path = sys.argv[1]
body = os.environ["MODELS_BODY"]
if body and not body.endswith("\n"):
    body += "\n"  # $(cat) drops it, and a row glued to the end marker is outside the block
block = "<!-- models:start -->\n" + body + "<!-- models:end -->\n" if body else ""
text = open(path).read()
pattern = r"<!-- models:start -->.*?<!-- models:end -->\n"
if re.search(pattern, text, re.S):
    text = re.sub(pattern, lambda _: block, text, flags=re.S)
elif block:
    text = text.rstrip("\n") + "\n\n" + block
open(path, "w").write(text)
PY

# The check reads the repository it sits in, so a case needs a whole copy of it.
# Tracked plus untracked-not-ignored: a case must see the file a contributor is
# editing right now, without dragging in build output a consumer's repo may hold.
base="$work/base"
mkdir -p "$base"
(cd "$repo" && git ls-files -z -co --exclude-standard | tar -cf - --null -T -) |
  (cd "$base" && tar -xf -)
# Asserted on the result, not on the pipeline's status: both the `git` and the `tar -c`
# status are masked by their pipelines, and `tar -x` on empty input exits 0.
if [ ! -f "$base/.lean/scripts/check-structure.sh" ]; then
  echo "FAIL could not copy the repository into a fixture (is $repo a git work tree?)"
  exit 1
fi
git -C "$base" init -q
git -C "$base" -c user.name=t -c user.email=t@t add -A
git -C "$base" -c user.name=t -c user.email=t@t commit -qm init

fixture() {
  local dir
  dir="$(mktemp -d "$work/case.XXXX")"
  cp -a "$base/." "$dir/"
  echo "$dir"
}

# set_registry <dir>; block body on stdin, empty stdin for no registry at all.
set_registry() {
  local body
  body="$(cat)"
  MODELS_BODY="$body" python3 "$work/setreg.py" "$1/.lean/PROJECT.md"
}

# block_of <dir> -- what sits between the registry markers, markers excluded.
block_of() {
  awk '/<!-- models:start -->/ { inside = 1; next }
       /<!-- models:end -->/   { inside = 0 }
       inside' "$1/.lean/PROJECT.md"
}

# head of a well-formed table
header() { printf '| runtime | tier | model | verified |\n| --- | --- | --- | --- |\n'; }

# rows <runtime> <date> -- one row per tier, all on the same date
rows() { printf '| %s | fast | m-f | %s |\n| %s | default | m-d | %s |\n| %s | strongest | m-s | %s |\n' "$1" "$2" "$1" "$2" "$1" "$2"; }

days_ago() {
  python3 -c 'import datetime,sys
print(datetime.date.today() - datetime.timedelta(days=int(sys.argv[1])))' "$1"
}

# run_check <dir>; sets $code and $out
run_check() {
  out="$("$1/.lean/scripts/check-structure.sh" 2>&1)"
  code=$?
}

expect_pass() {
  if [ "$code" -eq 0 ]; then ok "$1"; else bad "$1 (exit $code, want 0: $out)"; fi
}

# Names the registry, so a case cannot pass on an unrelated failure it caused.
expect_registry_fail() {
  if [ "$code" -eq 0 ]; then
    bad "$1 (exit 0, want non-zero)"
  elif printf '%s' "$out" | grep -qi 'model registry\|models:start'; then
    ok "$1"
  else
    bad "$1 (failed, but not on the registry: $out)"
  fi
}

today="$(days_ago 0)"

# 1. The fixture itself is sound, so every case below starts from a passing check.
dir="$(fixture)"
run_check "$dir"
expect_pass "structure: an unmodified copy of the repository passes"
case "$out" in
  *"structure ok"*) ok "structure: a passing run says so" ;;
  *) bad "structure: a passing run says so (got: $out)" ;;
esac

# 2. The registry this repository ships, checked where it actually lives. Without
#    this the suite would stay green on the day the shipped dates go stale, while
#    every turn in the repository is blocked by the gate.
run_check "$repo"
expect_pass "structure: this repository's own PROJECT.md passes as it stands"

# 3. A registry the case wrote itself, so the cases below do not depend on the host.
dir="$(fixture)"
{ header; rows claude "$today"; } | set_registry "$dir"
run_check "$dir"
expect_pass "structure: a registry verified today passes"

# 4. Past the window.
dir="$(fixture)"
{ header; rows claude "$(days_ago 91)"; } | set_registry "$dir"
run_check "$dir"
expect_registry_fail "structure: a row verified 91 days ago fails"
case "$out" in
  *"limit 90"*) ok "structure: the stale message names the limit" ;;
  *) bad "structure: the stale message names the limit (got: $out)" ;;
esac
case "$out" in
  *"runtime claude has a row verified"*) ok "structure: the stale message names the runtime" ;;
  *) bad "structure: the stale message names the runtime (got: $out)" ;;
esac

# 5. The edge of the window is inside it, not outside.
dir="$(fixture)"
{ header; rows claude "$(days_ago 90)"; } | set_registry "$dir"
run_check "$dir"
expect_pass "structure: a row verified 90 days ago still passes"

# 6. A date not yet reached verifies nothing, and is the cheapest way to silence
#    the check.
dir="$(fixture)"
{ header; rows claude "$(days_ago -1)"; } | set_registry "$dir"
run_check "$dir"
expect_registry_fail "structure: a row dated in the future fails"

# 7. A date the calendar does not have.
dir="$(fixture)"
{ header; rows claude 2026-13-45; } | set_registry "$dir"
run_check "$dir"
expect_registry_fail "structure: a malformed date fails"

# 8. Undated rows are the drift itself.
dir="$(fixture)"
{ printf '| runtime | tier | model |\n| --- | --- | --- |\n'
  printf '| claude | fast | m-f |\n| claude | default | m-d |\n| claude | strongest | m-s |\n'
} | set_registry "$dir"
run_check "$dir"
expect_registry_fail "structure: rows with no verified column fail"
# The verdict alone is not the point: without the shape check these rows reach the
# date arithmetic and fail as an unreadable date, which names the wrong problem.
case "$out" in
  *"| runtime | tier | model | YYYY-MM-DD |"*) ok "structure: the message names the row shape" ;;
  *) bad "structure: the message names the row shape (got: $out)" ;;
esac

# 9. Markers and a header, but nothing named.
dir="$(fixture)"
header | set_registry "$dir"
run_check "$dir"
expect_registry_fail "structure: a registry with no rows fails"

# 10. A lost marker must not read as no registry.
dir="$(fixture)"
{ header; rows claude "$today"; } | set_registry "$dir"
file="$dir/.lean/PROJECT.md"
grep -v 'models:end' "$file" > "$file.new" && mv "$file.new" "$file"
grep -q 'models:end' "$file" && bad "fixture: the end marker was not removed"
run_check "$dir"
expect_registry_fail "structure: a registry missing its end marker fails"

# 11. Both markers on one line count as one each, so the block must still close on
#     the line that opens it. A whole valid registry below them is what makes this
#     case discriminating: a scan that runs to end of file would read those rows and
#     call an empty block a current registry.
dir="$(fixture)"
printf '' | set_registry "$dir"
{ printf '\n<!-- models:start --> <!-- models:end -->\n\n'
  header
  rows claude "$today"
} >> "$dir/.lean/PROJECT.md"
run_check "$dir"
expect_registry_fail "structure: both markers on one line close the block"
case "$out" in
  *"has no rows"*) ok "structure: rows below a closed block are not read" ;;
  *) bad "structure: rows below a closed block are not read (got: $out)" ;;
esac

# 12. No registry at all is a project that has not adopted one, not a failure:
#     .lean/policy/MODELS.md falls back to the tier descriptions.
dir="$(fixture)"
printf '' | set_registry "$dir"
grep -q 'models:start' "$dir/.lean/PROJECT.md" && bad "fixture: the registry was not removed"
run_check "$dir"
expect_pass "structure: no registry is not a failure"

# 13. Per-runtime dates: one runtime's update does not vouch for another's.
dir="$(fixture)"
{ header; rows claude "$today"; rows codex "$(days_ago 91)"; } | set_registry "$dir"
run_check "$dir"
expect_registry_fail "structure: a second runtime's stale rows fail while the first is fresh"

dir="$(fixture)"
{ header; rows claude "$today"; rows codex "$(days_ago 30)"; } | set_registry "$dir"
run_check "$dir"
expect_pass "structure: two runtimes on different fresh dates pass"

# 14. A runtime listed for some tiers only is dated and trusted for the tier it
#     does not name.
dir="$(fixture)"
{ header; rows claude "$today"
  printf '| codex | fast | m-f | %s |\n' "$today"
} | set_registry "$dir"
run_check "$dir"
expect_registry_fail "structure: a runtime missing tiers fails"
case "$out" in
  *"codex has no row for: default strongest"*) ok "structure: the message names the missing tiers" ;;
  *) bad "structure: the message names the missing tiers (got: $out)" ;;
esac

# 15. A pinned version id carries a date of its own. Reading that as the row's
#     date would date the registry by the model it is meant to be checking.
dir="$(fixture)"
{ header
  printf '| codex | fast | some-model-2019-01-01 | %s |\n' "$today"
  printf '| codex | default | some-model-2019-01-01 | %s |\n' "$today"
  printf '| codex | strongest | some-model-2019-01-01 | %s |\n' "$today"
} | set_registry "$dir"
run_check "$dir"
expect_pass "structure: a date inside a pinned model id is not the row's date"

# 16. A CRLF checkout must not turn a present date into a missing one.
dir="$(fixture)"
{ header; rows claude "$today"; } | set_registry "$dir"
file="$dir/.lean/PROJECT.md"
sed $'s/$/\r/' "$file" > "$file.new" && mv "$file.new" "$file"
grep -q "$(printf '\r')" "$file" || bad "fixture: no CR was added, so the case proves nothing"
run_check "$dir"
expect_pass "structure: a CRLF PROJECT.md passes"

# 17. Markdown does not require the outer pipes, so a row written without them is a row
#     this check cannot see. Mixed with rows that have them, the block still parses and
#     the unseen rows' dates never reach the limit -- a stale registry reading as current,
#     which is the whole failure this feature exists to prevent.
dir="$(fixture)"
{ header; rows claude "$today"
  printf 'codex | fast | m-f | %s\ncodex | default | m-d | %s\ncodex | strongest | m-s | %s\n' \
    "$(days_ago 900)" "$(days_ago 900)" "$(days_ago 900)"
} | set_registry "$dir"
run_check "$dir"
expect_registry_fail "structure: rows without outer pipes fail rather than being skipped"
case "$out" in
  *"not a table row"*) ok "structure: the message says the line was not read as a row" ;;
  *) bad "structure: the message says the line was not read as a row (got: $out)" ;;
esac

# 18. Prose left inside the markers is unseen in the same way.
dir="$(fixture)"
{ header; rows claude "$today"; printf 'TODO: add the codex rows\n'; } | set_registry "$dir"
run_check "$dir"
expect_registry_fail "structure: prose inside the block fails"

# 19. An alignment delimiter is the separator row in one of the two shapes GFM allows,
#     not a data row. Reading it as one is a permanent failure over valid markdown.
dir="$(fixture)"
{ printf '| runtime | tier | model | verified |\n| :--- | :---: | ---: | --- |\n'
  rows claude "$today"
} | set_registry "$dir"
run_check "$dir"
expect_pass "structure: an alignment delimiter row is not read as a row"

# 20. The tier keys are MODELS.md's and are case-sensitive. Without this a capitalised
#     tier is accepted as a row for an unknown tier and counted as missing the real one,
#     and the failure blames the wrong thing.
dir="$(fixture)"
{ header
  printf '| claude | Fast | m-f | %s |\n' "$today"
  printf '| claude | default | m-d | %s |\n' "$today"
  printf '| claude | strongest | m-s | %s |\n' "$today"
} | set_registry "$dir"
run_check "$dir"
expect_registry_fail "structure: a tier MODELS.md does not name fails"
case "$out" in
  *"the tiers are fast, default, strongest"*) ok "structure: the message names the tier keys" ;;
  *) bad "structure: the message names the tier keys (got: $out)" ;;
esac

# 21. Blank lines inside the block are not content: the stray-line rule is about rows
#     the check cannot see, and a blank line is not a row anyone wrote.
dir="$(fixture)"
{ header; printf '\n'; rows claude "$today"; } | set_registry "$dir"
block_of "$dir" | grep -qx '' || bad "fixture: no blank line inside the block"
run_check "$dir"
expect_pass "structure: a blank line inside the block is not a stray line"

# 22. On a CRLF checkout a blank line is a bare \r, which is neither space nor tab. A
#     rule reading it as content fails a registry that is fine on LF, and prints the
#     offending line as empty while blaming outer pipes.
dir="$(fixture)"
{ header; printf '\n'; rows claude "$today"; } | set_registry "$dir"
file="$dir/.lean/PROJECT.md"
sed $'s/$/\r/' "$file" > "$file.new" && mv "$file.new" "$file"
grep -q "$(printf '\r')" "$file" || bad "fixture: no CR was added, so the case proves nothing"
run_check "$dir"
expect_pass "structure: a blank line in a CRLF registry is not a stray line"

# 23. A stray line on a CRLF tree still has its CR when the check reports it, and a CR
#     inside the message returns the terminal's cursor to column zero, overwriting the
#     half of it that says what to do.
dir="$(fixture)"
{ header; rows claude "$today"; printf 'codex | fast | m-f | 2019-01-01\n'; } | set_registry "$dir"
file="$dir/.lean/PROJECT.md"
sed $'s/$/\r/' "$file" > "$file.new" && mv "$file.new" "$file"
grep -q "$(printf '\r')" "$file" || bad "fixture: no CR was added, so the case proves nothing"
run_check "$dir"
expect_registry_fail "structure: a stray line on a CRLF tree fails"
case "$out" in
  *"2019-01-01 -- every row needs"*) ok "structure: the stray line is reported without its CR" ;;
  *) bad "structure: the stray line is reported without its CR (got: $out)" ;;
esac

# --- the workflow mode rules ------------------------------------------------
# The structure check is what stops a project running under a mode nobody chose:
# .lean/bin/mode.sh reads the value, and the hook only asks when there is none, so
# a typo would otherwise sit there silently dropping the records or the queue the
# project asked for.

expect_mode_fail() {
  if [ "$code" -eq 0 ]; then
    bad "$1 (exit 0, want non-zero)"
  elif printf '%s' "$out" | grep -qi 'mode'; then
    ok "$1"
  else
    bad "$1 (failed, but not on the mode: $out)"
  fi
}

set_mode() { # set_mode <dir> <value>
  python3 - "$1/.lean/PROJECT.md" "$2" <<'PYEOF'
import re, sys
path, value = sys.argv[1], sys.argv[2]
text = open(path).read()
block = "<!-- mode:start -->\n" + value + "\n<!-- mode:end -->"
text = re.sub(r"<!-- mode:start -->.*?<!-- mode:end -->", lambda _: block, text, flags=re.S)
open(path, "w").write(text)
PYEOF
}

# Each of the three modes passes, and so does an install that has not chosen yet:
# the hook asks for that one, and failing the gate over it would block every turn.
for value in standard tracker full unset; do
  dir="$(fixture)"
  set_mode "$dir" "$value"
  run_check "$dir"
  expect_pass "structure: the mode '$value' passes"
done

# Anything else is a typo, and the message names it.
dir="$(fixture)"
set_mode "$dir" "trackers"
run_check "$dir"
expect_mode_fail "structure: a mode that is not one of the three fails"
case "$out" in
  *"'trackers'"*) ok "structure: the failure names the recorded value" ;;
  *) bad "structure: the failure names the recorded value (got: $out)" ;;
esac

# A lost marker leaves the value unreadable, which mode.sh reads as unset -- so the
# markers are checked in their own right, or the block could rot away in silence.
dir="$(fixture)"
sed -i.bak 's|<!-- mode:end -->||' "$dir/.lean/PROJECT.md"
rm -f "$dir/.lean/PROJECT.md.bak"
run_check "$dir"
expect_mode_fail "structure: a missing mode marker fails"

# The tools have to be runnable: the SessionStart hook calls mode.sh every session,
# and a non-executable one would leave the mode unreadable without saying so.
dir="$(fixture)"
chmod -x "$dir/.lean/bin/mode.sh"
run_check "$dir"
expect_mode_fail "structure: a mode.sh that cannot run fails"

# A project that dropped .lean/bin/ altogether still fails -- on the documentation
# that names the tools, which it has to drop too -- but never on the mode rule.
# The hook says nothing about modes there, and the rule scoped to the directory is
# what keeps the two from disagreeing about a mode nobody can record.
dir="$(fixture)"
rm -rf "$dir/.lean/bin"
run_check "$dir"
if [ "$code" -ne 0 ]; then
  ok "structure: dropping .lean/bin/ fails while the docs still name it"
else
  bad "structure: dropping .lean/bin/ fails while the docs still name it (exit 0)"
fi
case "$out" in
  *"missing .lean/bin/mode.sh"*) ok "structure: it fails on the dangling reference" ;;
  *) bad "structure: it fails on the dangling reference (got: $out)" ;;
esac
case "$out" in
  *"workflow mode"* | *"not executable: .lean/bin/mode.sh"*)
    bad "structure: the mode rule fired without the directory (got: $out)" ;;
  *) ok "structure: the mode rule does not fire without the directory" ;;
esac

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
