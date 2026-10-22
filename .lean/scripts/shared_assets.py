"""Release skill identities and strictly scoped runtime discovery links."""
from pathlib import Path, PurePosixPath
import os

REQUIRED_SKILLS = ("lean-init", "lean-task", "lean-review", "lean-gate", "lean-scope",
                   "lean-research", "lean-grill", "lean-agents", "lean-effort",
                   "lean-prune", "lean-catalog", "lean-compress", "lean-takeover",
                   "lean-target", "lean-update", "lean-pattern", "lean-audit")
EXTRA_SKILLS = ("lean-prune", "lean-compress", "lean-catalog",
                "lean-takeover", "lean-target", "lean-update", "lean-pattern", "lean-audit")
CORE_SKILLS = tuple(name for name in REQUIRED_SKILLS if name not in EXTRA_SKILLS)
USER_COMMANDS = set(REQUIRED_SKILLS)
SKILL_LINKS = {f"{tree}/{name}": f"../../.lean/skills/{name}"
               for tree in (".claude/skills", ".agents/skills") for name in REQUIRED_SKILLS}
CORE_LINKS = {path: target for path, target in SKILL_LINKS.items() if PurePosixPath(path).name in CORE_SKILLS}


V4_SKILLS = ("lean-init", "lean-task", "lean-review", "lean-gate", "lean-scope",
             "lean-research", "lean-grill", "lean-multi-agent", "lean-clean-queue",
             "lean-model-update", "lean-compress", "lean-takeover-workflow", "lean-use-submodule",
             "lean-clean-repo", "lean-update-workflow", "lean-skill-effort",
             "lean-pattern", "lean-audit", "lean-quality-gate-mode")
V4_EXTRA_SKILLS = ("lean-clean-queue", "lean-clean-repo", "lean-compress", "lean-model-update",
                   "lean-takeover-workflow", "lean-use-submodule", "lean-update-workflow",
                   "lean-pattern", "lean-audit", "lean-quality-gate-mode")
V4_CORE_SKILLS = tuple(name for name in V4_SKILLS if name not in V4_EXTRA_SKILLS)
V4_SKILL_LINKS = {f"{tree}/{name}": f"../../.lean/skills/{name}"
                  for tree in (".claude/skills", ".agents/skills") for name in V4_SKILLS}
V4_CORE_LINKS = {path: target for path, target in V4_SKILL_LINKS.items() if PurePosixPath(path).name in V4_CORE_SKILLS}
PATTERN_SKILLS = tuple(name for name in V4_SKILLS if name != "lean-quality-gate-mode")
PATTERN_FULL_LINKS = {path: target for path, target in V4_SKILL_LINKS.items() if PurePosixPath(path).name in PATTERN_SKILLS}
PREVIOUS_SKILLS = tuple(name for name in PATTERN_SKILLS if name not in ("lean-pattern", "lean-audit"))
PREVIOUS_FULL_LINKS = {path: target for path, target in V4_SKILL_LINKS.items() if PurePosixPath(path).name in PREVIOUS_SKILLS}
LEGACY_SKILLS = tuple(name for name in PREVIOUS_SKILLS if name != "lean-skill-effort")
LEGACY_CORE_LINKS = {path: target for path, target in V4_CORE_LINKS.items() if PurePosixPath(path).name in LEGACY_SKILLS}
LEGACY_FULL_LINKS = {path: target for path, target in V4_SKILL_LINKS.items() if PurePosixPath(path).name in LEGACY_SKILLS}
ALL_KNOWN_SKILLS = frozenset((*REQUIRED_SKILLS, *V4_SKILLS))
RETIRED_SKILLS = frozenset(V4_SKILLS) - frozenset(REQUIRED_SKILLS)
ALL_KNOWN_SKILL_LINKS = {f"{tree}/{name}": f"../../.lean/skills/{name}"
                         for tree in (".claude/skills", ".agents/skills") for name in ALL_KNOWN_SKILLS}
RETIRED_SKILL_LINKS = {path: target for path, target in ALL_KNOWN_SKILL_LINKS.items()
                       if path not in SKILL_LINKS}


def declared_links(registry):
    """Schema 1 remains readable for migrating a previously installed baseline."""
    if registry.get("schema") == 1:
        if registry.get("links"):
            raise ValueError("schema 1 cannot declare links")
        return {}
    links = registry.get("links")
    if registry.get("schema") != 2 or not isinstance(links, dict):
        raise ValueError("registry must declare exactly core or supported full Lean skill discovery links")
    files = registry.get("files", [])
    present = {name for name in ALL_KNOWN_SKILLS if f".lean/skills/{name}/SKILL.md" in files}
    generations = ((REQUIRED_SKILLS, CORE_LINKS, SKILL_LINKS),
                   (V4_SKILLS, V4_CORE_LINKS, V4_SKILL_LINKS),
                   (PATTERN_SKILLS, V4_CORE_LINKS, PATTERN_FULL_LINKS),
                   (PREVIOUS_SKILLS, V4_CORE_LINKS, PREVIOUS_FULL_LINKS),
                   (LEGACY_SKILLS, LEGACY_CORE_LINKS, LEGACY_FULL_LINKS))
    if not any(present == set(names) and links in (core, full) for names, core, full in generations):
        raise ValueError("registry missing canonical skill or unsupported discovery generation")
    for path in files:
        if any(path == link or path.startswith(link + "/") for link in links):
            raise ValueError("registry cannot duplicate files beneath discovery links")
    return links


def link_leaf(root, relative, allow_retired=False):
    """Return an allowed leaf without following it; all parents must be plain."""
    allowed = ALL_KNOWN_SKILL_LINKS if allow_retired else SKILL_LINKS
    if relative not in allowed:
        raise ValueError(f"unregistered discovery link: {relative}")
    path = root / relative
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink() or (parent / ".git").exists():
            raise ValueError(f"symlink/nested repository boundary: {parent}")
    return path


def verify_link(root, relative, require_target=True, allow_retired=False):
    allowed = ALL_KNOWN_SKILL_LINKS if allow_retired else SKILL_LINKS
    path = link_leaf(root, relative, allow_retired=allow_retired)
    if not path.is_symlink() or os.readlink(path) != allowed[relative]:
        raise ValueError(f"incorrect discovery link: {relative}")
    destination = root / ".lean/skills" / PurePosixPath(relative).name
    for parent in (destination, *destination.parents):
        if parent == root:
            break
        if parent.is_symlink() or (parent / ".git").exists():
            raise ValueError(f"canonical skill boundary: {parent}")
    if (destination / "SKILL.md").is_symlink():
        raise ValueError(f"canonical skill boundary: {destination / 'SKILL.md'}")
    if require_target and not (destination / "SKILL.md").is_file():
        raise ValueError(f"missing discovery link target: {relative}")
    return path
