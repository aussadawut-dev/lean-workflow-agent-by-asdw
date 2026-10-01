#!/usr/bin/env bash
# Tracking records for the `tracker` and `full` workflow modes: one record per
# Task Contract under .lean/tracker/, committed with the change it describes.
# What belongs in one: .lean/policy/MODES.md.
#
#   tracker.sh new <title> [--contract <line>] [--queue <id>]   prints the path
#   tracker.sh state <record> <IN_PROGRESS|DONE|BLOCKED|FAILED>
#   tracker.sh set <record> <contract|queue> <value>
#   tracker.sh current                        the newest record still IN_PROGRESS
#   tracker.sh list
#   tracker.sh show <record>
#
# <record> is a path inside the records directory, a file name, or the slug part
# of one. When a slug matches several records, the open one wins and anything
# still ambiguous is refused with the matches listed -- closing the wrong record
# is the mistake this tool exists to prevent. This tool owns the header only:
# the sections under it are the Result Contract, written by whoever did the work.
#
# Exit codes: 0 done, 1 usage or a bad argument, 2 nothing matched (no record,
# or no open record for `current`).

set -u

root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
dir="$root/.lean/tracker"

STATES="IN_PROGRESS DONE BLOCKED FAILED"

die() { echo "$1" >&2; exit "${2:-1}"; }

usage() {
  echo "usage: tracker.sh [new <title> [--contract <line>] [--queue <id>]|state <record> <state>|set <record> <contract|queue> <value>|current|list|show <record>]" >&2
}

today() { date -u '+%Y-%m-%d'; }

slug() {
  printf '%s' "$1" |
    tr '\n\t' '  ' |
    tr '[:upper:]' '[:lower:]' |
    sed 's/[^a-z0-9]\{1,\}/-/g; s/^-*//; s/-*$//' |
    cut -c1-40 |
    sed 's/-*$//'
}

valid_state() {
  local state
  for state in $STATES; do
    [ "$1" = "$state" ] && return 0
  done
  return 1
}

# Header values reach awk through the environment, never as -v and never as a sed
# replacement: a contract line holds `=`, `|`, `&` and `/` as a matter of course.
field() {
  local file="$1"
  TK="$2" awk '
    BEGIN { key = ENVIRON["TK"] }
    NF == 0 { exit }
    index($0, key ": ") == 1 { print substr($0, length(key) + 3); exit }
  ' "$file"
}

set_field() {
  local file="$1" tmp
  tmp="$(mktemp)" || return 1
  if TK="$2" TV="$3" awk '
      BEGIN { key = ENVIRON["TK"]; value = ENVIRON["TV"] }
      !body && NF == 0 { body = 1 }
      !body && index($0, key ": ") == 1 { print key ": " value; found = 1; next }
      { print }
      END { exit found ? 0 : 1 }
    ' "$file" > "$tmp"; then
    # Copied, not moved, so the record keeps its permissions.
    cat "$tmp" > "$file" || { rm -f "$tmp"; return 1; }
    rm -f "$tmp"
    return 0
  fi
  rm -f "$tmp"
  return 1
}

records() { find "$dir" -maxdepth 1 -name '*.md' 2>/dev/null | sort; }

# Every path this tool writes to or reads out must be a record: the records
# directory is the whole of its business, and a mistyped or generated path would
# otherwise rewrite the `state:` line of any file whose first paragraph has one.
inside_records() {
  local real records_real
  real="$(cd "$(dirname "$1")" 2>/dev/null && pwd -P)" || return 1
  records_real="$(cd "$dir" 2>/dev/null && pwd -P)" || return 1
  [ "$real" = "$records_real" ]
}

# Resolution sets $record. A record is named by date and slug, and is found by
# path, file name, or slug, so a session that only knows what it called the task
# can close what an earlier one opened. Several matches are not a guess: the open
# record wins, and anything still ambiguous is refused with the matches named.
resolve() {
  local want="$1" candidate matches open count
  record=""
  [ -n "$want" ] || die "which record? give a path, a file name, or a slug" 1
  case "$want" in
    *[*?\[\]]*) die "not a record name: '$want' (a glob would match a record nobody meant)" 1 ;;
  esac

  if [ -f "$want" ]; then
    inside_records "$want" ||
      die "not a tracking record: '$want' is outside $dir" 2
    record="$want"
    return 0
  fi
  for candidate in "$dir/$want" "$dir/$want.md"; do
    if [ -f "$candidate" ]; then
      record="$candidate"
      return 0
    fi
  done

  matches="$(records | grep -F -- "$want" || true)"
  count="$(printf '%s\n' "$matches" | grep -c . || true)"
  [ "$count" -gt 0 ] || die "no tracking record matches: $want" 2
  if [ "$count" = "1" ]; then
    record="$(printf '%s\n' "$matches" | grep .)"
    return 0
  fi

  # Several: the one still open is the one a session means.
  open=""
  while read -r candidate; do
    [ -n "$candidate" ] || continue
    [ "$(field "$candidate" state)" = "IN_PROGRESS" ] && open="$open$candidate
"
  done <<< "$matches"
  count="$(printf '%s' "$open" | grep -c . || true)"
  if [ "$count" = "1" ]; then
    record="$(printf '%s' "$open" | grep .)"
    return 0
  fi
  die "several records match '$want'; name one of them:
$(printf '%s\n' "$matches" | grep . | sed 's|^|  |')" 1
}

# A header line that exists with an empty value is settable; one that is missing
# is not, and the two need different messages.
has_field() {
  # `exit` in a rule still runs END, whose own exit decides the status, so the
  # answer travels in a flag rather than in the early exit.
  TK="$2" awk '
    BEGIN { key = ENVIRON["TK"] }
    NF == 0 { exit found ? 0 : 1 }
    index($0, key ": ") == 1 || $0 == key ":" { found = 1; exit 0 }
    END { exit found ? 0 : 1 }
  ' "$1"
}

case "${1:-list}" in
  new)
    shift
    title="${1:-}"
    [ -n "$title" ] || { usage; exit 1; }
    shift || true
    contract="-"
    queue="-"
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --contract) [ "$#" -ge 2 ] || die "--contract needs a value"; contract="$2"; shift 2 ;;
        --queue) [ "$#" -ge 2 ] || die "--queue needs a value"; queue="$2"; shift 2 ;;
        *) die "unknown option: $1" ;;
      esac
    done
    # One header line per field: a value spanning lines would move the fields
    # below it into the body, where nothing reads them.
    for value in "$contract" "$queue"; do
      case "$value" in
        *[[:cntrl:]]*) die "a header value may not contain control characters or newlines: $value" ;;
      esac
    done

    # A title comes from a task description, which is routinely several lines. On
    # one line it is a heading; spanning lines its second line would be read as a
    # header field, and `# Fix it\nstate: DONE` would open a record already
    # claiming DONE -- with no evidence, which is the one thing this workflow
    # exists to prevent.
    title_line="$(printf '%s' "$title" | tr '\n\t' '  ' | tr -d '[:cntrl:]')"
    base="$(slug "$title")"
    [ -n "$base" ] || die "cannot make a record name from: $title"
    mkdir -p "$dir" || die "could not create $dir"
    # Created with noclobber, so two sessions starting at once take different
    # names rather than one overwriting the other's record.
    stem="$(today)-$base"
    file="$dir/$stem.md"
    n=1
    until (set -C; : > "$file") 2>/dev/null; do
      [ "$n" -lt 50 ] || die "too many records named $stem"
      n=$((n + 1))
      file="$dir/$stem-$n.md"
    done

    {
      printf '# %s\n' "$title_line"
      printf 'state: IN_PROGRESS\n'
      printf 'contract: %s\n' "$contract"
      printf 'started: %s\n' "$(today)"
      printf 'queue: %s\n' "$queue"
      printf '\n## Changes\n\n## Evidence\n\n## Not verified\n\n## Follow-ups\n'
    } > "$file" || die "could not write $file"

    # The header the gate and a later session read has to be there.
    for key in state contract started queue; do
      [ -n "$(field "$file" "$key")" ] || die "wrote $file without a '$key' field"
    done
    printf '%s\n' "$file"
    ;;

  state)
    want="${2:-}"
    new_state="${3:-}"
    if [ -z "$want" ] || [ -z "$new_state" ]; then
      usage
      exit 1
    fi
    valid_state "$new_state" || die "not a record state: '$new_state' (expected one of: $STATES)"
    resolve "$want"
    file="$record"
    has_field "$file" state || die "$file has no 'state' line to set"
    set_field "$file" state "$new_state" || die "could not set the state in $file"
    printf '%s %s\n' "$new_state" "$file"
    ;;

  set)
    want="${2:-}"
    key="${3:-}"
    value="${4:-}"
    if [ -z "$want" ] || [ -z "$key" ] || [ "$#" -lt 4 ]; then
      usage
      exit 1
    fi
    # The state has its own command so that it stays one of the four; the title
    # is the record's name. That leaves the two fields a task learns as it goes.
    case "$key" in
      contract | queue) ;;
      *) die "not a field this sets: '$key' (contract or queue; use 'state' for the state)" ;;
    esac
    case "$value" in
      *[[:cntrl:]]*) die "a header value may not contain control characters or newlines: $value" ;;
    esac
    resolve "$want"
    file="$record"
    has_field "$file" "$key" || die "$file has no '$key' line to set"
    set_field "$file" "$key" "$value" || die "could not set '$key' in $file"
    printf '%s\n' "$file"
    ;;

  current)
    found=""
    while read -r file; do
      [ -n "$file" ] || continue
      [ "$(field "$file" state)" = "IN_PROGRESS" ] && found="$found$file
"
    done <<< "$(records)"
    count="$(printf '%s' "$found" | grep -c . || true)"
    case "$count" in
      0) die "no tracking record is IN_PROGRESS" 2 ;;
      1) printf '%s\n' "$(printf '%s' "$found" | grep .)" ;;
      *) die "$count records are IN_PROGRESS; name the one you mean:
$(printf '%s' "$found" | grep . | sed 's|^|  |')" 1 ;;
    esac
    ;;

  list)
    printf '%-12s %-12s %s\n' "STATE" "QUEUE" "RECORD"
    while read -r file; do
      [ -n "$file" ] || continue
      state="$(field "$file" state)"
      printf '%-12s %-12s %s\n' \
        "${state:-MALFORMED}" "$(field "$file" queue)" "$(basename "$file")"
    done <<< "$(records)"
    ;;

  show)
    want="${2:-}"
    [ -n "$want" ] || { usage; exit 1; }
    resolve "$want"
    cat "$record"
    ;;

  *)
    usage
    exit 1
    ;;
esac
