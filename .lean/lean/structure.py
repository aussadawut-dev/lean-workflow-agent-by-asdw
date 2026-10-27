"""Static workflow checks (`lean lint`): code compiles, references resolve, skills and hooks are wired."""
import json
import os
from pathlib import Path
import re
import subprocess

from . import models
from .util import read_json

SKILLS = ("lean-init", "lean-task", "lean-scope", "lean-research", "lean-grill", "lean-agents",
          "lean-review", "lean-gate", "lean-effort", "lean-update", "lean-target")
# 4.x skill names whose discovery links must not linger after an upgrade.
RETIRED_SKILLS = ("lean-audit", "lean-catalog", "lean-compress", "lean-pattern", "lean-playbook", "lean-prune",
                  "lean-takeover", "lean-multi-agent", "lean-clean-queue", "lean-model-update",
                  "lean-takeover-workflow", "lean-use-submodule", "lean-clean-repo", "lean-update-workflow",
                  "lean-skill-effort", "lean-quality-gate-mode")
LINK_TREES = (".claude/skills", ".agents/skills")
# Paths created on demand (full mode, project choices); Markdown may name them before they exist.
OPTIONAL_PATHS = (".agents/queue/", ".lean/targets/", ".lean/skill-effort.json", ".lean/upstream.json",
                  ".lean/gate.json")
# History and migration notes name paths that no longer exist on purpose.
HISTORY_MARKDOWN = (".lean/CHANGELOG.md", "docs/history/", "docs/benchmarks/", "docs/tracking/", "docs/migrating-to-v5.md",
                    "evals/")
LEGACY_PATHS = (".codex/quality-gate.json",)  # 4.x gate mode file that `lean update` migrates.
VERSION = re.compile(r"Lean Workflow Baseline (\d+\.\d+\.\d+)")
# Workflow-owned directories: every Git-visible file in them ships in the asset registry.
WORKFLOW_DIRS = (".lean/bin/", ".lean/lean/", ".lean/policy/", ".lean/roles/", ".lean/skills/", ".lean/templates/",
                 ".lean/tests/")


def git_visible(root):
    result = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                            capture_output=True)
    if result.returncode:
        return None
    return sorted({name for name in result.stdout.decode().split("\0") if name and (root / name).exists()})


def frontmatter(path, bad, expected=None):
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", path.read_text(), re.DOTALL)
    if not match:
        bad(f"no closed frontmatter: {path}")
        return {}
    fields = {name: value.strip().strip("\"'") for name, value in
              re.findall(r"(?m)^([a-z-]+):[ \t]*(.*)$", match.group(1))}
    for name in ("name", "description"):
        if not fields.get(name):
            bad(f"empty or missing {name}: {path}")
    if expected and fields.get("name") != expected:
        bad(f"skill name does not match directory: {path}")
    return fields


# Release files outside the workflow directories, and the project files a release never carries.
RELEASE_EXTRAS = (".lean/README.md", ".lean/CHANGELOG.md", ".lean/CUSTOMIZING.md", ".lean/LICENSE", ".lean/assets.json",
                  ".claude/agents/reviewer.md", ".codex/hooks.json", ".claude/settings.json", "AGENTS.md", "CLAUDE.md")


def write_registry(root):
    """Regenerate .lean/assets.json from the Git-visible workflow files (maintainers review the diff)."""
    root = Path(root)
    files = [name for name in git_visible(root) or [] if name.startswith(WORKFLOW_DIRS)]
    files += [name for name in RELEASE_EXTRAS if (root / name).is_file()]
    skills = sorted(path.parent.name for path in (root / ".lean/skills").glob("*/SKILL.md"))
    data = {"schema": 3, "skills": skills, "files": sorted(set(files))}
    (root / ".lean/assets.json").write_text(json.dumps(data, indent=2) + "\n")
    return len(data["files"])


def routed_documents(root):
    """Backticked Markdown paths listed under PROJECT.md's Documentation routes heading."""
    project = Path(root) / ".lean/PROJECT.md"
    routes, inside = [], False
    for line in (project.read_text().splitlines() if project.is_file() else []):
        if line.startswith("## "):
            inside = line.strip() == "## Documentation routes"
        elif inside:
            routes += [path.removeprefix("./") for path in re.findall(r"`([^`\s]+\.md)`", line)]
    return routes


def references(text):
    """The workflow paths (.lean, .claude, .agents, .codex) a document names."""
    return sorted(set(re.findall(r"\.(?:lean|claude|agents|codex)/[A-Za-z0-9_./-]+\.(?:md|sh|py|json)", text)))


def instruction_markdown(root, visible):
    visible = set(visible)
    found = {name for name in visible if name.endswith(".md") and name.startswith(WORKFLOW_DIRS)}
    found |= {name for name in RELEASE_EXTRAS + ("AGENTS.md", "CLAUDE.md", ".lean/PROJECT.md")
              if name.endswith(".md") and name in visible}
    for route in routed_documents(root):
        candidates = (route, ".lean/" + route)
        found |= {name for name in candidates if name in visible}
    return found


def check(root):
    """Return the list of failures (empty means the structure is sound)."""
    root = Path(root)
    failures = []
    bad = failures.append
    visible = git_visible(root)
    if visible is None:
        bad("cannot enumerate Git-visible files; initialise Git after copying the workflow")
        visible = []

    # Workflow code compiles under the running interpreter.
    sources = [name for name in visible if name.startswith(".lean/") and name.endswith(".py")]
    sources += [".lean/bin/lean"] if (root / ".lean/bin/lean").is_file() else []
    for name in sources:
        try:
            compile((root / name).read_text(), name, "exec")
        except SyntaxError as error:
            bad(f"syntax error: {name}:{error.lineno}: {error.msg}")
    entry = root / ".lean/bin/lean"
    if not entry.is_file() or not os.access(entry, os.X_OK):
        bad("missing or non-executable: .lean/bin/lean")

    # Portable asset registry.
    try:
        registry = read_json(root / ".lean/assets.json")
        files = registry["files"]
        if (registry.get("schema") != 3 or not isinstance(files, list) or len(files) != len(set(files))
                or ".lean/assets.json" not in files):
            raise ValueError("invalid registry")
        for name in files:
            path = root / name
            if (Path(name).is_absolute() or ".." in Path(name).parts or not path.is_file()
                    or any(parent.is_symlink() for parent in (path, *path.parents) if root in parent.parents)):
                bad(f"invalid/missing portable asset: {name}")
        for name in SKILLS:
            if f".lean/skills/{name}/SKILL.md" not in files:
                bad(f"portable registry missing canonical skill: {name}")
        if sorted(registry.get("skills", [])) != sorted(SKILLS):
            bad("portable registry skills list differs from the canonical skills")
        for name in visible:
            if name.startswith(WORKFLOW_DIRS) and name not in files:
                bad(f"workflow file missing from .lean/assets.json: {name}")
    except (OSError, ValueError, KeyError, TypeError):
        bad("invalid or missing portable asset registry (.lean/assets.json, schema 3)")

    # Skills and discovery links.
    for name in SKILLS:
        path = root / ".lean/skills" / name / "SKILL.md"
        if not path.is_file():
            bad(f"missing canonical skill: {name}")
            continue
        fields = frontmatter(path, bad, name)
        if fields.get("user-invocable") != "true" or not fields.get("argument-hint"):
            bad(f"skill must be user-invocable with an argument hint: {name}")
        for tree in LINK_TREES:
            link = root / tree / name
            if not link.is_symlink() or os.readlink(link) != f"../../.lean/skills/{name}":
                bad(f"incorrect discovery link: {tree}/{name}")
    if (root / ".lean/skills").is_dir():
        for entry_dir in sorted((root / ".lean/skills").iterdir()):
            if entry_dir.name not in SKILLS:
                bad(f"unregistered canonical skill: .lean/skills/{entry_dir.name}")
    for tree in LINK_TREES:
        for entry_link in sorted((root / tree).iterdir()) if (root / tree).is_dir() else []:
            if entry_link.name in RETIRED_SKILLS or (entry_link.is_symlink() and not entry_link.exists()):
                bad(f"retired or broken discovery link: {tree}/{entry_link.name}")
            elif entry_link.name not in SKILLS and (entry_link / "SKILL.md").is_file():
                frontmatter(entry_link / "SKILL.md", bad, entry_link.name)  # A local extension.

    # Markdown that agents follow must name workflow paths that exist: workflow-owned documents,
    # the entrypoints, PROJECT.md and the documents PROJECT.md routes to. Other project documents
    # (history, evaluations, evidence) may name retired paths.
    for name in sorted(instruction_markdown(root, visible)):
        if name.startswith(HISTORY_MARKDOWN):
            continue
        try:
            text = (root / name).read_text()
        except (OSError, UnicodeDecodeError):
            bad(f"unreadable instruction document (not UTF-8 text?): {name}")
            continue
        for reference in references(text):
            if reference.startswith(OPTIONAL_PATHS) or reference in OPTIONAL_PATHS + LEGACY_PATHS:
                continue
            if not (root / reference).exists():
                bad(f"missing {reference} (from {name})")
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = root / name
        if not path.is_file():
            bad(f"missing entrypoint: {name}")
            continue
        for reference in re.findall(r"(?m)^@([^\n]+)$", path.read_text()):
            if not (root / reference.strip()).is_file():
                bad(f"missing import {reference.strip()} (from {name})")
    router = root / ".lean/README.md"
    if router.is_file():
        for reference in re.findall(r"`((?:policy/)?[A-Z][A-Z_-]*\.md)`", router.read_text()):
            target = root / reference if reference in ("AGENTS.md", "CLAUDE.md") else root / ".lean" / reference
            if not target.is_file():
                bad(f"missing .lean/{reference} (from policy router)")
    for path in sorted((root / ".lean/policy").glob("*.md")):
        for reference in re.findall(r"`([A-Z][A-Z_-]*\.md)`", path.read_text()):
            if not (path.parent / reference).is_file() and not (root / reference).is_file():
                bad(f"missing sibling policy {reference} (from {path.name})")

    # HIGH review routing stays independent and model-sized.
    for name in ("AGENTS.md", ".lean/skills/lean-task/SKILL.md", ".lean/skills/lean-review/SKILL.md"):
        path = root / name
        if path.is_file():
            paragraphs = re.split(r"\n\s*\n", path.read_text())
            if not any("HIGH" in p and "independent" in p.lower() and "MODELS.md" in p for p in paragraphs):
                bad(f"HIGH reviewer routing requires independent review and model/effort policy: {name}")
    reviewer = root / ".claude/agents/reviewer.md"
    if reviewer.is_file():
        frontmatter(reviewer, bad)
        if "../../.lean/roles/reviewer.md" not in reviewer.read_text():
            bad("reviewer must route to the shared role")

    # Provider hook wiring goes through the CLI.
    for name, provider in ((".claude/settings.json", "claude"), (".codex/hooks.json", "codex")):
        path = root / name
        try:
            text = path.read_text()
            json.loads(text)
        except (OSError, ValueError):
            bad(f"invalid JSON: {name}")
            continue
        if not re.search(r'\.lean/bin/lean(?:\\?")? hook ' + provider + r" ", text):
            bad(f"hooks must call the lean CLI: {name}")
        if "--seed" in text:
            bad(f"--seed must not appear in {name} (it would disable the gate)")
    try:
        problems = models.validate(read_json(root / models.FILE))
        for problem in problems:
            bad(f"{models.FILE}: {problem}")
    except (OSError, ValueError):
        bad(f"invalid or missing {models.FILE}")

    # One workflow version everywhere it is stated.
    found = {}
    for name in ("AGENTS.md", ".lean/README.md"):
        path = root / name
        match = VERSION.search(path.read_text()) if path.is_file() else None
        found[name] = match.group(1) if match else None
    changelog = root / ".lean/CHANGELOG.md"
    match = re.search(r"(?m)^## (\d+\.\d+\.\d+)", changelog.read_text()) if changelog.is_file() else None
    found[".lean/CHANGELOG.md"] = match.group(1) if match else None
    from . import __version__
    found[".lean/lean/__init__.py"] = __version__
    if len(set(found.values())) != 1 or None in found.values():
        bad("workflow version differs or is missing: " + ", ".join(f"{k}={v}" for k, v in found.items()))

    # Runtime state stays out of Git, and the gate block is well formed.
    if subprocess.run(["git", "-C", str(root), "check-ignore", "-q", ".agent-runtime/gate-cache"]).returncode:
        bad("not ignored by git: .agent-runtime/")
    project = root / ".lean/PROJECT.md"
    if project.is_file():
        text = project.read_text()
        for marker in ("gate:start", "gate:end"):
            count = text.count(f"<!-- {marker} -->")
            if count != 1:
                bad(f"expected one {marker} marker in .lean/PROJECT.md, found {count}")
    else:
        bad("missing .lean/PROJECT.md")
    return failures
