#!/usr/bin/env bash
# Workflow mode: read, validate, and record the value in the mode block of
# .lean/PROJECT.md. What each mode adds: .lean/policy/MODES.md.
#
#   mode.sh get           print standard | tracker | full, or `unset`
#   mode.sh check         exit non-zero if the recorded value is not a mode
#   mode.sh set <mode>    record the choice
#
# The value lives in .lean/PROJECT.md because upgrades replace .lean/policy/ and
# never touch that file: the choice survives them, and editing the block by hand
# is the supported way to change it.

set -u

root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
project="$root/.lean/PROJECT.md"

usage() {
  echo "usage: mode.sh [get|check|set <standard|tracker|full>]" >&2
}

# The first line between the markers that is not a fence, a comment, or blank.
# Anything unreadable reads as `unset`, so a project without the block asks
# rather than silently running one mode's rules under another's name.
read_mode() {
  local value=""
  if [ -f "$project" ]; then
    value="$(awk '
      /<!-- mode:start -->/ { on = 1; next }
      /<!-- mode:end -->/   { on = 0 }
      on && !/^```/ && !/^[[:space:]]*(#|$)/ { print; exit }
    ' "$project" | tr -d '`' | tr -d '[:space:]')"
  fi
  [ -n "$value" ] || value="unset"
  printf '%s\n' "$value"
}

valid() {
  case "$1" in
    standard | tracker | full) return 0 ;;
    *) return 1 ;;
  esac
}

case "${1:-get}" in
  get)
    read_mode
    ;;

  check)
    mode="$(read_mode)"
    if [ "$mode" = "unset" ] || valid "$mode"; then
      exit 0
    fi
    echo "invalid workflow mode '$mode' in $project (expected standard, tracker, or full)" >&2
    exit 1
    ;;

  set)
    new="${2:-}"
    if ! valid "$new"; then
      usage
      exit 1
    fi
    [ -f "$project" ] || { echo "no $project" >&2; exit 1; }
    for marker in 'mode:start' 'mode:end'; do
      count="$(grep -c "<!-- $marker -->" "$project")"
      [ "$count" = "1" ] || {
        echo "expected one <!-- $marker --> marker in $project, found $count" >&2
        exit 1
      }
    done

    tmp="$(mktemp)" || exit 1
    if awk -v new="$new" '
      /<!-- mode:start -->/ { print; print new; on = 1; next }
      /<!-- mode:end -->/   { on = 0 }
      on { next }
      { print }
    ' "$project" > "$tmp"; then
      # Copied rather than moved, so PROJECT.md keeps its own permissions.
      cat "$tmp" > "$project"
      rm -f "$tmp"
      echo "workflow mode: $new"
    else
      rm -f "$tmp"
      echo "could not write $project" >&2
      exit 1
    fi
    ;;

  *)
    usage
    exit 1
    ;;
esac
