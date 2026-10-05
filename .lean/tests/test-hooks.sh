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
echo '{"mode":"standard","configured":true}' > "$dir/.lean/config.json"
out="$(CLAUDE_PROJECT_DIR="$dir" bash "$session")"
if [ -z "$out" ]; then ok "session: silent when filled"; else bad "session: silent when filled (got: $out)"; fi

# 15. Session hook seeds the gate cache.
dir="$(fixture)"
echo '{"mode":"standard","configured":false}' > "$dir/.lean/config.json"
out="$(CLAUDE_PROJECT_DIR="$dir" bash "$session")"
case "$out" in
  *"choose standard, tracker, or full"*) ok "session: prompts for mode before initial setup" ;;
  *) bad "session: prompts for mode before initial setup (got: $out)" ;;
esac
echo '{"mode":"tracker","configured":true}' > "$dir/.lean/config.json"
out="$(CLAUDE_PROJECT_DIR="$dir" bash "$session")"
case "$out" in
  *"choose standard, tracker, or full"*) bad "session: no mode prompt after setup (got: $out)" ;;
  *) ok "session: no mode prompt after setup" ;;
esac

# Missing config uses the same onboarding as unconfigured standard mode.
dir="$(fixture)"
out="$(CLAUDE_PROJECT_DIR="$dir" bash "$session")"
case "$out" in
  *"choose standard, tracker, or full"*) ok "session: prompts when config is missing" ;;
  *) bad "session: prompts when config is missing (got: $out)" ;;
esac

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

# 26. A gate command whose program is not installed blocks like any other
# failure -- a gate that could not run has not passed -- but the message has to
# say which of the two it is, because they need opposite responses: fix the
# code, or report that the environment could not check it. Verified on the
# container this repository is developed in, which ships no shellcheck -- the
# very first gate command in .lean/PROJECT.md. With one message for both, every
# turn there that touched a file ended as BLOCKED work over a clean diff.
dir="$(fixture 'lean-no-such-tool --check')"
# Seeded first so a cache exists for the run to clear: without one, the cache
# half of the refusal assertion below passes whatever the hook does with it.
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
expect_code "gate: a missing program still blocks" 2
case "$err" in
  *"Quality Gate could not run: lean-no-such-tool --check"*)
    ok "gate: a missing program says the gate could not run" ;;
  *) bad "gate: a missing program says the gate could not run (got: $err)" ;;
esac
case "$err" in
  *"not a failure your change caused"*)
    ok "gate: a missing program is named as the environment" ;;
  *) bad "gate: a missing program is named as the environment (got: $err)" ;;
esac
case "$err" in
  *"If your change caused this"*)
    bad "gate: a missing program does not ask for a code fix (got: $err)" ;;
  *) ok "gate: a missing program does not ask for a code fix" ;;
esac
if [ -f "$dir/.claude/.gate-failed" ] && [ ! -f "$dir/.claude/.gate-cache" ]; then
  ok "gate: a missing program records the refusal like any other"
else
  bad "gate: a missing program records the refusal like any other"
fi

# 27. The other half: a command that exists and fails keeps the ordinary
# verdict. Without this the split could drift into calling every failure an
# environment problem, which reads as "nothing here to fix" on a real
# regression -- the same mistake as case 26, pointed the other way.
dir="$(fixture "test -f '$work/never-created'")"
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
expect_code "gate: a real failure still blocks" 2
case "$err" in
  *"Quality Gate failed: test -f"*) ok "gate: a real failure keeps the failure message" ;;
  *) bad "gate: a real failure keeps the failure message (got: $err)" ;;
esac
case "$err" in
  *"If your change caused this"*) ok "gate: a real failure still asks for a fix" ;;
  *) bad "gate: a real failure still asks for a fix (got: $err)" ;;
esac
case "$err" in
  *"could not run"*)
    bad "gate: a real failure is not called an environment problem (got: $err)" ;;
  *) ok "gate: a real failure is not called an environment problem" ;;
esac

# 28. A gate command that names a path rather than a program is this
# repository's business even when it is missing: the shell reports that the same
# way it reports an absent tool, so the split reads the command's shape, and
# this pins the side of it that stays an ordinary failure.
dir="$(fixture './scripts/gone.sh')"
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
expect_code "gate: a missing script still blocks" 2
case "$err" in
  *"Quality Gate failed: ./scripts/gone.sh"*)
    ok "gate: a missing script is a failure, not an environment problem" ;;
  *) bad "gate: a missing script is a failure, not an environment problem (got: $err)" ;;
esac

# 29. 127 is not proof that the gate line's own program is absent: a wrapper
# hands back the status of whatever it ran. `bash lint.sh` whose script calls a
# tool the diff never added is the change's business, and the environment
# message would tell the agent the opposite while naming bash -- which is
# plainly installed, since it ran the script -- as the thing to install. So the
# split asks whether the looked-up word resolves, not merely whether it holds a
# slash, and this is the case that tells those two rules apart.
dir="$(fixture 'bash scripts/lint.sh')"
mkdir -p "$dir/scripts"
printf '#!/usr/bin/env bash\n./tools/lint-tool --check\n' > "$dir/scripts/lint.sh"
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
expect_code "gate: a wrapper whose inner program is missing still blocks" 2
case "$err" in
  *"Quality Gate failed: bash scripts/lint.sh"*)
    ok "gate: a present wrapper is a failure, not a missing tool" ;;
  *) bad "gate: a present wrapper is a failure, not a missing tool (got: $err)" ;;
esac

# 30. A leading VAR=VALUE is the shell's business, not the program. Left in the
# lookup it decides the verdict by whether `LEAN_TEST=1` resolves as a command,
# which nothing does, and then names an assignment as the tool to install -- so
# this asserts the program by name, not just the branch.
dir="$(fixture 'LEAN_TEST=1 lean-no-such-tool --check')"
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
expect_code "gate: an assignment does not hide a missing program" 2
case "$err" in
  *"'lean-no-such-tool' is not available"*)
    ok "gate: the message names the program, not the assignment" ;;
  *) bad "gate: the message names the program, not the assignment (got: $err)" ;;
esac

# 31. The assignment strip is a regex over the line, so it cannot see quoting:
# `FOO="a b" cmd` leaves `b"` as the word to look up. That is a fragment of the
# line, not a name, and nothing resolves it -- so with the lookup alone the
# verdict would be decided by a parse failure, and case 29's shape, one quoted
# assignment later, would be exculpated all over again. A word that is not a
# plain command name therefore takes the ordinary message: under-attributing
# sends the agent to look, which is the safe direction, while over-attributing
# is the bug this version exists to fix.
dir="$(fixture 'LEAN_OPTS="-a b" bash scripts/lint.sh')"
mkdir -p "$dir/scripts"
printf '#!/usr/bin/env bash\n./tools/lint-tool --check\n' > "$dir/scripts/lint.sh"
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
expect_code "gate: a quoted assignment value still blocks" 2
case "$err" in
  *'Quality Gate failed: LEAN_OPTS="-a b" bash scripts/lint.sh'*)
    ok "gate: a fragment left by quoting is not called a missing tool" ;;
  *) bad "gate: a fragment left by quoting is not called a missing tool (got: $err)" ;;
esac
case "$err" in
  *"could not run"*)
    bad "gate: a fragment does not claim the environment (got: $err)" ;;
  *) ok "gate: a fragment does not claim the environment" ;;
esac

# 32. The status is a condition in its own right: in a compound line the word
# that did not resolve need not be the word that decided the verdict. Here a
# missing tool is tolerated and `false` is the check that actually says no -- the
# shape of an optional linter in front of a real test run. The status is 1, so
# the gate ran and something failed, and the environment's excuse would bury
# that even though a tool really is absent. Note the first word is clean: with
# `tool; false` the semicolon sticks to it and the name test below would refuse
# the excuse for the wrong reason, so this case would pin nothing.
dir="$(fixture 'lean-no-such-tool ; false')"
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
expect_code "gate: a compound line that fails on its own still blocks" 2
case "$err" in
  *"Quality Gate failed: lean-no-such-tool ; false"*)
    ok "gate: a status other than 127 is a failure whatever the first word is" ;;
  *) bad "gate: a status other than 127 is a failure whatever the first word is (got: $err)" ;;
esac

# 33. A word that could not be a program name is not a missing tool. A gate
# command wrapped over two lines hands the extractor its continuation as a
# command of its own, and an option is nobody's package to install: the block is
# malformed, which is this repository's business, so it takes the ordinary
# message and sends the agent to look. The indent is load-bearing -- `-x` at the
# very start of the line makes bash reject it as its own invocation option and
# exit 2, and only an indented or assignment-prefixed one reaches the shell as a
# command word and exits 127, which is the status that can claim the excuse. The
# class allows `-` inside a name and refuses it in front; case 26's
# `lean-no-such-tool` pins the half this case does not.
dir="$(fixture '  -x code.txt')"
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
expect_code "gate: an option-shaped word still blocks" 2
case "$err" in
  *"Quality Gate failed:   -x code.txt"*)
    ok "gate: an option is not reported as a missing tool" ;;
  *) bad "gate: an option is not reported as a missing tool (got: $err)" ;;
esac

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
