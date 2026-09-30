#!/usr/bin/env bash
# Structural checks for the workflow files: referenced paths exist,
# settings are valid, hooks are executable, skills and agents have
# frontmatter. Usage: .lean/scripts/check-structure.sh

set -u

cd "$(dirname "$0")/../.." || exit 1

fail=0
bad() { fail=$((fail + 1)); echo "FAIL $1"; }

docs="$(find . -path ./.git -prune -o -name '*.md' -type f -print | sort)"

# Repo-root references to workflow files, e.g. `.lean/policy/REVIEW.md`.
for ref in $(printf '%s\n' "$docs" | xargs grep -hoE '\.(lean|claude)/[A-Za-z0-9_./-]+\.(md|sh|json)' | sort -u); do
  [ -e "$ref" ] || bad "missing $ref"
done

# Router references relative to .lean/, e.g. `policy/REVIEW.md`.
# shellcheck disable=SC2016 # literal backticks in the pattern
while read -r ref; do
  [ -e ".lean/$ref" ] || bad "missing .lean/$ref (from .lean/README.md)"
done < <(grep -oE '`(policy/)?[A-Z]+\.md`' .lean/README.md | tr -d '`' | sort -u)

# Sibling references inside policy files, e.g. `CONTRACTS.md`.
for file in .lean/policy/*.md; do
  # shellcheck disable=SC2016 # literal backticks in the pattern
  while read -r ref; do
    [ -e ".lean/policy/$ref" ] || bad "missing .lean/policy/$ref (from $file)"
  done < <(grep -oE '`[A-Z]+\.md`' "$file" | tr -d '`' | sort -u)
done

# CLAUDE.md imports.
while read -r ref; do
  [ -e "$ref" ] || bad "missing import $ref (from CLAUDE.md)"
done < <(grep -oE '^@[^ ]+' CLAUDE.md | cut -c2-)

# settings.json is valid and its hook scripts exist and are executable.
if python3 -c 'import json,sys; json.load(open(sys.argv[1]))' .claude/settings.json 2>/dev/null; then
  while read -r script; do
    [ -x "$script" ] || bad "hook not executable: $script"
  done < <(grep -oE '\.claude/hooks/[A-Za-z0-9_.-]+' .claude/settings.json | sort -u)
else
  bad "invalid JSON: .claude/settings.json"
fi

# Workflow scripts are executable, so CI and the docs can run them by path.
for script in .lean/scripts/*.sh .lean/tests/*.sh; do
  [ -f "$script" ] || continue
  [ -x "$script" ] || bad "not executable: $script"
done

# Skills and agents need name and description frontmatter.
for file in .claude/skills/*/SKILL.md .claude/agents/*.md; do
  [ -f "$file" ] || continue
  head -1 "$file" | grep -q '^---$' || { bad "no frontmatter: $file"; continue; }
  front="$(awk 'NR > 1 && /^---$/ { exit } NR > 1 { print }' "$file")"
  printf '%s\n' "$front" | grep -q '^name: ' || bad "no name: $file"
  printf '%s\n' "$front" | grep -q '^description: ' || bad "no description: $file"
done

# Skill name matches its directory.
for file in .claude/skills/*/SKILL.md; do
  [ -f "$file" ] || continue
  dir="$(basename "$(dirname "$file")")"
  grep -q "^name: $dir\$" "$file" || bad "skill name does not match directory: $file"
done

# The HIGH-review path must name the model rule. `.lean/policy/MODELS.md` puts the
# strongest model on HIGH-risk review, but `.claude/agents/reviewer.md` ships
# `model: inherit` -- deliberately, since pinned frontmatter breaks an install whose
# plan lacks that model -- so the model is chosen only where the reviewer is spawned.
# Through 2.2.0 no spawn site said so and the rule was a silent no-op. Guarded on the
# code-span form of the subagent name, never the bare word, so a project that drops
# the subagent is not blocked on every turn by a rule it deliberately dropped. The
# phrase may sit anywhere in the file: in /lean-review the two are on different lines.
for file in CLAUDE.md .claude/skills/lean-task/SKILL.md .claude/skills/lean-review/SKILL.md; do
  [ -f "$file" ] || continue
  # shellcheck disable=SC2016 # literal backtick in the pattern
  grep -q 'reviewer` subagent' "$file" || continue
  grep -qi 'strongest model available' "$file" ||
    bad "spawns the reviewer without the strongest-model rule from .lean/policy/MODELS.md: $file"
done

# The workflow version, in the two workflow-owned files that carry it. Both must be
# present and agree. .lean/PROJECT.md is project-owned and free-form -- a project's own
# "Current version" line is none of this check's business -- so it is not read here.
found="$( {
  grep -oE 'Baseline [0-9]+\.[0-9]+\.[0-9]+' .lean/README.md
  grep -m1 -oE '^## [0-9]+\.[0-9]+\.[0-9]+' .lean/CHANGELOG.md
} | grep -oE '[0-9]+\.[0-9]+\.[0-9]+$' )"
n="$(printf '%s\n' "$found" | grep -c .)"
if [ "$n" != "2" ]; then
  bad "workflow version: expected exactly one in each of .lean/README.md and .lean/CHANGELOG.md, found $n"
elif [ "$(printf '%s\n' "$found" | sort -u | grep -c .)" != "1" ]; then
  bad "workflow version differs between .lean/README.md and .lean/CHANGELOG.md: $(printf '%s' "$found" | tr '\n' ' ')"
fi

# Paths the 2.0.0 move retired. Only .lean/CHANGELOG.md may still name them, in its
# history and its migration steps; the pattern below spells the dot as a class so
# this file does not match itself. The match is textual, not by reference, so a
# project owning a directory by either name should drop this check -- as should
# everyone, once 1.x is out of circulation. This scan and the .gitignore assertions
# below both need git, and the README's `npx degit` route leaves none, so say that
# once instead of failing three times, each naming the wrong cause.
retired='[.]agent/|[.]github/lean-workflow/'
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  bad "no git work tree: cannot check retired paths or .gitignore entries"
else
  if ! scan_err="$(mktemp)" || [ -z "$scan_err" ]; then
    bad "retired-path scan could not start: mktemp failed"
  else
    # git grep, not the filesystem: a vendored or ignored file that happens to
    # name a retired path is not this repository's content, and a false hit in a
    # downstream install would block every turn. --untracked still covers a new
    # file a contributor has not staged yet, which is content, and git chunks its
    # own argument list, so there is no argv ceiling. `-a` rather than `-I`, so a
    # .gitattributes binary marking cannot hide a real hit. A scan that cannot run
    # is read as a failure below, never a pass.
    hits="$(git grep --no-color -a -nE --untracked "$retired" \
      -- ':(exclude).lean/CHANGELOG.md' 2>>"$scan_err")"
    status=$?
    [ "$status" -gt 1 ] && bad "retired-path scan could not complete (git grep exit $status)"
    [ -s "$scan_err" ] && bad "retired-path scan reported: $(head -n 1 "$scan_err")"
    rm -f "$scan_err"

    while IFS= read -r hit; do
      [ -n "$hit" ] && bad "retired path still referenced: $hit"
    done <<EOF
$hits
EOF
  fi

  # The gate's own state files must stay untracked, or each run's state includes
  # the file the previous run wrote and the gate never settles. Asked by effect,
  # so any equivalent .gitignore pattern passes.
  for ignored in '.claude/.gate-cache' '.claude/.gate-failed'; do
    git check-ignore -q "$ignored" || bad "not ignored by git: $ignored"
  done
fi

# --seed records state and runs nothing, so wiring it to Stop disables the gate
# in silence. It belongs in session-start.sh, never in a settings file --
# including the gitignored local one, which is where someone would experiment.
for settings in .claude/settings.json .claude/settings.local.json; do
  [ -f "$settings" ] || continue
  if grep -q -- '--seed' "$settings"; then
    bad "--seed must not appear in $settings (it would disable the gate)"
  fi
done

# Gate markers exist exactly once.
for marker in 'gate:start' 'gate:end'; do
  count="$(grep -c "<!-- $marker -->" .lean/PROJECT.md)"
  [ "$count" = "1" ] || bad "expected one $marker marker in .lean/PROJECT.md, found $count"
done

# Model registry. `.lean/policy/MODELS.md` names tiers; the registry in .lean/PROJECT.md
# names the model each tier resolves to, per runtime -- an agent reaching this repository
# through AGENTS.md spawns models this one cannot, so a single column of names would be
# wrong for everyone but its author. The names cannot be checked from here, since no list
# of current models is in this repository. What can be: that each runtime named covers
# every tier, and that the dates are current. Model generations turn over faster than the
# file gets reread, and a stale or half-filled registry is worse than none, because the
# agent trusts it instead of falling back. Each row carries its own date, so one runtime's
# update does not vouch for another's; the oldest decides. A project carrying no registry
# is not failed: MODELS.md's fallback covers it. Half a registry is, since a lost marker
# would otherwise read as no registry and skip the check in silence.
models_start="$(grep -c -- '<!-- models:start -->' .lean/PROJECT.md)"
models_end="$(grep -c -- '<!-- models:end -->' .lean/PROJECT.md)"
if [ "$models_start$models_end" != "00" ]; then
  if [ "$models_start" != "1" ] || [ "$models_end" != "1" ]; then
    bad "expected one models:start and one models:end marker in .lean/PROJECT.md, found $models_start and $models_end"
  else
    tab="$(printf '\t')"
    # Cells of each table row, never a bare date scan over the block: a pinned version id
    # may carry a date of its own, and reading that as the row's date would date the
    # registry by the very model it is meant to be checking. No `next` on the start rule,
    # so both markers on one line still close the block. A row is read only between its
    # outer pipes, which is also what makes a CRLF checkout pass: the \r lands in the
    # field after the last one, and nothing reads it.
    rows="$(awk -F '|' '
      /<!-- models:start -->/ { inside = 1 }
      /<!-- models:end -->/   { inside = 0 }
      inside && /^[ \t]*\|/ {
        out = ""
        for (i = 2; i < NF; i++) {
          cell = $i
          gsub(/^[ \t]+|[ \t]+$/, "", cell)
          out = (i == 2) ? cell : out "\t" cell
        }
        print out
      }' .lean/PROJECT.md | grep -vE "^(runtime$tab|-+$tab)")"

    if [ -z "$rows" ]; then
      bad "model registry in .lean/PROJECT.md has no rows: a registry naming no model verifies nothing"
    else
      malformed="$(printf '%s\n' "$rows" |
        grep -cvE "^[^${tab}]+${tab}[^${tab}]+${tab}[^${tab}]+${tab}[0-9]{4}-[0-9]{2}-[0-9]{2}$")"
      if [ "$malformed" != "0" ]; then
        bad "model registry in .lean/PROJECT.md has $malformed row(s) that are not | runtime | tier | model | YYYY-MM-DD |"
      else
        # A runtime listed for some tiers only is dated and trusted for the tier it does
        # not name. The tier names are MODELS.md's; both files are workflow-owned and
        # move together.
        while IFS= read -r runtime; do
          [ -n "$runtime" ] || continue
          missing=""
          for tier in fast default strongest; do
            printf '%s\n' "$rows" | cut -f1,2 | grep -qxF "$runtime$tab$tier" ||
              missing="$missing $tier"
          done
          [ -n "$missing" ] &&
            bad "model registry in .lean/PROJECT.md: runtime $runtime has no row for:$missing"
        done <<EOF
$(printf '%s\n' "$rows" | cut -f1 | sort -u)
EOF

        # python3 is already required above, for settings.json. Date arithmetic in shell is
        # not portable between the GNU and BSD `date` this template runs on; this is.
        ages="$(printf '%s\n' "$rows" | cut -f4 | python3 -c '
import datetime, sys
today = datetime.date.today()
ages = sorted((today - datetime.date.fromisoformat(d)).days for d in sys.stdin.read().split())
print(ages[0], ages[-1])' 2>/dev/null)"
        if [ -z "$ages" ]; then
          bad "model registry in .lean/PROJECT.md: could not evaluate its verified dates -- either python3 is missing here, or a date is one the calendar does not have"
        elif [ "${ages% *}" -lt 0 ]; then
          bad "model registry in .lean/PROJECT.md has a row dated in the future: a date not yet reached verifies nothing"
        elif [ "${ages#* }" -gt 90 ]; then
          bad "model registry in .lean/PROJECT.md has a row verified ${ages#* } days ago (limit 90): check that runtime's tiers against the models it offers now, then move that row's date forward"
        fi
      fi
    fi
  fi
fi

if [ "$fail" -eq 0 ]; then echo "structure ok"; fi
[ "$fail" -eq 0 ]
