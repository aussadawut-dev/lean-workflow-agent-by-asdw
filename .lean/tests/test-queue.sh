#!/usr/bin/env bash
# Tests for .lean/bin/queue.sh, the `full` mode task queue. Each case runs
# against a throwaway bare remote with two clones, which is the arrangement the
# claim protocol exists for: two sessions, one item.
# Usage: .lean/tests/test-queue.sh

set -u

repo="$(cd "$(dirname "$0")/../.." && pwd)"
queue="$repo/.lean/bin/queue.sh"
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

# A bare remote plus two clones with one commit on the default branch. Prints the
# directory holding remote.git, A, and B.
pair() {
  local dir
  dir="$(mktemp -d "$work/pair.XXXX")"
  git init -q --bare "$dir/remote.git"
  git clone -q "$dir/remote.git" "$dir/A" 2>/dev/null
  git clone -q "$dir/remote.git" "$dir/B" 2>/dev/null
  local clone
  for clone in A B; do
    git -C "$dir/$clone" config user.email "$clone@test"
    git -C "$dir/$clone" config user.name "$clone"
  done
  echo start > "$dir/A/file.txt"
  git -C "$dir/A" add -A
  git -C "$dir/A" commit -qm init
  git -C "$dir/A" push -q origin HEAD 2>/dev/null
  git -C "$dir/B" fetch -q origin 2>/dev/null
  echo "$dir"
}

# A bare remote plus n clones (c1..cn) with one commit on the default branch, for
# the cases that need several sessions writing at once. Prints the directory.
fleet() {
  local n="$1" dir i
  dir="$(mktemp -d "$work/fleet.XXXX")"
  git init -q --bare "$dir/remote.git"
  for i in $(seq 1 "$n"); do
    git clone -q "$dir/remote.git" "$dir/c$i" 2>/dev/null
    git -C "$dir/c$i" config user.email "c$i@test"
    git -C "$dir/c$i" config user.name "c$i"
  done
  echo start > "$dir/c1/file.txt"
  git -C "$dir/c1" add -A
  git -C "$dir/c1" commit -qm init
  git -C "$dir/c1" push -q origin HEAD 2>/dev/null
  echo "$dir"
}

# q <clone dir> <args...>; sets $out and $code
q() {
  local dir="$1"
  shift
  out="$(CLAUDE_PROJECT_DIR="$dir" bash "$queue" "$@" 2>&1)"
  code=$?
}

# 1. An added item is open, owned by nobody, and visible to the other clone --
# the queue is shared state or it is nothing.
dir="$(pair)"
q "$dir/A" add "Add login flow"
expect "add: exits 0" "$code" "0"
expect "add: prints the id derived from the title" "$out" "add-login-flow"
q "$dir/A" list
contains "list: shows the new item as open" "$out" "add-login-flow                           open     -"
q "$dir/B" list
contains "list: the other clone sees it" "$out" "add-login-flow"

# 2. A second item with the same title gets its own id rather than overwriting.
q "$dir/A" add "Add login flow"
expect "add: a repeated title gets a distinct id" "$out" "add-login-flow-2"

# 3. A claim records the owner, and the other clone can read it.
q "$dir/A" claim add-login-flow
expect "claim: exits 0" "$code" "0"
q "$dir/B" show add-login-flow
contains "claim: records the status" "$out" "status: claimed"
contains "claim: records the owner" "$out" "owner: A@test"

# 4. The race the protocol is for: B computes its claim against the queue as it
# was before A's claim, so its push is rejected rather than silently winning.
# Both clones hold the item open at that point, so a check on status alone would
# hand it to both of them.
dir="$(pair)"
q "$dir/A" add "Ship the parser"
q "$dir/B" list                      # B's last look at the queue: item open
q "$dir/A" claim ship-the-parser
expect "race: the first claim wins" "$code" "0"
out="$(LEAN_QUEUE_NO_FETCH=1 CLAUDE_PROJECT_DIR="$dir/B" bash "$queue" claim ship-the-parser 2>&1)"
code=$?
expect "race: the second claim exits 3" "$code" "3"
contains "race: the loser is told who holds it" "$out" "claimed by A@test"
q "$dir/B" show ship-the-parser
contains "race: the winner still owns the item" "$out" "owner: A@test"

# 5. A claim on an item someone else holds is refused with the same code, with no
# race involved.
q "$dir/B" claim ship-the-parser
expect "claim: an item held by someone else exits 3" "$code" "3"

# 6. Re-claiming your own item is not a failure: a resumed session says so and
# carries on.
q "$dir/A" claim ship-the-parser
expect "claim: re-claiming your own item exits 0" "$code" "0"
contains "claim: re-claiming says it is already yours" "$out" "already claimed by you"

# 7. Only the holder can close the item.
q "$dir/B" "done" ship-the-parser
expect "done: a non-holder exits 3" "$code" "3"
contains "done: a non-holder is told who holds it" "$out" "claimed by A@test"

# 8. The holder can, and a done item is not claimable again.
q "$dir/A" "done" ship-the-parser
expect "done: the holder closes the item" "$code" "0"
q "$dir/B" claim ship-the-parser
expect "claim: a done item exits 3" "$code" "3"
contains "claim: a done item says it is not open" "$out" "not open (done)"

# 9. release returns the item to the pool, and someone else can then take it.
dir="$(pair)"
q "$dir/A" add "Rotate the keys"
q "$dir/A" claim rotate-the-keys
q "$dir/B" release rotate-the-keys
expect "release: a non-holder exits 3" "$code" "3"
q "$dir/A" release rotate-the-keys
expect "release: the holder releases the item" "$code" "0"
q "$dir/B" show rotate-the-keys
contains "release: the item is open again" "$out" "status: open"
contains "release: the owner is cleared" "$out" "owner: -"
q "$dir/B" claim rotate-the-keys
expect "release: the other clone can claim it" "$code" "0"

# 10. list orders by what a session needs first: open, then claimed, then done.
dir="$(pair)"
head_before="$(git -C "$dir/A" rev-parse HEAD)"
q "$dir/A" add "Aaa done item"
q "$dir/A" claim aaa-done-item
q "$dir/A" "done" aaa-done-item
q "$dir/A" add "Bbb claimed item"
q "$dir/A" claim bbb-claimed-item
q "$dir/A" add "Ccc open item"
q "$dir/A" list
order="$(printf '%s\n' "$out" | sed -n '2,$p' | awk '{print $2}' | tr '\n' ' ')"
expect "list: open first, then claimed, then done" "$order" "open claimed done "

# 11. The queue never touches the work: no checkout, no local branch, no change
# to the tree or to HEAD. A queue that dirtied the tree would break the Quality
# Gate's state and every diff the session reports.
expect "queue: the working tree stays clean" "$(git -C "$dir/A" status --porcelain)" ""
expect "queue: no local queue branch is created" \
  "$(git -C "$dir/A" branch --list lean-queue)" ""
expect "queue: HEAD is untouched" "$(git -C "$dir/A" rev-parse HEAD)" "$head_before"

# 12. An id nobody added is an error, not an empty claim.
q "$dir/A" claim no-such-item
expect "claim: an unknown id exits 1" "$code" "1"
contains "claim: an unknown id says so" "$out" "no such queue item"

# 13. Without a remote the queue still works, on a local branch. Claims
# coordinate nothing outside the checkout, which MODES.md says; the commands must
# not fail for it.
solo="$(mktemp -d "$work/solo.XXXX")"
git init -q "$solo"
git -C "$solo" config user.email solo@test
git -C "$solo" config user.name solo
echo x > "$solo/file.txt"
git -C "$solo" add -A
git -C "$solo" commit -qm init
q "$solo" add "Local only"
expect "no remote: add works" "$code" "0"
q "$solo" claim local-only
expect "no remote: claim works" "$code" "0"
q "$solo" show local-only
contains "no remote: the claim is recorded" "$out" "owner: solo@test"
out="$(LEAN_QUEUE_OWNER=other@test CLAUDE_PROJECT_DIR="$solo" bash "$queue" claim local-only 2>&1)"
code=$?
expect "no remote: another owner is still refused" "$code" "3"
expect "no remote: the working tree stays clean" "$(git -C "$solo" status --porcelain)" ""

# 14. An explicit branch name is honoured, so two queues can share a repository.
q "$solo" add "Second queue item"
LEAN_QUEUE_BRANCH=other-queue CLAUDE_PROJECT_DIR="$solo" bash "$queue" add "Elsewhere" >/dev/null
out="$(LEAN_QUEUE_BRANCH=other-queue CLAUDE_PROJECT_DIR="$solo" bash "$queue" list 2>&1)"
contains "branch: the override holds its own items" "$out" "elsewhere"
case "$out" in
  *second-queue-item*) bad "branch: the override does not see the default queue (got: $out)" ;;
  *) ok "branch: the override does not see the default queue" ;;
esac

# 15. An owner is a string, not a pattern. `&`, `|` and a backslash are ordinary
# characters in an email or a hostname, and splicing them into a rewrite
# corrupted the item: the claim reported success while writing a header nobody
# could read, so the item could never be claimed, released, or closed again.
dir="$(pair)"
q "$dir/A" add "Escape the owner"
weird='a&b|c\1@test'
out="$(LEAN_QUEUE_OWNER="$weird" CLAUDE_PROJECT_DIR="$dir/A" bash "$queue" claim escape-the-owner 2>&1)"
code=$?
expect "owner: a claim by an owner with sed metacharacters exits 0" "$code" "0"
q "$dir/B" show escape-the-owner
contains "owner: the owner is recorded verbatim" "$out" "owner: $weird"
contains "owner: the item still parses" "$out" "status: claimed"
out="$(LEAN_QUEUE_OWNER="$weird" CLAUDE_PROJECT_DIR="$dir/A" bash "$queue" release escape-the-owner 2>&1)"
code=$?
expect "owner: the same owner can release it again" "$code" "0"

# 16. The claim protocol, run for real: several sessions racing one item, no
# staged staleness. Exactly one may win, and the item must end up owned by the
# one that did.
dir="$(fleet 4)"
q "$dir/c1" add "One item many claimers"
for i in 1 2 3 4; do
  (
    res="$(CLAUDE_PROJECT_DIR="$dir/c$i" bash "$queue" claim one-item-many-claimers 2>&1)"
    echo "$? $res" > "$dir/result.$i"
  ) &
done
wait
won=0
for i in 1 2 3 4; do
  read -r rc rest < "$dir/result.$i"
  [ "$rc" = "0" ] && { won=$((won + 1)); winner="c$i"; }
  case "$rc $rest" in
    0*) ;;
    3*"claimed by"*) ;;
    4*"kept moving"*) ;;
    *) bad "race: a loser reported something else (got: $rc $rest)" ;;
  esac
done
expect "race: exactly one of four concurrent claimers wins" "$won" "1"
q "$dir/c1" show one-item-many-claimers
contains "race: the item is owned by the winner" "$out" "owner: ${winner:-none}@test"

# 17. The other half: concurrent writers on *different* items are not a race at
# all, and none of them may be starved out. A rejected push says nothing about
# this item, so it is retried rather than reported as held -- which is what
# `exit 3` would have claimed, sending an agent away from an open item.
dir="$(fleet 4)"
for i in 1 2 3 4; do
  q "$dir/c1" add "Item number $i"
done
for i in 1 2 3 4; do
  (
    CLAUDE_PROJECT_DIR="$dir/c$i" bash "$queue" claim "item-number-$i" >/dev/null 2>&1
    echo "$?" > "$dir/result.$i"
  ) &
done
wait
codes="$(cat "$dir"/result.1 "$dir"/result.2 "$dir"/result.3 "$dir"/result.4 | tr '\n' ' ')"
expect "concurrency: four claims of four items all succeed" "$codes" "0 0 0 0 "

# 18. Adding is the first thing a session does in `full` mode, so it is retried
# on a rejected push like any other write.
dir="$(fleet 4)"
for i in 1 2 3 4; do
  (
    CLAUDE_PROJECT_DIR="$dir/c$i" bash "$queue" add "Concurrent add $i" >/dev/null 2>&1
    echo "$?" > "$dir/result.$i"
  ) &
done
wait
codes="$(cat "$dir"/result.1 "$dir"/result.2 "$dir"/result.3 "$dir"/result.4 | tr '\n' ' ')"
expect "concurrency: four concurrent adds all succeed" "$codes" "0 0 0 0 "
q "$dir/c1" list
added="$(printf '%s\n' "$out" | grep -c 'concurrent-add-')"
expect "concurrency: all four items are in the queue" "$added" "4"

# 19. Running out of attempts is not the same answer as "someone holds it": one
# is a transient the caller should retry, the other is a decision about the item.
# Staged with one attempt against a stale base, which is a guaranteed rejection.
dir="$(pair)"
q "$dir/A" add "Exhausted retries"
q "$dir/B" list
q "$dir/A" add "Something else"
out="$(LEAN_QUEUE_NO_FETCH=1 LEAN_QUEUE_ATTEMPTS=1 CLAUDE_PROJECT_DIR="$dir/B" \
  bash "$queue" claim exhausted-retries 2>&1)"
code=$?
expect "retries: running out of attempts exits 4, not 3" "$code" "4"
contains "retries: the message says nothing was decided" "$out" "nothing about this item was decided"

# 20. The queue writes with plumbing, which does not know about checkouts: aimed
# at the branch the session has checked out it would commit onto that work and
# leave the index reporting the queue files as deleted.
dir="$(pair)"
head_before="$(git -C "$dir/A" rev-parse HEAD)"
current="$(git -C "$dir/A" rev-parse --abbrev-ref HEAD)"
out="$(LEAN_QUEUE_BRANCH="$current" CLAUDE_PROJECT_DIR="$dir/A" bash "$queue" add "Onto my branch" 2>&1)"
code=$?
expect "checkout: a queue aimed at the checked-out branch is refused" "$code" "1"
contains "checkout: the refusal says why" "$out" "is checked out"
expect "checkout: no commit was added to it" "$(git -C "$dir/A" rev-parse HEAD)" "$head_before"
expect "checkout: the tree is still clean" "$(git -C "$dir/A" status --porcelain)" ""

# 21. An id is a path in the queue tree. One that climbs out of it, or holds
# anything but the characters a slug is made of, is refused before any write.
q "$dir/A" claim "../../etc/passwd"
expect "id: a traversing id is refused" "$code" "1"
contains "id: the refusal names the id" "$out" "not a usable queue id"

# 22. A title spanning lines still makes a one-line id: the id becomes a path and
# a header value, and a newline in either makes the item unreadable.
q "$dir/A" add "$(printf 'two\nlines')"
expect "add: a multi-line title makes a single-line id" "$out" "two-lines"

# 23. An owner is checked for control characters, not for being ASCII. Plenty of
# CI images run under LC_ALL=C, where a non-ASCII user.email would otherwise fail
# every queue command with a reason that is not true of it.
dir="$(pair)"
q "$dir/A" add "Unicode owner"
out="$(LC_ALL=C LEAN_QUEUE_OWNER='josé@test' CLAUDE_PROJECT_DIR="$dir/A" \
  bash "$queue" claim unicode-owner 2>&1)"
code=$?
expect "locale: a non-ASCII owner is accepted under LC_ALL=C" "$code" "0"
q "$dir/A" show unicode-owner
contains "locale: the non-ASCII owner is recorded" "$out" "owner: josé@test"

# 24. An attempt count that is not a positive number is a usage error. Left to
# `seq` it printed its own error and then claimed the branch kept moving, which
# asserts a race that never happened.
for bad_value in abc 0 -1; do
  out="$(LEAN_QUEUE_ATTEMPTS="$bad_value" CLAUDE_PROJECT_DIR="$dir/A" \
    bash "$queue" claim unicode-owner 2>&1)"
  code=$?
  expect "attempts: '$bad_value' is a usage error, not a race" "$code" "1"
  contains "attempts: the refusal names the value" "$out" "not '$bad_value'"
done

# 25. Checking the queue branch out to read it is a reasonable thing to do,
# especially with no remote, where it is the only copy. Reads keep working;
# only the writes refuse, because those would commit onto that checkout.
solo="$(mktemp -d "$work/checkout.XXXX")"
git init -q "$solo"
git -C "$solo" config user.email solo@test
git -C "$solo" config user.name solo
echo x > "$solo/file.txt"
git -C "$solo" add -A
git -C "$solo" commit -qm init
q "$solo" add "Read me while checked out"
git -C "$solo" checkout -q lean-queue
q "$solo" list
contains "checkout: list still works from a checkout of the queue branch" "$out" "read-me-while-checked-out"
q "$solo" show read-me-while-checked-out
contains "checkout: show still works" "$out" "status: open"
q "$solo" claim read-me-while-checked-out
expect "checkout: a write refuses" "$code" "1"
contains "checkout: the refusal says the branch is checked out" "$out" "is checked out"
expect "checkout: the checkout is untouched" "$(git -C "$solo" status --porcelain)" ""

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
