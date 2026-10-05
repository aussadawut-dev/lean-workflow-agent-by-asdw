#!/usr/bin/env python3
"""Static imports, review routing and skill parity checks; no third-party dependencies."""
import re
import subprocess
import sys
from pathlib import Path

REQUIRED_SKILLS = ("lean-init", "lean-task", "lean-review", "lean-gate", "lean-scope",
                   "lean-research", "lean-grill", "lean-multi-agent")


def check(root):
    failures = []

    def bad(message):
        failures.append(message)

    listing = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                             cwd=root, capture_output=True)
    if listing.returncode:
        bad("cannot enumerate git-visible Markdown files; initialize Git after copying the template")
    else:
        for name in set(listing.stdout.decode().split("\0")):
            path = root / name
            if path.suffix != ".md" or not path.is_file():
                continue
            content = path.read_text()
            for reference in set(re.findall(r"\.(?:lean|claude|agents)/[A-Za-z0-9_./-]+\.(?:md|sh|py|json)", content)):
                # These paths are created by opting into full mode; examples are not items.
                if reference.startswith(".agents/queue/"):
                    continue
                if not (root / reference).exists():
                    bad(f"missing {reference} (from {name})")

    for entry in ("AGENTS.md", "CLAUDE.md"):
        path = root / entry
        if not path.is_file():
            bad(f"missing entrypoint: {entry}")
            continue
        for reference in re.findall(r"(?m)^@([^\n]+)$", path.read_text()):
            if not (root / reference.strip()).is_file():
                bad(f"missing import {reference.strip()} (from {entry})")

    router = root / ".lean/README.md"
    if router.is_file():
        for reference in re.findall(r"`((?:policy/)?[A-Z][A-Z_-]*\.md)`", router.read_text()):
            destination = root / reference if reference in ("AGENTS.md", "CLAUDE.md") else root / ".lean" / reference
            if not destination.is_file():
                bad(f"missing .lean/{reference} (from policy router)")
    for path in (root / ".lean/policy").glob("*.md"):
        for reference in re.findall(r"`([A-Z][A-Z_-]*\.md)`", path.read_text()):
            if not (path.parent / reference).is_file():
                bad(f"missing sibling policy {reference} (from {path.name})")

    # Support the legacy CLAUDE-first arrangement during migration, as well as AGENTS.
    agents = root / "AGENTS.md"
    canonical = "CLAUDE.md" if agents.is_file() and re.search(r"(?m)^@CLAUDE\.md$", agents.read_text()) else "AGENTS.md"
    for name in (canonical, ".claude/skills/lean-task/SKILL.md", ".claude/skills/lean-review/SKILL.md"):
        path = root / name
        if not path.is_file():
            bad(f"missing reviewer routing: {name}")
            continue
        content = path.read_text()
        paragraphs = re.split(r"\n\s*\n", content)
        routing = [paragraph for paragraph in paragraphs if "HIGH" in paragraph and "review" in paragraph.lower()]
        if not any("independent" in paragraph.lower() and "MODELS.md" in paragraph for paragraph in routing):
            bad(f"HIGH reviewer routing requires independent review and model/effort policy: {name}")

    for tree in (".claude/skills", ".agents/skills"):
        for name in REQUIRED_SKILLS:
            if not (root / tree / name / "SKILL.md").is_file():
                bad(f"missing {'adapter' if tree.startswith('.agents') else 'skill'}: {tree}/{name}/SKILL.md")
        for path in sorted((root / tree).glob("*/SKILL.md")):
            validate_frontmatter(path, path.parent.name, bad)
            if tree == ".agents/skills" and path.parent.name in REQUIRED_SKILLS:
                expected = (root / ".claude/skills" / path.parent.name / "SKILL.md").resolve()
                destinations = re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text())
                targets = [(path.parent / value.split("#", 1)[0]).resolve() for value in destinations
                           if "://" not in value]
                if expected not in targets or not expected.is_file():
                    bad(f"adapter must link its canonical procedure: {path.relative_to(root)}")
                for target in targets:
                    if not target.is_file():
                        bad(f"missing adapter target: {path.relative_to(root)} -> {target}")
    for path in sorted((root / ".claude/agents").glob("*.md")):
        validate_frontmatter(path, None, bad)
    for message in failures:
        print(f"FAIL {message}")
    return bool(failures)


def validate_frontmatter(path, expected_name, bad):
    content = path.read_text()
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", content, re.DOTALL)
    if not match:
        bad(f"no closed frontmatter: {path}")
        return
    fields = {}
    for name, value in re.findall(r"(?m)^([a-z-]+):[ \t]*(.*)$", match.group(1)):
        fields[name] = value.strip().strip("\"'")
    for name in ("name", "description"):
        if not fields.get(name):
            bad(f"empty or missing {name}: {path}")
    if expected_name and fields.get("name") != expected_name:
        bad(f"skill name does not match directory: {path}")


if __name__ == "__main__":
    sys.exit(check(Path(__file__).resolve().parents[2]))
