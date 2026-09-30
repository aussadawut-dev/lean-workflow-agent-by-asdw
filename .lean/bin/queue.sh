#!/usr/bin/env bash
# Task queue with git-backed claims. Used by the `full` workflow mode; see
# .lean/policy/MODES.md.
#
#   queue.sh list                open items first, then claimed, then done
#   queue.sh show <id>
#   queue.sh add <title>         prints the new id
#   queue.sh claim <id>          exit 3: someone else holds it
#   queue.sh release <id>
#   queue.sh done <id>
#
# Exit codes: 0 done, 1 usage or a bad argument, 3 the item's state says no
# (held by someone else, not claimed, already done), 4 the queue branch kept
# moving under this write -- nothing was decided, so try again.
#
# Items live on their own branch -- `lean-queue`, or LEAN_QUEUE_BRANCH -- one
# file per item at queue/<id>.md. Nothing is checked out and the working tree is
# never touched: every write is a commit built with plumbing against the branch
# as the remote currently has it, and pushed. That push is the whole claim
# protocol. Two sessions that claim the same item build on the same parent, so
# the second push is rejected as non-fast-forward, and the loser re-reads the
# item and reports who holds it. A repository with no `origin` keeps the branch
# locally and claims are local only.
#
# A write rejected because the branch moved is retried (LEAN_QUEUE_ATTEMPTS, default
# 8) with a short randomized backoff before it gives up with exit 4.
#
# Identity is LEAN_QUEUE_OWNER, else git's user.email. To take over a claim
# whose owner is gone, run with LEAN_QUEUE_OWNER set to the recorded owner.

set -u

root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$root" || exit 1

branch="${LEAN_QUEUE_BRANCH:-lean-queue}"
remote="${LEAN_QUEUE_REMOTE:-origin}"
attempts="${LEAN_QUEUE_ATTEMPTS:-8}"

die() { echo "$1" >&2; exit "${2:-1}"; }

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not a git repository: $root"

case "$attempts" in
  "" | *[!0-9]* | 0) die "LEAN_QUEUE_ATTEMPTS must be a positive whole number, not '$attempts'" ;;
esac


owner="${LEAN_QUEUE_OWNER:-$(git config user.email 2>/dev/null || true)}"
[ -n "$owner" ] || owner="$(id -un)@$(hostname 2>/dev/null || echo local)"
# One header line per field, so an owner spanning lines would rewrite the item
# into something no other session can read.
case "$owner" in
  *[[:cntrl:]]*) die "the queue owner may not contain control characters or newlines: LEAN_QUEUE_OWNER=$owner" ;;
esac

# commit-tree needs an identity even where the repository has none configured.
if [ -z "$(git config user.email 2>/dev/null || true)" ]; then
  export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-lean-queue}"
  export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-$owner}"
  export GIT_COMMITTER_NAME="${GIT_COMMITTER_NAME:-lean-queue}"
  export GIT_COMMITTER_EMAIL="${GIT_COMMITTER_EMAIL:-$owner}"
fi

has_remote=0
git remote get-url "$remote" >/dev/null 2>&1 && has_remote=1

base_ref() {
  if [ "$has_remote" = 1 ]; then
    echo "refs/remotes/$remote/$branch"
  else
    echo "refs/heads/$branch"
  fi
}

# Empty when the queue branch does not exist yet.
base_commit() { git rev-parse --verify -q "$(base_ref)" || true; }

fetch_queue() {
  [ "$has_remote" = 1 ] || return 0
  git fetch -q "$remote" "+refs/heads/$branch:$(base_ref)" 2>/dev/null || true
}

now() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }

item_path() { echo "queue/$1.md"; }

# An id becomes a path in the queue tree and a word in every message about it.
check_id() {
  case "$1" in
    "" | -*) die "not a usable queue id: '$1'" ;;
    *[!a-z0-9._-]*) die "not a usable queue id: '$1' (lowercase letters, digits, '.', '_' and '-' only)" ;;
    *..*) die "not a usable queue id: '$1'" ;;
  esac
}

read_item() {
  local base
  base="$(base_commit)"
  [ -n "$base" ] || return 1
  git show "$base:$(item_path "$1")" 2>/dev/null
}

list_ids() {
  local base
  base="$(base_commit)"
  [ -n "$base" ] || return 0
  git ls-tree --name-only "$base:queue" 2>/dev/null | sed -n 's/\.md$//p'
}

# Header fields are the lines between the title and the first blank line. Read
# and written with awk, never sed: a value holding `&`, `|` or a backslash is an
# ordinary owner string, and sed would splice it into the replacement. The values
# reach awk through the environment rather than -v, which expands backslash
# escapes and turned an owner holding `\1` into a control character.
field() {
  QK="$2" awk '
    BEGIN { key = ENVIRON["QK"] }
    NF == 0 { exit }
    index($0, key ": ") == 1 { print substr($0, length(key) + 3); exit }
  ' <<< "$1"
}

set_field() {
  QK="$2" QV="$3" awk '
    BEGIN { key = ENVIRON["QK"]; value = ENVIRON["QV"] }
    !body && NF == 0 { body = 1 }
    !body && index($0, key ": ") == 1 { print key ": " value; next }
    { print }
  ' <<< "$1"
}

# Every field a later session reads has to survive the rewrite, or the item is
# wedged: nothing can claim, release or close it again.
check_header() {
  local content="$1" key
  for key in status owner updated; do
    [ -n "$(field "$content" "$key")" ] || return 1
  done
  return 0
}

# Build a commit adding or replacing one item, and print its sha. Uses a
# throwaway index so the repository's own index and working tree are untouched.
build_commit() {
  local id="$1" content="$2" message="$3" base index status
  base="$(base_commit)"
  index="$(mktemp)" || return 1
  rm -f "$index"
  (
    export GIT_INDEX_FILE="$index"
    if [ -n "$base" ]; then
      git read-tree "$base" || exit 1
    else
      git read-tree --empty || exit 1
    fi
    blob="$(printf '%s\n' "$content" | git hash-object -w --stdin)" || exit 1
    git update-index --add --cacheinfo "100644,$blob,$(item_path "$id")" || exit 1
    tree="$(git write-tree)" || exit 1
    if [ -n "$base" ]; then
      git commit-tree "$tree" -p "$base" -m "$message" || exit 1
    else
      git commit-tree "$tree" -m "$message" || exit 1
    fi
  )
  status=$?
  rm -f "$index"
  return $status
}

# Move the queue branch to $1, but only if it still points where this commit was
# built on. A rejected push or a failed compare-and-swap means someone else got
# there first; that is the race the claim protocol is made of, so it is a plain
# non-zero return. The reason is kept in $push_err for the caller that runs out
# of attempts, since an auth or network failure looks the same from here.
push_err=""
publish() {
  local commit="$1" old
  if [ "$has_remote" = 1 ]; then
    push_err="$(git push -q "$remote" "$commit:refs/heads/$branch" 2>&1)" || return 1
    git update-ref "$(base_ref)" "$commit"
    return 0
  fi
  old="$(base_commit)"
  push_err="$(git update-ref "refs/heads/$branch" "$commit" "$old" 2>&1)" || return 1
  return 0
}

# The queue branch is written by plumbing, which does not know about checkouts:
# aimed at a branch someone has checked out it would commit onto their work and
# leave their index reporting the queue files as deleted. Checked before a write
# rather than at startup, so reading the queue from a checkout of it still works.
assert_writable_branch() {
  local checked_out
  checked_out="$(git symbolic-ref --short -q HEAD || true)"
  if [ "$branch" = "$checked_out" ] ||
     git worktree list --porcelain 2>/dev/null | grep -qxF "branch refs/heads/$branch"; then
    die "the queue branch '$branch' is checked out; the queue never writes to a checked-out branch. Switch that checkout away, or point LEAN_QUEUE_BRANCH at the queue's own branch."
  fi
}

# A rejected push says nothing about this item: another session wrote another
# item. Backing off by a random fraction of a second keeps several sessions from
# re-colliding in lockstep.
backoff() { sleep "0.$((RANDOM % 4 + 1))"; }

slug() {
  printf '%s' "$1" |
    tr '\n\t' '  ' |
    tr '[:upper:]' '[:lower:]' |
    sed 's/[^a-z0-9]\{1,\}/-/g; s/^-*//; s/-*$//' |
    cut -c1-40 |
    sed 's/-*$//'
}

require_id() { [ -n "${1:-}" ] || die "usage: queue.sh $2 <id>"; }

# One state change, retried while the branch moves under it. The first fetch is
# skipped under LEAN_QUEUE_NO_FETCH, which is how the tests stage a lost race; a
# retry always fetches.
transition() {
  local id="$1" verb="$2" attempt content status holder new commit
  assert_writable_branch
  for attempt in $(seq 1 "$attempts"); do
    if [ "$attempt" != 1 ] || [ -z "${LEAN_QUEUE_NO_FETCH:-}" ]; then
      fetch_queue
    fi

    content="$(read_item "$id")" || die "no such queue item: $id"
    status="$(field "$content" status)"
    holder="$(field "$content" owner)"

    case "$verb" in
      claim)
        case "$status" in
          open) ;;
          claimed)
            [ "$holder" = "$owner" ] && { echo "already claimed by you: $id"; return 0; }
            die "claimed by $holder: $id" 3
            ;;
          *) die "not open ($status): $id" 3 ;;
        esac
        new="$(set_field "$content" status claimed)"
        new="$(set_field "$new" owner "$owner")"
        ;;
      release | "done")
        [ "$status" = "claimed" ] || die "not claimed ($status): $id" 3
        [ "$holder" = "$owner" ] || die "claimed by $holder, not you: $id" 3
        if [ "$verb" = "release" ]; then
          new="$(set_field "$content" status open)"
          new="$(set_field "$new" owner "-")"
        else
          new="$(set_field "$content" status "done")"
        fi
        ;;
    esac

    new="$(set_field "$new" updated "$(now)")"
    check_header "$new" || die "refusing to write $id: the rewritten item lost a header field"
    commit="$(build_commit "$id" "$new" "queue: $verb $id ($owner)")" ||
      die "could not build the queue commit for $id"
    if publish "$commit"; then
      echo "$verb $id"
      return 0
    fi
    backoff
  done
  die "could not $verb $id in $attempts attempts: the queue branch kept moving, so nothing about this item was decided. Last git message: ${push_err:-none}" 4
}

add_item() {
  local title="$1" attempt base_id id n item commit
  assert_writable_branch
  base_id="$(slug "$title")"
  [ -n "$base_id" ] || die "cannot make an id from: $title"
  for attempt in $(seq 1 "$attempts"); do
    fetch_queue
    id="$base_id"
    n=1
    while read_item "$id" >/dev/null 2>&1; do
      n=$((n + 1))
      id="$base_id-$n"
    done
    item="$(printf '# %s\nstatus: open\nowner: -\nupdated: %s\n' "$title" "$(now)")"
    commit="$(build_commit "$id" "$item" "queue: add $id")" ||
      die "could not build the queue commit for $id"
    if publish "$commit"; then
      echo "$id"
      return 0
    fi
    backoff
  done
  die "could not add '$title' in $attempts attempts: the queue branch kept moving, so nothing was added. Last git message: ${push_err:-none}" 4
}

case "${1:-list}" in
  list)
    fetch_queue
    printf '%-40s %-8s %s\n' "ID" "STATUS" "OWNER"
    for want in open claimed "done"; do
      while read -r id; do
        [ -n "$id" ] || continue
        content="$(read_item "$id")" || continue
        status="$(field "$content" status)"
        [ "$status" = "$want" ] || continue
        printf '%-40s %-8s %s\n' "$id" "$status" "$(field "$content" owner)"
      done <<< "$(list_ids)"
    done
    ;;

  show)
    require_id "${2:-}" show
    check_id "$2"
    fetch_queue
    read_item "$2" || die "no such queue item: $2"
    ;;

  add)
    shift
    title="$*"
    [ -n "$title" ] || die "usage: queue.sh add <title>"
    add_item "$title"
    ;;

  claim | release | "done")
    verb="$1"
    require_id "${2:-}" "$verb"
    check_id "$2"
    transition "$2" "$verb"
    ;;

  *)
    echo "usage: queue.sh [list|show <id>|add <title>|claim <id>|release <id>|done <id>]" >&2
    exit 1
    ;;
esac
