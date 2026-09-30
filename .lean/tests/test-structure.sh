#!/usr/bin/env bash
# Tests for .lean/scripts/check-structure.sh, covering the model registry age
# check. Each case runs the script inside a throwaway copy of this repository.
# Usage: .lean/tests/test-structure.sh

set -u

repo="$(cd "$(dirname "$0")/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

pass=0
fail=0

ok()  { pass=$((pass + 1)); echo "ok   $1"; }
bad() { fail=$((fail + 1)); echo "FAIL $1"; }

# The check reads the repository it sits in, so a case needs a whole copy of it.
# The working tree, not `git ls-files`: a case must see the file a contributor is
# editing right now. Built once, then copied per case.
base="$work/base"
mkdir -p "$base"
if ! (cd "$repo" && tar -cf - --exclude=./.git .) | (cd "$base" && tar -xf -); then
  echo "FAIL could not copy the repository into a fixture"
  exit 1
fi
git -C "$base" init -q
git -C "$base" -c user.name=t -c user.email=t@t add -A
git -C "$base" -c user.name=t -c user.email=t@t commit -qm init

# A fresh copy per case: a counter would not survive, since the call is a subshell.
fixture() {
  local dir
  dir="$(mktemp -d "$work/case.XXXX")"
  cp -a "$base/." "$dir/"
  echo "$dir"
}

# run_check <dir>; sets $code and $out
run_check() {
  out="$("$1/.lean/scripts/check-structure.sh" 2>&1)"
  code=$?
}

days_ago() {
  python3 -c 'import datetime,sys
print(datetime.date.today() - datetime.timedelta(days=int(sys.argv[1])))' "$1"
}

# set_verified <dir> <date>
set_verified() {
  local file="$1/.lean/PROJECT.md"
  sed "s/^verified: .*/verified: $2/" "$file" > "$file.new" && mv "$file.new" "$file"
}

# drop_lines <dir> <regex>
drop_lines() {
  local file="$1/.lean/PROJECT.md"
  grep -v -- "$2" "$file" > "$file.new" && mv "$file.new" "$file"
}

# drop_registry <dir> -- removes the whole block, markers included.
drop_registry() {
  python3 - "$1/.lean/PROJECT.md" <<'PY'
import re, sys
p = sys.argv[1]
s = open(p).read()
s = re.sub(r'<!-- models:start -->.*?<!-- models:end -->\n', '', s, flags=re.S)
open(p, 'w').write(s)
PY
}

expect_code() {
  if [ "$code" -eq "$2" ]; then ok "$1"; else bad "$1 (exit $code, want $2)"; fi
}

expect_pass() {
  if [ "$code" -eq 0 ]; then ok "$1"; else bad "$1 (exit $code, want 0: $out)"; fi
}

# names the registry, so a case cannot pass on an unrelated failure it caused.
expect_registry_fail() {
  if [ "$code" -eq 0 ]; then
    bad "$1 (exit 0, want non-zero)"
  elif printf '%s' "$out" | grep -qi 'model registry\|models:start'; then
    ok "$1"
  else
    bad "$1 (failed, but not on the registry: $out)"
  fi
}

# 1. The fixture itself is sound, so every case below starts from a passing check.
dir="$(fixture)"
run_check "$dir"
expect_pass "structure: an unmodified copy of the repository passes"
case "$out" in
  *"structure ok"*) ok "structure: a passing run says so" ;;
  *) bad "structure: a passing run says so (got: $out)" ;;
esac

# 2. The registry this repository ships is inside the window. Without this the
#    suite would still pass on the day the shipped date goes stale, while every
#    turn in the repository is blocked by the gate.
run_check "$repo"
expect_pass "structure: the repository's own registry is current"

# 3. Past the window.
dir="$(fixture)"
set_verified "$dir" "$(days_ago 91)"
run_check "$dir"
expect_registry_fail "structure: a registry verified 91 days ago fails"
case "$out" in
  *"limit 90"*) ok "structure: the stale message names the limit" ;;
  *) bad "structure: the stale message names the limit (got: $out)" ;;
esac

# 4. The edge of the window is inside it, not outside.
dir="$(fixture)"
set_verified "$dir" "$(days_ago 90)"
run_check "$dir"
expect_pass "structure: a registry verified 90 days ago still passes"

# 5. A date not yet reached verifies nothing, and is the cheapest way to silence
#    the check.
dir="$(fixture)"
set_verified "$dir" "$(days_ago -1)"
run_check "$dir"
expect_registry_fail "structure: a verified date in the future fails"

# 6. A date the calendar does not have.
dir="$(fixture)"
set_verified "$dir" "2026-13-45"
run_check "$dir"
expect_registry_fail "structure: a malformed verified date fails"

# 7. Markers but no date: undated entries are the drift itself.
dir="$(fixture)"
drop_lines "$dir" '^verified: '
run_check "$dir"
expect_registry_fail "structure: a registry with no verified line fails"

# 8. A lost marker must not read as no registry.
dir="$(fixture)"
drop_lines "$dir" 'models:end'
run_check "$dir"
expect_registry_fail "structure: a registry missing its end marker fails"

# 9. No registry at all is a project that has not adopted one, not a failure:
#    .lean/policy/MODELS.md falls back to the tier descriptions.
dir="$(fixture)"
drop_registry "$dir"
run_check "$dir"
expect_pass "structure: no registry is not a failure"

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
