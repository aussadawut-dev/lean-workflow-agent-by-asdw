#!/usr/bin/env bash
# Project checks; --claude-hook adds transcript checks and local state.
# Cache is opt-in (--cache-tree) for checks depending only on Git-visible files.
# Refusals never become passes. Local receipts catch drift, not hostile writers.

set -u

hook=0
seed=0
cache_tree=0
require_review=0
contract=""
helper="$(cd "$(dirname "$0")" && pwd)/gate_evidence.py"
root="$(pwd)"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --claude-hook) hook=1; shift ;;
    --seed) seed=1; shift ;;
    --cache-tree) cache_tree=1; shift ;;
    --require-review) require_review=1; shift ;;
    --contract)
      [ "$#" -ge 2 ] || { echo "--contract requires a line" >&2; exit 2; }
      contract="$2"; shift 2 ;;
    --root)
      [ "$#" -ge 2 ] || { echo "--root requires a path" >&2; exit 2; }
      root="$2"; shift 2 ;;
    *) echo "Unknown gate option: $1" >&2; exit 2 ;;
  esac
done
[ "$seed" -eq 0 ] || [ "$hook" -eq 1 ] || { echo "--seed requires --claude-hook" >&2; exit 2; }
root="$(cd "$root" && pwd)" || exit 2
project="$root/.lean/PROJECT.md"
cache="$root/.claude/.gate-cache"
failed="$root/.claude/.gate-failed"
baseline="$root/.agent-runtime/gate-baseline"
[ "$hook" -eq 0 ] || mkdir -p "$root/.claude" || exit 2

active=0
transcript=""
if [ "$hook" -eq 1 ] && [ "$seed" -eq 0 ]; then
  input="$(cat)"

  active="$(printf '%s' "$input" | python3 "$helper" --root "$root" hook-field --field stop_hook_active)" || exit 2
  transcript="$(printf '%s' "$input" | python3 "$helper" --root "$root" hook-field --field transcript_path)" || exit 2
fi

# Record a refusal; $1 is "c" for a contract refusal, empty for a gate failure.
# A continuation adds to the count; a fresh Stop starts it at 1. A contract
# refusal says nothing about the code, so it keeps the passing-state cache and a
# later session's seed clears it instead of declining.
# After max_refusals continued refusals the Stop is released so the agent can
# report BLOCKED instead of looping; the release tells the user the work is
# unverified, keeps the refusal marker and never writes a cache or receipt.
max_refusals=3
refuse() {
  [ "$hook" -eq 1 ] && [ "$seed" -eq 0 ] || return 0
  local n=0
  if [ "$active" -eq 1 ]; then
    n="$(cat "$failed" 2>/dev/null)"
    n="${n#c}"
    case "$n" in ''|*[!0-9]*) n=0 ;; esac
  fi
  [ "${1:-}" = "c" ] || rm -f "$cache"
  n=$((n + 1))
  printf '%s' "${1:-}$n" > "$failed"
  if [ "$n" -gt "$max_refusals" ]; then
    printf '{"systemMessage":"Lean Quality Gate still refused after %s attempts; Stop released UNVERIFIED. The work is not DONE; see the last gate refusal."}\n' "$max_refusals"
    exit 0
  fi
}

# A gate refusal is outstanding: the marker exists and is not a contract one.
gate_refused() {
  [ -f "$failed" ] && case "$(cat "$failed" 2>/dev/null)" in c*) return 1 ;; *) return 0 ;; esac
}

# Application checks must run before the Lean cache can skip its own checks.
# Target state (including untracked files) is separate from the superproject.
if [ "$seed" -eq 0 ] && { [ -e "$root/.agent-runtime/active-target.json" ] || [ -L "$root/.agent-runtime/active-target.json" ]; }; then
  python3 "$root/.lean/scripts/submodule.py" --root "$root" gate --optional || { refuse; exit 2; }
fi

python3 "$helper" --root "$root" guard-controls || { refuse; exit 2; }
[ -f "$project" ] || { echo "Quality Gate undefined: missing .lean/PROJECT.md; run /lean-init." >&2; refuse; exit 2; }

commands="$(awk '
  /<!-- gate:start -->/ { starts++; on = 1; next }
  /<!-- gate:end -->/   { ends++; if (!on) invalid=1; on = 0 }
  on && !/^```/ && !/^[[:space:]]*(#|$)/ { print }
  END { if (starts != 1 || ends != 1 || invalid) exit 2 }
' "$project")" || { echo "Quality Gate undefined: malformed gate markers." >&2; refuse; exit 2; }

[ -n "$commands" ] || { echo "Quality Gate undefined: configure checks in .lean/PROJECT.md; no validation passed." >&2; refuse; exit 2; }

cd "$root" || { refuse; exit 2; }

# State receipts cover Git-visible files, modes, index and submodule work.
state=""
if [ "$hook" -eq 1 ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  state="$(python3 "$helper" --root "$root" state)" || { refuse; exit 2; }
fi

# SessionStart records a change baseline, never a passing cache.
if [ "$seed" -eq 1 ]; then
  gate_refused && exit 0
  rm -f "$failed"
  if [ -n "$state" ]; then
    printf '%s' "$state" > "$baseline"
    git rev-parse -q --verify HEAD > "$baseline-head" 2>/dev/null || rm -f "$baseline-head"
  fi
  exit 0
fi

# A baseline can identify chat-only turns; it is never proof of validation.
changed=1
for prior in "$baseline" "$cache"; do
  if [ -n "$state" ] && [ -f "$prior" ] && [ "$(cat "$prior")" = "$state" ]; then changed=0; fi
done
if [ "$hook" -eq 1 ] && [ -n "$transcript" ]; then
  if [ ! -r "$transcript" ]; then
    echo "Contract transcript unreadable: $transcript" >&2
    refuse c; exit 2
  fi
  if found="$(python3 "$helper" --root "$root" contract --transcript "$transcript")"; then
    contract="$found"
  elif [ "$changed" -eq 1 ]; then
    refuse c; exit 2
  fi
fi
case "$contract" in
  "Contract: risk=HIGH quality="*|"Contract: risk=LOW quality=VERY_HIGH acceptance="*|"Contract: risk=MEDIUM quality=VERY_HIGH acceptance="*) require_review=1 ;;
esac

# PROJECT.md High-risk areas set a review floor that a self-declared risk cannot lower.
# An unchanged state matches the session baseline or a pass that already applied it.
risky=""
if [ "$changed" -eq 1 ]; then
  risky="$(python3 "$helper" --root "$root" high-risk)" || { refuse; exit 2; }
fi
[ -z "$risky" ] || require_review=1

# Explain a refused review receipt, naming any High-risk areas that required it.
review_refused() {
  [ -z "$risky" ] || { echo "High-risk areas changed; HIGH independent review is required:"; printf '%s\n' "$risky"; } >&2
  refuse
  exit 2
}

# Only a real passing run can be cached; contracts and HIGH review are checked first.
if [ "$cache_tree" -eq 1 ] && [ "$hook" -eq 1 ] && [ -n "$state" ] && [ ! -f "$failed" ] &&
   [ -f "$cache" ] && [ "$(cat "$cache")" = "$state" ]; then
  if [ "$require_review" -eq 1 ]; then
    python3 "$helper" --root "$root" check-review --contract "$contract" || review_refused
  fi
  exit 0
fi

while IFS= read -r cmd; do
  output="$(bash -c "$cmd" 2>&1)" && continue
  status=$?

  # 127 identifies a missing tool only when its plain command name cannot
  # resolve. Wrappers, paths and shell fragments retain the failure verdict.
  # Skip leading simple VAR=VALUE words before looking up the command.
  lookup="$cmd"
  while [[ "$lookup" =~ ^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+(.*)$ ]]; do
    lookup="${BASH_REMATCH[1]}"
  done
  read -r first _ <<< "$lookup"

  missing=0
  if [ "$status" -eq 127 ] &&
     [[ "$first" =~ ^[A-Za-z0-9_][A-Za-z0-9_.+:@-]*$ ]] &&
     ! command -v -- "$first" >/dev/null 2>&1; then
    missing=1
  fi

  {
    if [ "$missing" -eq 1 ]; then
      echo "Quality Gate could not run: $cmd"
      printf '%s\n' "$output" | tail -n 40
      echo "'$first' is not available in this environment, so this check never ran. That is a missing tool, not a failure your change caused. Do not edit code, the gate, or the tests to get past it: report BLOCKED, name the gate command that could not run and the tool it needs, say the change is unverified by that command, and do not declare DONE."
    else
      echo "Quality Gate failed: $cmd"
      printf '%s\n' "$output" | tail -n 40
      echo "If your change caused this, fix it. If it was already failing or is outside the task, do not touch it: report BLOCKED and ask. Do not declare DONE."
    fi
  } >&2
  refuse
  exit 2
done <<< "$commands"

if [ "$require_review" -eq 1 ]; then
  python3 "$helper" --root "$root" check-review --contract "$contract" || review_refused
fi
[ "$hook" -eq 0 ] || rm -f "$failed"
[ -n "$state" ] && printf '%s' "$state" > "$cache"
exit 0
