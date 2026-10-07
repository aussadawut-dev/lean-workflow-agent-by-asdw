#!/usr/bin/env python3
"""Enable optional Lean discovery links without deleting canonical tools or resources."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from shared_assets import EXTRA_SKILLS, SKILL_LINKS, link_leaf, verify_link


def configure(root, action):
    paths = [f"{tree}/{name}" for tree in (".agents/skills", ".claude/skills") for name in EXTRA_SKILLS]
    present = []
    # Preflight all slots before any writes. Custom skills and parent links block the batch.
    for relative in paths:
        path = link_leaf(root, relative)
        if path.exists() or path.is_symlink():
            verify_link(root, relative)
            present.append(relative)
        destination = root / ".lean/skills" / path.name
        if destination.is_symlink() or any(parent.is_symlink() for parent in destination.parents if parent != root):
            raise ValueError(f"canonical skill boundary: {destination}")
        if not (destination / "SKILL.md").is_file() or (destination / "SKILL.md").is_symlink():
            raise ValueError(f"missing canonical skill: {destination}")
    changed = []
    try:
        for relative in paths:
            path = root / relative
            if action == "enable" and relative not in present:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(SKILL_LINKS[relative], target_is_directory=True)
                changed.append(relative)
            elif action == "disable" and relative in present:
                path.unlink()
                changed.append(relative)
    except OSError:
        for relative in reversed(changed):
            path = root / relative
            if action == "enable":
                path.unlink()
            else:
                path.symlink_to(SKILL_LINKS[relative], target_is_directory=True)
        raise
    enabled = len(present) == len(paths) if action == "status" else action == "enable"
    return {"enabled": enabled, "partial": bool(present) and len(present) != len(paths) if action == "status" else False,
            "changed": changed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "enable", "disable"))
    args = parser.parse_args()
    try:
        print(json.dumps(configure(Path(__file__).resolve().parents[2], args.action)))
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
