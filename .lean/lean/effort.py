"""Inspect or set Lean procedure intensity; never changes model or runtime settings."""
from .util import LeanError, WORKFLOW_ROOT, locked, read_json, safe_path, write_json

LEVELS = ("standard", "high", "ultra")
SETTINGS = ".lean/skill-effort.json"


def skill_names():
    return sorted(path.parent.name for path in (WORKFLOW_ROOT / ".lean/skills").glob("lean-*/SKILL.md"))


def read_settings(path, names):
    if not path.exists():
        return {"default": "standard", "skills": {}}
    settings = read_json(path)
    if (not isinstance(settings, dict) or set(settings) != {"default", "skills"}
            or settings["default"] not in LEVELS or not isinstance(settings["skills"], dict)
            or any(name not in names or level not in LEVELS for name, level in settings["skills"].items())):
        raise LeanError("invalid shared skill intensity settings")
    return settings


def run(root, level=None, skill=None):
    names = skill_names()
    if skill and skill not in names:
        raise LeanError(f"unknown Lean skill: {skill}")
    path = safe_path(root, SETTINGS)
    if level is None:
        settings = read_settings(path, names)
        lines = ["Lean procedure intensity (separate from model reasoning effort):"]
        lines += [f"{name}: {settings['skills'].get(name, settings['default'])}" for name in names]
        return "\n".join(lines)
    if level not in LEVELS + ("reset",):
        raise LeanError(f"unknown level {level!r}; use standard, high, ultra or reset")
    with locked(root, "skill-effort.lock"):
        settings = read_settings(path, names)
        if level == "reset":
            if not skill:
                path.unlink(missing_ok=True)
                return "All Lean skills: standard procedure intensity (reset)."
            settings["skills"].pop(skill, None)
        elif skill:
            settings["skills"][skill] = level
        else:
            settings = {"default": level, "skills": {}}
        write_json(path, settings)
    effective = settings["skills"].get(skill, settings["default"])
    return f"{skill or 'All Lean skills'}: {effective} procedure intensity. Model settings unchanged."
