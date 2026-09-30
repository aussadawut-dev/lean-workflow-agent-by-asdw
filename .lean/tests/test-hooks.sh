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

# 16. The commit is part of the state: the second commit is gated too, not just
# the first. Without the commit in the state both post-commit trees look alike.
: > "$counter"
dir="$(fixture "echo run >> '$counter'")"
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed
for n in 1 2; do
  echo "change $n" > "$dir/code.txt"
  git -C "$dir" -c user.name=t -c user.email=t@t add -A
  git -C "$dir" -c user.name=t -c user.email=t@t commit -qm "work $n"
  run_gate "$dir" '{}'
done
runs="$(wc -l < "$counter" | tr -d ' ')"
if [ "$runs" = "2" ]; then ok "gate: every commit is gated"; else bad "gate: every commit is gated (ran $runs of 2)"; fi

# 17. The uncommitted diff is part of the state: two edits to one tracked file
# look identical to git status, so only the diff itself distinguishes them.
: > "$counter"
dir="$(fixture "echo run >> '$counter'")"
echo first > "$dir/t.txt"
git -C "$dir" -c user.name=t -c user.email=t@t add -A
git -C "$dir" -c user.name=t -c user.email=t@t commit -qm add-t
echo second > "$dir/t.txt"
run_gate "$dir" '{}'
echo third > "$dir/t.txt"
run_gate "$dir" '{}'
runs="$(wc -l < "$counter" | tr -d ' ')"
if [ "$runs" = "2" ]; then ok "gate: a further edit to a tracked file re-runs"; else bad "gate: a further edit to a tracked file re-runs (ran $runs of 2)"; fi

# 18. Editing the gate commands re-runs the gate.
: > "$counter"
dir="$(fixture "echo run >> '$counter'")"
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
sed -i.bak "s|echo run >> |echo edited >> |" "$dir/.lean/PROJECT.md"
run_gate "$dir" '{}'
runs="$(wc -l < "$counter" | tr -d ' ')"
if [ "$runs" = "2" ]; then ok "gate: editing the gate commands re-runs"; else bad "gate: editing the gate commands re-runs (ran $runs of 2)"; fi

# 19. A state the gate refused is not blessed by a later seed.
dir="$(fixture 'false')"
echo broken > "$dir/code.txt"
run_gate "$dir" '{}'
expect_code "gate: refuses broken work" 2
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed
run_gate "$dir" '{}'
expect_code "gate: a seed does not bless a refused state" 2

# 20. The same, once the broken work is committed.
dir="$(fixture 'false')"
echo broken > "$dir/code.txt"
git -C "$dir" -c user.name=t -c user.email=t@t add -A
git -C "$dir" -c user.name=t -c user.email=t@t commit -qm broken
run_gate "$dir" '{}'
expect_code "gate: refuses committed broken work" 2
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed
run_gate "$dir" '{}'
expect_code "gate: a seed does not bless refused committed work" 2

# 21. A refusal is recorded, and a passing run clears it.
dir="$(fixture "test -f '$work/flag'")"
rm -f "$work/flag"
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
expect_code "gate: refuses while the check fails" 2
if [ -f "$dir/.claude/.gate-failed" ]; then ok "gate: a refusal is recorded"; else bad "gate: a refusal is recorded"; fi
: > "$work/flag"
run_gate "$dir" '{}'
expect_code "gate: passes once the check passes" 0
if [ ! -f "$dir/.claude/.gate-failed" ]; then ok "gate: a pass clears the refusal"; else bad "gate: a pass clears the refusal"; fi

# 22. A new untracked file changes the state even when it is empty: its content
# adds nothing, so only git status sees that it appeared.
: > "$counter"
dir="$(fixture "echo run >> '$counter'")"
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
: > "$dir/appeared.txt"
run_gate "$dir" '{}'
runs="$(wc -l < "$counter" | tr -d ' ')"
if [ "$runs" = "2" ]; then ok "gate: a new empty untracked file re-runs"; else bad "gate: a new empty untracked file re-runs (ran $runs of 2)"; fi

# 23. The gate commands are part of the state in their own right. With
# .lean/PROJECT.md ignored by git, no other term in the state can see an edit
# to it: it is neither in the diff nor among the untracked files. The trailing
# `*` in the ignore pattern is load-bearing -- it also covers the .bak that
# `sed -i.bak` leaves, which git status would otherwise report, making this
# check pass without the commands being in the state at all.
: > "$counter"
dir="$(fixture "echo run >> '$counter'")"
printf '.lean/PROJECT.md*\n' >> "$dir/.gitignore"
git -C "$dir" rm -q --cached .lean/PROJECT.md
git -C "$dir" -c user.name=t -c user.email=t@t add -A
git -C "$dir" -c user.name=t -c user.email=t@t commit -qm "ignore PROJECT.md"
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
sed -i.bak "s|echo run >> |echo edited >> |" "$dir/.lean/PROJECT.md"
run_gate "$dir" '{}'
runs="$(wc -l < "$counter" | tr -d ' ')"
if [ "$runs" = "2" ]; then ok "gate: the gate commands are part of the state"; else bad "gate: the gate commands are part of the state (ran $runs of 2)"; fi

# 24. Two guards keep a refusal from being skipped, and each is pinned on its
# own. First: while a refusal stands, seeding writes no cache at all.
dir="$(fixture 'false')"
echo broken > "$dir/code.txt"
run_gate "$dir" '{}'
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed
if [ ! -f "$dir/.claude/.gate-cache" ]; then
  ok "gate: a seed writes no cache while a refusal stands"
else
  bad "gate: a seed writes no cache while a refusal stands"
fi

# 25. Second: a cache that does match is still not skipped while the refusal
# stands. Built by seeding with the marker briefly out of the way, which is the
# state two concurrent sessions could otherwise leave behind. This tests the
# guard only while the marker is gitignored: untracked and visible, recreating
# it would change the state by itself and the gate would run for that reason
# instead, so the dependency is asserted rather than assumed.
if git -C "$dir" check-ignore -q .claude/.gate-failed; then
  ok "gate: the refusal marker is invisible to the state"
else
  bad "gate: the refusal marker is invisible to the state (case 25 tests nothing without it)"
fi
rm -f "$dir/.claude/.gate-failed"
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed
: > "$dir/.claude/.gate-failed"
run_gate "$dir" '{}'
expect_code "gate: a matching cache does not override a refusal" 2

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
