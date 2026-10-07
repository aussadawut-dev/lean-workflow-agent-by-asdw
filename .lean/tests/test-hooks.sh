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

# run_gate <dir> <stdin json>; sets $code, $err and $out
run_gate() {
  # These legacy cases intentionally edit gate commands; acceptance is fixture setup.
  python3 "$repo/.lean/scripts/gate_evidence.py" --root "$1" accept-controls --reason 'Fixture intentionally selected these controls' >/dev/null || return
  err="$(printf '%s' "$2" | CLAUDE_PROJECT_DIR="$1" bash "$gate" --cache-tree 2>&1 >"$work/stdout")"
  code=$?
  out="$(cat "$work/stdout")"
}

expect_code() {
  if [ "$code" -eq "$2" ]; then ok "$1"; else bad "$1 (exit $code, want $2)"; fi
}

# 1. No PROJECT.md
dir="$(mktemp -d "$work/empty.XXXX")"
run_gate "$dir" '{}'
expect_code "gate: no PROJECT.md is undefined" 2

# 2. Empty gate block
dir="$(fixture)"
echo change > "$dir/file.txt"
run_gate "$dir" '{}'
expect_code "gate: empty block is undefined" 2

# 3. Failing command blocks with a message
dir="$(fixture 'false')"
echo change > "$dir/file.txt"
run_gate "$dir" '{"stop_hook_active": false}'
expect_code "gate: failing command exits 2" 2
case "$err" in
  *"Quality Gate failed: false"*) ok "gate: failure names the command" ;;
  *) bad "gate: failure names the command (got: $err)" ;;
esac

# 4. stop_hook_active no longer waves a failing gate through, but the loop is bounded:
# after three refusals the Stop is released UNVERIFIED, never recorded as a pass.
run_gate "$dir" '{"stop_hook_active":true}'
expect_code "gate: stop_hook_active still refuses a failing gate (2nd refusal)" 2
run_gate "$dir" '{"stop_hook_active":true}'
expect_code "gate: stop_hook_active still refuses a failing gate (3rd refusal)" 2
run_gate "$dir" '{"stop_hook_active":true}'
expect_code "gate: continued failure is released after three refusals" 0
case "$out" in
  *'"systemMessage"'*UNVERIFIED*) ok "gate: the release tells the user the work is unverified" ;;
  *) bad "gate: the release tells the user the work is unverified (got: $out)" ;;
esac
if [ -f "$dir/.claude/.gate-failed" ] && [ ! -f "$dir/.claude/.gate-cache" ]; then
  ok "gate: a release keeps the refusal and caches nothing"
else
  bad "gate: a release keeps the refusal and caches nothing"
fi
run_gate "$dir" '{"stop_hook_active":false}'
expect_code "gate: a fresh Stop is gated again after the cap" 2
if [ "$(cat "$dir/.claude/.gate-failed")" = "1" ]; then ok "gate: a fresh refusal restarts the count"; else bad "gate: a fresh refusal restarts the count"; fi

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
expect_code "gate: seed is not proof a failing gate passed" 2

# 7. Seeded, then something changed: the gate runs.
echo change > "$dir/code.txt"
run_gate "$dir" '{}'
expect_code "gate: seeded then changed runs" 2

# 8. --seed records the state and runs no commands.
counter="$work/seeded"
: > "$counter"
dir="$(fixture "echo run >> '$counter'")"
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed
if [ -s "$dir/.agent-runtime/gate-baseline" ] && [ ! -s "$counter" ] && [ ! -f "$dir/.claude/.gate-cache" ]; then
  ok "gate: --seed records baseline without validating"
else
  bad "gate: --seed records baseline without validating"
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

# 14. Session hook is silent once Purpose and the gate are filled
dir="$(fixture true)"
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
if [ -s "$dir/.agent-runtime/gate-baseline" ]; then
  ok "session: records the change baseline"
else
  bad "session: records the change baseline"
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
# Distinct untracked file boundaries must invalidate a passing cache.
dir="$(fixture "test \"\$(cat a)\" = A")"
printf A > "$dir/a"
printf BC > "$dir/b"
run_gate "$dir" '{}'
expect_code "gate: initial untracked boundary fixture passes" 0
printf AB > "$dir/a"
printf C > "$dir/b"
run_gate "$dir" '{}'
expect_code "gate: redistributed untracked bytes rerun and fail" 2


# Contract line enforcement. The transcript is JSONL; only assistant entries count.
contract_case() { # <name> <want> <transcript body>
  local d t
  d="$(fixture 'true')"
  echo change > "$d/file.txt"
  t="$work/transcript.$RANDOM.jsonl"
  printf '%s\n' "$3" > "$t"
  run_gate "$d" "{\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"
  expect_code "$1" "$2"
}
contract_case "contract: real assistant Contract line passes" 0 \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"Contract: risk=LOW quality=STANDARD acceptance=tests pass\nDone"}]}}'
contract_case "contract: trivial form passes" 0 \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"Contract: trivial (typo)"}]}}'
contract_case "contract: missing line blocks" 2 \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"Done."}]}}'
contract_case "contract: template placeholders do not count" 2 \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"Contract: risk=<LOW|MEDIUM|HIGH> quality=<STANDARD|HIGH|VERY_HIGH> acceptance=<observable check> / Contract: trivial (<reason>)"}]}}'
contract_case "contract: a line in a user entry does not count" 2 \
  '{"type":"user","message":{"content":"Contract: risk=LOW quality=STANDARD acceptance=tests pass"}}'
dir="$(fixture 'true')"
echo change > "$dir/file.txt"
run_gate "$dir" '{"stop_hook_active":false,"transcript_path":"/nonexistent/t.jsonl"}'
expect_code "contract: unreadable transcript blocks with a diagnostic" 2
contract_case "contract: block message tells how to fix" 2 '{"type":"assistant","message":{"content":"x"}}'
case "$err" in
  *"No Task Contract first line"*) ok "contract: block message is specific" ;;
  *) bad "contract: block message is specific (got: $err)" ;;
esac


# Tool input holding a real-valued Contract line is not a reply line.
contract_case "contract: a line inside tool_use input does not count" 2 \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","input":{"new_string":"Contract: risk=LOW quality=STANDARD acceptance=tests pass"}}]}}'
contract_case "contract: a contract after prose is not a first line" 2 \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"say \"hi\"\nContract: risk=LOW quality=STANDARD acceptance=x ok"}]}}'

# A contract refusal says nothing about the code: a later chat-only session must not inherit it.
dir="$(fixture 'true')"
t="$work/t-none.jsonl"; printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"text","text":"hi"}]}}' > "$t"
echo change > "$dir/file.txt"
run_gate "$dir" "{\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"
expect_code "contract: first refusal" 2
if [ "$(cat "$dir/.claude/.gate-failed")" = "c1" ]; then ok "contract: marker is a contract marker"; else bad "contract: marker is a contract marker"; fi
run_gate "$dir" "{\"stop_hook_active\":true,\"transcript_path\":\"$t\"}"
expect_code "contract: continued refusal (2nd)" 2
run_gate "$dir" "{\"stop_hook_active\":true,\"transcript_path\":\"$t\"}"
expect_code "contract: continued refusal (3rd)" 2
run_gate "$dir" "{\"stop_hook_active\":true,\"transcript_path\":\"$t\"}"
expect_code "contract: continued refusal is released after three refusals" 0
case "$(cat "$dir/.claude/.gate-failed")" in
  c*) ok "contract: a released refusal stays a contract refusal" ;;
  *) bad "contract: a released refusal stays a contract refusal" ;;
esac
# New session: seed clears the contract marker, so a session that changes nothing is not gated.
git -C "$dir" -c user.name=t -c user.email=t@t add -A
git -C "$dir" -c user.name=t -c user.email=t@t commit -qm change
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed </dev/null
if [ ! -f "$dir/.claude/.gate-failed" ]; then ok "contract: seed clears a contract marker"; else bad "contract: seed clears a contract marker"; fi
run_gate "$dir" "{\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"
expect_code "contract: chat-only follow-up session is not blocked" 0

# No transcript_path in the input: not checked.
dir="$(fixture 'true')"
echo change > "$dir/file.txt"
run_gate "$dir" '{"stop_hook_active":false}'
expect_code "contract: missing transcript_path is not checked" 0

# Runtime-injected user entries are not human turns: skill bodies, Stop hook
# feedback, background task notifications and compaction summaries.
human='{"type":"user","message":{"content":"please change file"}}'
said='{"type":"assistant","message":{"content":[{"type":"text","text":"Contract: risk=LOW quality=STANDARD acceptance=tests pass"}]}}'
edit='{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","input":{}}]}}'
contract_case "contract: a loaded skill body does not end the turn" 0 "$human
$said
{\"type\":\"user\",\"isMeta\":true,\"message\":{\"content\":[{\"type\":\"text\",\"text\":\"Base directory for this skill: x\"}]}}
$edit"
contract_case "contract: Stop hook feedback cannot excuse an earlier write" 2 "$human
$edit
{\"type\":\"user\",\"isMeta\":true,\"message\":{\"content\":[{\"type\":\"text\",\"text\":\"Stop hook feedback: no contract\"}]}}
$said"
contract_case "contract: a task notification does not end the turn" 0 "$human
$said
{\"type\":\"user\",\"message\":{\"content\":\"<task-notification> <task-id>a1</task-id> </task-notification>\"}}
$edit"
contract_case "contract: a compaction summary does not end the turn" 0 "$human
$said
{\"type\":\"user\",\"isCompactSummary\":true,\"message\":{\"content\":\"This session is being continued\"}}
$edit"
contract_case "contract: a new human prompt still needs a new contract" 2 "$human
$said
{\"type\":\"user\",\"message\":{\"content\":\"now change it again\"}}
$edit"

# High-risk areas in PROJECT.md set a review floor that a low contract cannot lower.
risky_fixture() {
  local d
  d="$(fixture 'true')"
  # shellcheck disable=SC2016 # literal Markdown backticks
  printf '\n## High-risk areas\n\n- `secure/`: auth boundary.\n- `deploy/*.yml`: production config.\n\n## Other\n\n- `not/listed/`\n' >> "$d/.lean/PROJECT.md"
  git -C "$d" -c user.name=t -c user.email=t@t commit -qam areas
  echo "$d"
}
low="Contract: risk=LOW quality=STANDARD acceptance=tests pass"
t="$work/t-low.jsonl"; printf '%s\n' "$said" > "$t"
dir="$(risky_fixture)"
mkdir -p "$dir/secure"; echo x > "$dir/secure/auth.py"
run_gate "$dir" "{\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"
expect_code "risk: a LOW contract in a high-risk area needs a review receipt" 2
case "$err" in
  *"High-risk areas changed"*"secure/auth.py"*) ok "risk: refusal names the high-risk path" ;;
  *) bad "risk: refusal names the high-risk path (got: $err)" ;;
esac
evidence() { python3 "$repo/.lean/scripts/gate_evidence.py" --root "$dir" "$@"; }
evidence record-review --contract "$low" --reviewer independent --evidence 'round 1, no findings' \
  --verdict PASS --state "$(evidence state)" >/dev/null
run_gate "$dir" "{\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"
expect_code "risk: a matching review receipt satisfies the floor" 0
dir="$(risky_fixture)"
echo x > "$dir/elsewhere.txt"; mkdir -p "$dir/not/listed"; echo x > "$dir/not/listed/f"
run_gate "$dir" "{\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"
expect_code "risk: paths outside High-risk areas keep the contract depth" 0
dir="$(risky_fixture)"
mkdir -p "$dir/deploy"; echo x > "$dir/deploy/prod.yml"
run_gate "$dir" "{\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"
expect_code "risk: glob areas match" 2
dir="$(risky_fixture)"
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed </dev/null
mkdir -p "$dir/secure"; echo x > "$dir/secure/auth.py"
git -C "$dir" -c user.name=t -c user.email=t@t add -A
git -C "$dir" -c user.name=t -c user.email=t@t commit -qm risky
run_gate "$dir" "{\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"
expect_code "risk: work committed during the session still counts" 2
dir="$(risky_fixture)"
mkdir -p "$dir/secure"; echo x > "$dir/secure/auth.py"
run_gate "$dir" '{"stop_hook_active":false}'
expect_code "risk: a high-risk change without any contract is refused" 2

dir="$(risky_fixture)"
mkdir -p "$dir/secure"; echo x > "$dir/secure/auth.py"
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed </dev/null
t="$work/t-chat.jsonl"; printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"text","text":"hi"}]}}' > "$t"
run_gate "$dir" "{\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"
expect_code "risk: a chat-only turn over an inherited high-risk change is not refused" 0
# A Lean root below the Git toplevel matches areas against root-relative paths.
outer="$(mktemp -d "$work/outer.XXXX")"
git -C "$outer" init -q
dir="$outer/app"; mkdir -p "$dir/.lean" "$dir/secure"
cp "$(risky_fixture)/.lean/PROJECT.md" "$dir/.lean/PROJECT.md"
echo old > "$dir/secure/auth.py"
git -C "$outer" -c user.name=t -c user.email=t@t add -A
git -C "$outer" -c user.name=t -c user.email=t@t commit -qm init
echo new > "$dir/secure/auth.py"
t="$work/t-low.jsonl"
run_gate "$dir" "{\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"
expect_code "risk: a nested Lean root still sees tracked high-risk edits" 2

# Every hook refusal after input parsing counts toward the cap, including
# protected-control drift and an undefined gate.
run_raw() { # <dir> <stdin json>; no fixture control acceptance
  err="$(printf '%s' "$2" | CLAUDE_PROJECT_DIR="$1" bash "$gate" 2>&1 >"$work/stdout")"
  code=$?
  out="$(cat "$work/stdout")"
}
dir="$(fixture 'true')"
run_raw "$dir" '{"stop_hook_active":false}'
expect_code "cap: first use records gate controls" 0
sed -i.bak 's/^true$/test -d ./' "$dir/.lean/PROJECT.md" && rm -f "$dir/.lean/PROJECT.md.bak"
run_raw "$dir" '{"stop_hook_active":false}'
expect_code "cap: changed controls refuse" 2
run_raw "$dir" '{"stop_hook_active":true}'
run_raw "$dir" '{"stop_hook_active":true}'
expect_code "cap: changed controls still refuse (3rd)" 2
run_raw "$dir" '{"stop_hook_active":true}'
expect_code "cap: changed-control refusals are released after three" 0
case "$out" in *UNVERIFIED*) ok "cap: control release is marked unverified" ;; *) bad "cap: control release is marked unverified (got: $out)" ;; esac
dir="$(fixture 'true')"
rm "$dir/.lean/PROJECT.md"
for active in false true true; do run_raw "$dir" "{\"stop_hook_active\":$active}"; done
expect_code "cap: an undefined gate still refuses (3rd)" 2
run_raw "$dir" '{"stop_hook_active":true}'
expect_code "cap: undefined-gate refusals are released after three" 0
dir="$(fixture 'true')"
rm "$dir/.lean/PROJECT.md"
CLAUDE_PROJECT_DIR="$dir" bash "$gate" --seed </dev/null
if [ ! -f "$dir/.claude/.gate-failed" ]; then ok "cap: seed never records a refusal"; else bad "cap: seed never records a refusal"; fi

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
