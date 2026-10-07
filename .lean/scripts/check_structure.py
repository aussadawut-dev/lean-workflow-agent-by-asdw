#!/usr/bin/env python3
"""Static imports, review routing and skill parity checks; no third-party dependencies."""
import re
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True
from shared_assets import REQUIRED_SKILLS, EXTRA_SKILLS, USER_COMMANDS, declared_links, verify_link


def check(root):
    failures = []

    def bad(message):
        failures.append(message)

    try:
        registry = json.loads((root / ".lean/assets.json").read_text())
        assets = registry["files"]
        if (registry.get("schema") not in (1, 2) or not isinstance(assets, list) or not assets
                or not all(isinstance(name, str) for name in assets) or len(assets) != len(set(assets))
                or ".lean/assets.json" not in assets):
            raise ValueError("invalid portable registry")
        for name in assets:
            path = Path(name)
            location = root / path
            symbolic = any(parent.is_symlink() for parent in (location, *location.parents) if parent != root and root in parent.parents)
            if path.is_absolute() or ".." in path.parts or symbolic or not location.is_file():
                bad(f"invalid/missing portable asset: {name}")
        links = declared_links(registry)
        for name in REQUIRED_SKILLS:
            if f".lean/skills/{name}/SKILL.md" not in assets:
                bad(f"portable registry missing canonical skill: {name}")
        for name in links:
            try:
                verify_link(root, name)
            except ValueError as error:
                bad(str(error))
        # Extra discovery is optional, but an enabled slot must use the canonical source.
        for tree in (".agents/skills", ".claude/skills"):
            for name in EXTRA_SKILLS:
                relative = f"{tree}/{name}"
                path = root / relative
                if relative not in links and (path.exists() or path.is_symlink()):
                    try:
                        verify_link(root, relative)
                    except ValueError as error:
                        bad(str(error))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        bad("invalid or missing portable asset registry")

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
                if reference.startswith((".agents/queue/", ".lean/targets/")) or reference in {".lean/model-catalog.json", ".lean/upstream.json"}:
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
    for name in (canonical, ".lean/skills/lean-task/SKILL.md", ".lean/skills/lean-review/SKILL.md"):
        path = root / name
        if not path.is_file():
            bad(f"missing reviewer routing: {name}")
            continue
        content = path.read_text()
        paragraphs = re.split(r"\n\s*\n", content)
        routing = [paragraph for paragraph in paragraphs if "HIGH" in paragraph and "review" in paragraph.lower()]
        if not any("independent" in paragraph.lower() and "MODELS.md" in paragraph for paragraph in routing):
            bad(f"HIGH reviewer routing requires independent review and model/effort policy: {name}")

    for name in REQUIRED_SKILLS:
        path = root / ".lean/skills" / name / "SKILL.md"
        if not path.is_file():
            bad(f"missing canonical skill: {name}")
            continue
        fields = validate_frontmatter(path, name, bad)
        expected_visibility = "true" if name in USER_COMMANDS else "false"
        if fields.get("user-invocable") != expected_visibility:
            bad(f"incorrect command visibility: {path.relative_to(root)}")
        if name in USER_COMMANDS and not fields.get("argument-hint"):
            bad(f"missing command argument hint: {path.relative_to(root)}")
        if fields.get("disable-model-invocation") == "true":
            bad(f"workflow skill must remain available to the agent: {path.relative_to(root)}")
    # Local extensions may remain ordinary provider-specific skills.
    for tree in (".claude/skills", ".agents/skills"):
        for path in sorted((root / tree).glob("*/SKILL.md")):
            if path.parent.name not in REQUIRED_SKILLS:
                validate_frontmatter(path, path.parent.name, bad)
    reviewer = root / ".claude/agents/reviewer.md"
    if reviewer.is_file() and "../../.lean/roles/reviewer.md" not in reviewer.read_text():
        bad("reviewer must route to the shared role")
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
        return {}
    fields = {}
    for name, value in re.findall(r"(?m)^([a-z-]+):[ \t]*(.*)$", match.group(1)):
        fields[name] = value.strip().strip("\"'")
    for name in ("name", "description"):
        if not fields.get(name):
            bad(f"empty or missing {name}: {path}")
    if expected_name and fields.get("name") != expected_name:
        bad(f"skill name does not match directory: {path}")
    return fields


if __name__ == "__main__":
    sys.exit(check(Path(__file__).resolve().parents[2]))
