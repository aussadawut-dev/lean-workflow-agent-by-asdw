#!/usr/bin/env bash
# Structural checks for the workflow files: referenced paths exist,
# settings are valid, hooks are executable, skills and agents have
# frontmatter. Usage: .github/lean-workflow/check-structure.sh

set -u

cd "$(dirname "$0")/../.." || exit 1

fail=0
bad() { fail=$((fail + 1)); echo "FAIL $1"; }

docs="$(find . -path ./.git -prune -o -name '*.md' -type f -print | sort)"

# Repo-root references to workflow files, e.g. `.agent/policy/REVIEW.md`.
for ref in $(printf '%s\n' "$docs" | xargs grep -hoE '\.(agent|claude)/[A-Za-z0-9_./-]+\.(md|sh|json)' | sort -u); do
  [ -e "$ref" ] || bad "missing $ref"
done

# Router references relative to .agent/, e.g. `policy/REVIEW.md`.
for ref in $(grep -oE '`(policy/)?[A-Z]+\.md`' .agent/README.md | tr -d '`' | sort -u); do
  [ -e ".agent/$ref" ] || bad "missing .agent/$ref (from .agent/README.md)"
done

# Sibling references inside policy files, e.g. `CONTRACTS.md`.
for file in .agent/policy/*.md; do
  for ref in $(grep -oE '`[A-Z]+\.md`' "$file" | tr -d '`' | sort -u); do
    [ -e ".agent/policy/$ref" ] || bad "missing .agent/policy/$ref (from $file)"
  done
done

# CLAUDE.md imports.
for ref in $(grep -oE '^@[^ ]+' CLAUDE.md | cut -c2-); do
  [ -e "$ref" ] || bad "missing import $ref (from CLAUDE.md)"
done

# settings.json is valid and its hook scripts exist and are executable.
if python3 -c 'import json,sys; json.load(open(sys.argv[1]))' .claude/settings.json 2>/dev/null; then
  for script in $(grep -oE '\.claude/hooks/[A-Za-z0-9_.-]+' .claude/settings.json | sort -u); do
    [ -x "$script" ] || bad "hook not executable: $script"
  done
else
  bad "invalid JSON: .claude/settings.json"
fi

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

# Gate markers exist exactly once.
for marker in 'gate:start' 'gate:end'; do
  count="$(grep -c "<!-- $marker -->" .agent/PROJECT.md)"
  [ "$count" = "1" ] || bad "expected one $marker marker in .agent/PROJECT.md, found $count"
done

if [ "$fail" -eq 0 ]; then echo "structure ok"; fi
[ "$fail" -eq 0 ]
