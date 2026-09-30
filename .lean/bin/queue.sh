#!/usr/bin/env bash
# Task queue with git-backed claims. Used by the `full` workflow mode; see
# .lean/policy/MODES.md.
#
#   queue.sh list                open items first, then claimed, then done
#   queue.sh show <id>
#   queue.sh add <title>         prints the new id
#   queue.sh claim <id>          exit 3 if someone else holds it
#   queue.sh release <id>
#   queue.sh done <id>
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
# Identity is LEAN_QUEUE_OWNER, else git's user.email. To take over a claim
# whose owner is gone, run with LEAN_QUEUE_OWNER set to the recorded owner.

set -u

root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$root" || exit 1

branch="${LEAN_QUEUE_BRANCH:-lean-queue}"
remote="${LEAN_QUEUE_REMOTE:-origin}"

die() { echo "$1" >&2; exit "${2:-1}"; }

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not a git repository: $root"

owner="${LEAN_QUEUE_OWNER:-$(git config user.email 2>/dev/null || true)}"
[ -n "$owner" ] || owner="$(id -un)@$(hostname 2>/dev/null || echo local)"

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

# Header fields are the lines between the title and the first blank line.
field() { printf '%s\n' "$1" | sed -n "1,/^\$/ s/^$2: //p" | head -1; }

set_field() {
  printf '%s\n' "$1" | sed "1,/^\$/ s|^$2: .*|$2: $3|"
}

# Build a commit adding or replacing one item, and print its sha. Uses a
# throwaway index so the repository's own index and working tree are untouched.
build_commit() {
  local id="$1" content="$2" message="$3" base tree blob commit index
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
      commit="$(git commit-tree "$tree" -p "$base" -m "$message")" || exit 1
    else
      commit="$(git commit-tree "$tree" -m "$message")" || exit 1
    fi
    printf '%s\n' "$commit"
  )
  local status=$?
  rm -f "$index"
  return $status
}

# Move the queue branch to $1, but only if it still points where this commit was
# built on. A rejected push or a failed compare-and-swap means someone else got
# there first; that is the race the claim protocol is made of, so it is a plain
# non-zero return, not an error message.
publish() {
  local commit="$1" old
  if [ "$has_remote" = 1 ]; then
    git push -q "$remote" "$commit:refs/heads/$branch" 2>/dev/null || return 1
    git update-ref "$(base_ref)" "$commit"
    return 0
  fi
  old="$(base_commit)"
  git update-ref "refs/heads/$branch" "$commit" "$old" 2>/dev/null || return 1
  return 0
}

slug() {
  printf '%s' "$1" |
    tr '[:upper:]' '[:lower:]' |
    sed 's/[^a-z0-9]\{1,\}/-/g; s/^-*//; s/-*$//' |
    cut -c1-40 |
    sed 's/-*$//'
}

require_id() { [ -n "${1:-}" ] || die "usage: queue.sh $2 <id>"; }

# One attempt to write a state change, retried while the branch moves under it.
# The first fetch is skipped under LEAN_QUEUE_NO_FETCH, which is how the tests
# stage a genuine lost race; a retry always fetches.
transition() {
  local id="$1" verb="$2" attempt content status holder new commit
  for attempt in 1 2 3; do
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
      release | done)
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
    commit="$(build_commit "$id" "$new" "queue: $verb $id ($owner)")" ||
      die "could not build the queue commit for $id"
    if publish "$commit"; then
      echo "$verb $id"
      return 0
    fi
  done
  die "could not $verb $id: the queue branch moved under every attempt" 3
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
    fetch_queue
    read_item "$2" || die "no such queue item: $2"
    ;;

  add)
    shift
    title="$*"
    [ -n "$title" ] || die "usage: queue.sh add <title>"
    fetch_queue
    base_id="$(slug "$title")"
    [ -n "$base_id" ] || die "cannot make an id from: $title"
    id="$base_id"
    n=1
    while read_item "$id" >/dev/null 2>&1; do
      n=$((n + 1))
      id="$base_id-$n"
    done
    item="$(printf '# %s\nstatus: open\nowner: -\nupdated: %s\n' "$title" "$(now)")"
    commit="$(build_commit "$id" "$item" "queue: add $id")" ||
      die "could not build the queue commit for $id"
    publish "$commit" || die "could not add $id: the queue branch moved; try again"
    echo "$id"
    ;;

  claim | release | "done")
    verb="$1"
    require_id "${2:-}" "$verb"
    transition "$2" "$verb"
    ;;

  *)
    echo "usage: queue.sh [list|show <id>|add <title>|claim <id>|release <id>|done <id>]" >&2
    exit 1
    ;;
esac
