#!/usr/bin/env bash
# Tests for .claude/hooks/*.sh. Each case runs in a throwaway git repo.
# Usage: .lean/tests/test-hooks.sh

set -u

repo="$(cd "$(dirname "$0")/../.." && pwd)"
gate="$repo/.claude/hooks/quality-gate.sh"
session="$repo/.claude/hooks/session-start.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

pass=0
fail=0

ok()  { pass=$((pass + 1)); echo "ok   $1"; }
bad() { fail=$((fail + 1)); echo "FAIL $1"; }

# New fixture repo with the real .gitignore and a PROJECT.md whose gate
# block holds the given lines. Prints the repo path.
fixture() {
  local dir
  dir="$(mktemp -d "$work/repo.XXXX")"
  mkdir -p "$dir/.lean" "$dir/.claude"
  cp "$repo/.gitignore" "$dir/.gitignore"
  {
    echo "# Project Context"
    echo
    echo "## Purpose"
    echo
    echo "Not defined yet."
    echo
    echo "<!-- gate:start -->"
    echo '```sh'
    printf '%s\n' "$@"
    echo '```'
    echo "<!-- gate:end -->"
  } > "$dir/.lean/PROJECT.md"
  git -C "$dir" init -q
  git -C "$dir" -c user.name=t -c user.email=t@t add -A
  git -C "$dir" -c user.name=t -c user.email=t@t commit -qm init
  echo "$dir"
}

# run_gate <dir> <stdin json>; sets $code and $err
run_gate() {
  err="$(printf '%s' "$2" | CLAUDE_PROJECT_DIR="$1" bash "$gate" 2>&1 >/dev/null)"
  code=$?
}

expect_code() {
  if [ "$code" -eq "$2" ]; then ok "$1"; else bad "$1 (exit $code, want $2)"; fi
}

# 1. No PROJECT.md
dir="$(mktemp -d "$work/empty.XXXX")"
run_gate "$dir" '{}'
expect_code "gate: no PROJECT.md is a no-op" 0

# 2. Empty gate block
dir="$(fixture)"
echo change > "$dir/file.txt"
run_gate "$dir" '{}'
expect_code "gate: empty block is a no-op" 0

# 3. Failing command blocks with a message
dir="$(fixture 'false')"
echo change > "$dir/file.txt"
run_gate "$dir" '{"stop_hook_active": false}'
expect_code "gate: failing command exits 2" 2
case "$err" in
  *"Quality Gate failed: false"*) ok "gate: failure names the command" ;;
  *) bad "gate: failure names the command (got: $err)" ;;
esac

# 4. stop_hook_active prevents a loop
run_gate "$dir" '{"stop_hook_active":true}'
expect_code "gate: stop_hook_active skips" 0

# 5. A clean tree is not a validated tree: committed work is still gated.
dir="$(fixture 'false')"
echo change > "$dir/code.txt"
git -C "$dir" -c user.name=t -c user.email=t@t add -A
git -C "$dir" -c user.name=t -c user.email=t@t commit -qm work
run_gate "$dir" '{}'
expect_code "gate: committed work is still gated" 2

# 6. Seeded at session start with nothing changed since: skip, failing gate or not.
dir="$(fixture 'false')"
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed
run_gate "$dir" '{}'
expect_code "gate: seeded and unchanged skips" 0

# 7. Seeded, then something changed: the gate runs.
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
expect_code "gate: seeded then changed runs" 2

# 8. --seed records the state and runs no commands.
counter="$work/seeded"
: > "$counter"
dir="$(fixture "echo run >> '$counter'")"
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed
if [ -s "$dir/.claude/.gate-cache" ] && [ ! -s "$counter" ]; then
  ok "gate: --seed caches without running commands"
else
  bad "gate: --seed caches without running commands"
fi

# 9. Comments, blank lines, and fences are not commands
dir="$(fixture '# comment' '' 'true')"
echo change > "$dir/file.txt"
run_gate "$dir" '{}'
expect_code "gate: ignores comments and blank lines" 0

# 10. Passing run is cached; unchanged tree does not re-run
counter="$work/count"
: > "$counter"
dir="$(fixture "echo run >> '$counter'")"
echo change > "$dir/file.txt"
run_gate "$dir" '{}'
expect_code "gate: passing command exits 0" 0
run_gate "$dir" '{}'
runs="$(wc -l < "$counter" | tr -d ' ')"
if [ "$runs" = "1" ]; then ok "gate: cache skips unchanged tree"; else bad "gate: cache skips unchanged tree (ran $runs times)"; fi

# 11. Changing a file invalidates the cache
echo other > "$dir/file.txt"
run_gate "$dir" '{}'
runs="$(wc -l < "$counter" | tr -d ' ')"
if [ "$runs" = "2" ]; then ok "gate: change re-runs"; else bad "gate: change re-runs (ran $runs times)"; fi

# 12. Stops at the first failing command
: > "$counter"
dir="$(fixture 'false' "echo run >> '$counter'")"
echo change > "$dir/file.txt"
run_gate "$dir" '{}'
runs="$(wc -l < "$counter" | tr -d ' ')"
if [ "$code" -eq 2 ] && [ "$runs" = "0" ]; then ok "gate: stops at first failure"; else bad "gate: stops at first failure (exit $code, later ran $runs)"; fi

# 13. Session hook nudges while PROJECT.md is empty
dir="$(fixture)"
out="$(CLAUDE_PROJECT_DIR="$dir" bash "$session")"
case "$out" in
  *"/lean-init"*) ok "session: suggests /lean-init when empty" ;;
  *) bad "session: suggests /lean-init when empty" ;;
esac

# 14. Session hook is silent once Purpose is filled
sed -i.bak 's/^Not defined yet\.$/A real project./' "$dir/.lean/PROJECT.md"
out="$(CLAUDE_PROJECT_DIR="$dir" bash "$session")"
if [ -z "$out" ]; then ok "session: silent when filled"; else bad "session: silent when filled (got: $out)"; fi

# 15. Session hook seeds the gate cache.
dir="$(fixture 'false')"
rm -f "$dir/.claude/.gate-cache"
CLAUDE_PROJECT_DIR="$dir" bash "$session" >/dev/null 2>&1
if [ -s "$dir/.claude/.gate-cache" ]; then
  ok "session: seeds the gate cache"
else
  bad "session: seeds the gate cache"
fi

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
