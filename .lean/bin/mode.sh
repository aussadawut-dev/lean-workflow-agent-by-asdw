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
#
# That hand edit is also why every read and write here is bounded by the marker
# line numbers and verified afterwards. The same file carries the Quality Gate
# commands the Stop hook runs, so a rewrite that misreads a malformed block would
# take the gate, the commands, and the rest of the project's own notes with it. A
# block this cannot make sense of reads as `unset`, which is a question, and
# refuses to be written to, which is a message -- never a guess.

set -u

root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
project="$root/.lean/PROJECT.md"

START='<!-- mode:start -->'
END='<!-- mode:end -->'

usage() {
  echo "usage: mode.sh [get|check|set <standard|tracker|full>]" >&2
}

die() { echo "$1" >&2; exit "${2:-1}"; }

# Prints "<start line> <end line>" when the block is well formed: exactly one of
# each marker, the start before the end. Non-zero otherwise.
block() {
  local file="$1" starts ends sn en
  [ -f "$file" ] || return 1
  starts="$(grep -o -F "$START" "$file" | grep -c .)"
  ends="$(grep -o -F "$END" "$file" | grep -c .)"
  [ "$starts" = "1" ] && [ "$ends" = "1" ] || return 1
  sn="$(grep -n -F "$START" "$file" | head -1 | cut -d: -f1)"
  en="$(grep -n -F "$END" "$file" | head -1 | cut -d: -f1)"
  if [ "$sn" -gt "$en" ]; then
    return 1
  elif [ "$sn" -eq "$en" ]; then
    # Both markers on one line: the value can only be between them.
    awk -v s="$START" -v e="$END" -v n="$sn" \
      'NR == n { exit (index($0, s) < index($0, e)) ? 0 : 1 }' "$file" || return 1
  fi
  printf '%s %s\n' "$sn" "$en"
}

# The first thing between the markers that is not a fence, a comment, or blank.
# Decoration around a hand-edited value is not part of it.
read_mode() {
  local file="$1" bounds value=""
  if bounds="$(block "$file")"; then
    value="$(awk -v s="$START" -v e="$END" -v from="${bounds% *}" -v to="${bounds#* }" '
      NR < from || NR > to { next }
      {
        line = $0
        if (NR == from) { i = index(line, s); line = substr(line, i + length(s)) }
        if (NR == to)   { j = index(line, e); if (j > 0) line = substr(line, 1, j - 1) }
        gsub(/`/, "", line)
        if (line ~ /^[[:space:]]*#/) next
        gsub(/[[:space:]]/, "", line)
        if (line != "") { print line; exit }
      }
    ' "$file")"
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
    read_mode "$project"
    ;;

  check)
    mode="$(read_mode "$project")"
    if [ "$mode" = "unset" ] || valid "$mode"; then
      exit 0
    fi
    die "invalid workflow mode '$mode' in $project (expected standard, tracker, or full)"
    ;;

  set)
    new="${2:-}"
    valid "$new" || { usage; exit 1; }
    [ -f "$project" ] || die "no $project"

    bounds="$(block "$project")" ||
      die "the mode block in $project is missing or malformed: expected one $START and one $END, the start first. Fix the block by hand; nothing was written."
    start="${bounds% *}"
    end="${bounds#* }"
    [ "$start" -lt "$end" ] ||
      die "the markers in $project share line $start. Put $START and $END on separate lines; nothing was written."

    # A value on a marker line survives the rewrite below and would be read
    # instead of the new one. The verification further down catches that, but it
    # can only say the result did not read back; this says what to fix.
    inline="$(awk -v s="$START" -v n="$start" \
      'NR == n { rest = substr($0, index($0, s) + length(s)); gsub(/[[:space:]]/, "", rest); print rest }' \
      "$project")"
    [ -z "$inline" ] ||
      die "line $start of $project holds '$inline' after $START. The value goes on its own line between the markers; nothing was written."
    inline="$(awk -v e="$END" -v n="$end" \
      'NR == n { rest = substr($0, 1, index($0, e) - 1); gsub(/[[:space:]]/, "", rest); print rest }' \
      "$project")"
    [ -z "$inline" ] ||
      die "line $end of $project holds '$inline' before $END. The value goes on its own line between the markers; nothing was written."

    total="$(grep -c '' "$project")"
    tmp="$(mktemp)" || exit 1
    trap 'rm -f "$tmp"' EXIT

    # Only the lines strictly between the markers are replaced, by line number.
    { head -n "$start" "$project" &&
      printf '%s\n' "$new" &&
      tail -n +"$end" "$project"; } > "$tmp" ||
      die "could not stage the change to $project; nothing was written."

    # Refuse to overwrite unless the result is the file it should be: the mode
    # reads back, the line count is the old one minus the block's contents, and
    # the Quality Gate markers are still there.
    [ "$(read_mode "$tmp")" = "$new" ] ||
      die "the rewritten $project does not read back as '$new'; nothing was written."
    want=$((start + 1 + total - end + 1))
    got="$(grep -c '' "$tmp")"
    [ "$got" = "$want" ] ||
      die "the rewritten $project has $got lines, expected $want; nothing was written."
    for marker in "$START" "$END" '<!-- gate:start -->' '<!-- gate:end -->'; do
      before="$(grep -c -F "$marker" "$project")"
      after="$(grep -c -F "$marker" "$tmp")"
      [ "$before" = "$after" ] ||
        die "the rewritten $project lost a '$marker' line; nothing was written."
    done

    # Copied rather than moved, so PROJECT.md keeps its own permissions.
    cat "$tmp" > "$project" || die "could not write $project"
    echo "workflow mode: $new"
    ;;

  *)
    usage
    exit 1
    ;;
esac
