"""Release skill identities and strictly scoped runtime discovery links."""
from pathlib import Path, PurePosixPath
import os

REQUIRED_SKILLS = ("lean-init", "lean-task", "lean-review", "lean-gate", "lean-scope",
                   "lean-research", "lean-grill", "lean-multi-agent", "lean-clean-queue",
                   "lean-model-update", "lean-compress", "lean-takeover-workflow", "lean-use-submodule", "lean-clean-repo", "lean-update-workflow")
EXTRA_SKILLS = ("lean-clean-queue", "lean-clean-repo", "lean-compress", "lean-model-update",
                "lean-takeover-workflow", "lean-use-submodule", "lean-update-workflow")
CORE_SKILLS = tuple(name for name in REQUIRED_SKILLS if name not in EXTRA_SKILLS)
USER_COMMANDS = {"lean-init", "lean-task", "lean-model-update", "lean-compress", "lean-clean-queue",
                 "lean-takeover-workflow", "lean-use-submodule", "lean-clean-repo", "lean-update-workflow"}
SKILL_LINKS = {f"{tree}/{name}": f"../../.lean/skills/{name}"
               for tree in (".claude/skills", ".agents/skills") for name in REQUIRED_SKILLS}
CORE_LINKS = {path: target for path, target in SKILL_LINKS.items() if PurePosixPath(path).name in CORE_SKILLS}


def declared_links(registry):
    """Schema 1 remains readable for migrating a previously installed baseline."""
    if registry.get("schema") == 1:
        if registry.get("links"):
            raise ValueError("schema 1 cannot declare links")
        return {}
    links = registry.get("links")
    if registry.get("schema") != 2 or not isinstance(links, dict) or links not in (CORE_LINKS, SKILL_LINKS):
        raise ValueError("registry must declare exactly core or legacy full Lean skill discovery links")
    files = registry.get("files", [])
    for name in REQUIRED_SKILLS:
        if f".lean/skills/{name}/SKILL.md" not in files:
            raise ValueError(f"registry missing canonical skill: {name}")
    for path in files:
        if any(path == link or path.startswith(link + "/") for link in links):
            raise ValueError("registry cannot duplicate files beneath discovery links")
    return links


def link_leaf(root, relative):
    """Return an allowed leaf without following it; all parents must be plain."""
    if relative not in SKILL_LINKS:
        raise ValueError(f"unregistered discovery link: {relative}")
    path = root / relative
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink() or (parent / ".git").exists():
            raise ValueError(f"symlink/nested repository boundary: {parent}")
    return path


def verify_link(root, relative, require_target=True):
    path = link_leaf(root, relative)
    if not path.is_symlink() or os.readlink(path) != SKILL_LINKS[relative]:
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
