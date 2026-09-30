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
# history and its migration steps. The pattern is spelled [.]agent/ so that this file
# does not match itself, which is the idiom that file's own verify step uses. Every
# text file is scanned: .gitignore is a workflow file here, and GitHub accepts both
# .yml and .yaml. Drop this check once 1.x is out of circulation.
scan_err="$(mktemp)"
hits="$(find . -path ./.git -prune -o ! -path ./.lean/CHANGELOG.md -type f \
  -exec grep -I -nE '[.]agent/|[.]github/lean-workflow/' /dev/null {} + 2>"$scan_err")"
# Fail closed: an unreadable file or a broken scan must not read as a clean one.
if [ -s "$scan_err" ]; then
  bad "retired-path scan could not complete: $(head -n 1 "$scan_err")"
fi
rm -f "$scan_err"
while IFS= read -r hit; do
  [ -n "$hit" ] && bad "retired path still referenced: $hit"
done <<EOF
$hits
EOF

# Gate markers exist exactly once.
for marker in 'gate:start' 'gate:end'; do
  count="$(grep -c "<!-- $marker -->" .lean/PROJECT.md)"
  [ "$count" = "1" ] || bad "expected one $marker marker in .lean/PROJECT.md, found $count"
done

if [ "$fail" -eq 0 ]; then echo "structure ok"; fi
[ "$fail" -eq 0 ]
