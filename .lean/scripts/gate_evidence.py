#!/usr/bin/env python3
"""Local drift and review receipts; these records are not a security boundary."""
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
CONTRACT = re.compile(r"Contract: (?:risk=(LOW|MEDIUM|HIGH) quality=(STANDARD|HIGH|VERY_HIGH) acceptance=([^<\s].*)|trivial \(([^<].*)\))\Z")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def state(root):
    """Bind HEAD, index and all Git-visible bytes, paths, symlinks and modes."""
    names = set(git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")) - {b""}
    entries = []
    for raw in sorted(names):
        name = os.fsdecode(raw)
        path = root / name
        # A retired index path under a moved symlink is represented by the link itself.
        if any((root / parent).is_symlink() for parent in Path(name).parents):
            continue
        if path.is_symlink():
            value = {"link": os.readlink(path)}
        elif path.is_file():
            value = {"sha256": digest(path.read_bytes()), "mode": path.stat().st_mode & 0o777}
        elif path.is_dir():
            # Gitlinks: include untracked submodule work as well as its commit.
            value = {"submodule": state(path)} if (path / ".git").exists() else {"directory": True}
        else:
            value = None
        entries.append([name, value])
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True)
    return digest(json.dumps([head.stdout.decode().strip(), controls(root),
                             git(root, "ls-files", "--stage", "-z").hex(), entries],
                            ensure_ascii=True, sort_keys=True).encode())


def controls(root):
    names = [".claude/settings.json", ".lean/scripts/quality-gate.sh", ".lean/scripts/gate_evidence.py"]
    names += [str(path.relative_to(root)) for path in sorted((root / ".claude/hooks").glob("*.sh"))]
    values = {}
    for name in names:
        path = root / name
        values[name] = {"sha256": digest(path.read_bytes()), "mode": path.stat().st_mode & 0o777} if path.is_file() else None
    project = root / ".lean/PROJECT.md"
    text = project.read_text() if project.is_file() else ""
    values["gate"] = text.split("<!-- gate:start -->", 1)[-1].split("<!-- gate:end -->", 1)[0]
    return values


def save(path, value):
    if path.parent.is_symlink() or path.is_symlink() or path.with_suffix(".tmp").is_symlink():
        raise ValueError("Evidence state must not cross a symlink boundary")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def human_turn(entry):
    """A person's prompt; runtime-injected skill, hook, task and compaction text is not."""
    if entry.get("type") != "user" or entry.get("isSidechain") or entry.get("isMeta") or entry.get("isCompactSummary"):
        return False
    content = entry.get("message", {}).get("content", [])
    texts = [content] if isinstance(content, str) else [
        block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
    return bool(texts) and not texts[0].lstrip().startswith("<task-notification>")


def contract_from_transcript(path):
    """Use only assistant text in the latest human turn, before known write tools."""
    try:
        entries = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    except ValueError as error:
        raise ValueError("Malformed contract transcript: " + str(error)) from error
    start = 0
    for index, entry in enumerate(entries):
        if human_turn(entry):
            start = index + 1
    for entry in entries[start:]:
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        content = entry.get("message", {}).get("content", [])
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        text_seen = False
        for block in content:
            if block.get("type") == "tool_use" and block.get("name") in {"Edit", "Write", "MultiEdit", "apply_patch"}:
                raise ValueError("Task Contract must precede write tools in the current turn")
            if block.get("type") == "text" and not text_seen:
                first = block.get("text", "").splitlines()
                if first:
                    text_seen = True
                if first and CONTRACT.fullmatch(first[0]):
                    return first[0]
    raise ValueError("No Task Contract first line found in the current turn transcript")


def high_risk_areas(root):
    """Backticked paths in bullets under PROJECT.md's High-risk areas heading."""
    project = root / ".lean/PROJECT.md"
    areas, inside = [], False
    for line in (project.read_text().splitlines() if project.is_file() else []):
        if line.startswith("## "):
            inside = line.strip() == "## High-risk areas"
        elif inside and line.lstrip().startswith("- "):
            areas += [area.removeprefix("./") for area in re.findall(r"`([^`\s]+)`", line)]
    return [area for area in areas if area.strip("/")]


def changed_paths(root):
    """Uncommitted, untracked and session-committed paths relative to the root."""
    names = set(git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0"))
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "-q", "--verify", "HEAD"], capture_output=True)
    if head.returncode:
        names |= set(git(root, "ls-files", "--cached", "-z").split(b"\0"))
    else:
        names |= set(git(root, "diff", "--relative", "--name-only", "--no-renames", "-z", "HEAD").split(b"\0"))
        names |= set(git(root, "diff", "--cached", "--relative", "--name-only", "--no-renames", "-z", "HEAD").split(b"\0"))
        base_file = root / ".agent-runtime/gate-baseline-head"
        base = base_file.read_text().strip() if base_file.is_file() else ""
        if re.fullmatch(r"[0-9a-f]{40,64}", base):
            known = subprocess.run(["git", "-C", str(root), "cat-file", "-e", base + "^{commit}"], capture_output=True)
            if known.returncode == 0:
                names |= set(git(root, "diff", "--relative", "--name-only", "--no-renames", "-z", base, "HEAD").split(b"\0"))
    return sorted(os.fsdecode(name) for name in names - {b""})


def high_risk_changes(root):
    if subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], capture_output=True).returncode:
        return []
    areas = high_risk_areas(root)
    def risky(path):
        for area in areas:
            if any(mark in area for mark in "*?["):
                if fnmatch.fnmatchcase(path, area):
                    return True
            elif path == area.rstrip("/") or path.startswith(area.rstrip("/") + "/"):
                return True
        return False
    return [path for path in changed_paths(root) if risky(path)] if areas else []


def check_review(root, contract):
    receipt = json.loads((root / ".agent-runtime/review.json").read_text())
    if (receipt.get("schema") != 1 or receipt.get("verdict") != "PASS"
            or receipt.get("contract") != contract or receipt.get("state") != state(root)
            or not receipt.get("reviewer") or not receipt.get("evidence")):
        raise ValueError("Review receipt does not cover the current contract and shipping state")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("guard-controls")
    accept = commands.add_parser("accept-controls")
    accept.add_argument("--reason", required=True)
    commands.add_parser("state")
    commands.add_parser("high-risk")
    transcript = commands.add_parser("contract")
    transcript.add_argument("--transcript", required=True)
    field = commands.add_parser("hook-field")
    field.add_argument("--field", choices=("stop_hook_active", "transcript_path"), required=True)
    for name in ("record-review", "check-review"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--contract", required=True)
        if name == "record-review":
            cmd.add_argument("--reviewer", required=True)
            cmd.add_argument("--evidence", required=True)
            cmd.add_argument("--verdict", choices=("PASS", "REWORK"), required=True)
            cmd.add_argument("--state", required=True, help="SHA-256 state captured before review")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command in {"guard-controls", "accept-controls"}:
            path = root / ".agent-runtime/gate-controls.json"
            current = controls(root)
            if args.command == "accept-controls":
                if not args.reason.strip():
                    raise ValueError("User approval reason is required")
                old = json.loads(path.read_text()) if path.exists() else None
                history = old.get("history", []) if old else []
                history.append({"before": old.get("controls") if old else None,
                                "after": current, "reason": args.reason})
                save(path, {"schema": 1, "controls": current, "history": history})
            elif not path.exists():
                save(path, {"schema": 1, "controls": current, "history": []})
            elif json.loads(path.read_text()).get("controls") != current:
                raise ValueError("Protected gate controls changed. Inspect the diff; use accept-controls --reason only for an already user-approved change")
        elif args.command == "state":
            print(state(root))
        elif args.command == "high-risk":
            for path in high_risk_changes(root):
                print(path)
        elif args.command == "contract":
            print(contract_from_transcript(args.transcript))
        elif args.command == "hook-field":
            payload = json.load(sys.stdin)
            value = payload.get(args.field, False if args.field == "stop_hook_active" else "")
            if args.field == "stop_hook_active":
                if not isinstance(value, bool):
                    raise ValueError("stop_hook_active must be a boolean")
                print("1" if value else "0")
            else:
                if not isinstance(value, str) or "\n" in value:
                    raise ValueError("transcript_path must be a single-line path")
                print(value)
        else:
            if not CONTRACT.fullmatch(args.contract):
                raise ValueError("A real Task Contract is required")
            if args.command == "record-review":
                if not args.reviewer.strip() or not args.evidence.strip():
                    raise ValueError("Reviewer identity and review evidence are required")
                current = state(root)
                if args.state != current:
                    raise ValueError("Shipping state changed since review began; review the new delta")
                save(root / ".agent-runtime/review.json", {"schema": 1, "contract": args.contract,
                     "state": current, "reviewer": args.reviewer, "verdict": args.verdict,
                     "evidence": args.evidence})
            else:
                check_review(root, args.contract)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.CalledProcessError) as error:
        print("Gate evidence: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
