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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from contract_guard import LINE as CONTRACT, parse as parse_contract  # noqa: E402


def digest(value):
    return hashlib.sha256(value).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def entries(root, skip=lambda name: False):
    """Bytes, modes and links of every Git-visible path."""
    names = set(git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")) - {b""}
    found = []
    for raw in sorted(names):
        name = os.fsdecode(raw)
        path = root / name
        # A retired index path under a moved symlink is represented by the link itself.
        if skip(name) or any((root / parent).is_symlink() for parent in Path(name).parents):
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
        found.append([name, value])
    return found


def state(root):
    """Gate cache and change baseline: HEAD, index and all Git-visible bytes, paths, symlinks and modes."""
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True)
    return digest(json.dumps([head.stdout.decode().strip(), controls(root),
                             git(root, "ls-files", "--stage", "-z").hex(), entries(root)],
                            ensure_ascii=True, sort_keys=True).encode())


EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def tracker_record(name):
    """A tracker file directly under docs/tracking/, written after review to record its result."""
    path = Path(name)
    return path.parent == Path("docs/tracking") and path.suffix == ".md"


def review_state(root):
    """The reviewed content: Git-visible bytes, modes, links, paths and gate controls.

    Git bookkeeping is left out, so staging or committing keeps this value; `shipping_gap`
    checks that the index and HEAD ship only that content. Submodules keep their full `state`,
    HEAD included. Top-level tracker records are left out (`workflow.py check` validates them).
    """
    found = [entry for entry in entries(root, tracker_record)
             if entry[1] is not None]  # A missing file reads the same deleted, staged or committed.
    return digest(json.dumps(["review", controls(root), found], ensure_ascii=True, sort_keys=True).encode())


def head_tree(root):
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "-q", "--verify", "HEAD^{tree}"], capture_output=True)
    return head.stdout.decode().strip() if head.returncode == 0 else EMPTY_TREE


def captured_state(root):
    """What a reviewer captures before reading: the reviewed content and HEAD's tree together.

    Binding HEAD here means a commit between capture and recording is refused, so the recorded
    base is the tree the reviewer actually saw.
    """
    return digest(json.dumps(["capture", review_state(root), head_tree(root)]).encode())


def shipping_gap(root, base):
    """Why the index or HEAD would ship something other than the reviewed content, or None.

    `base` is HEAD's tree when the review began. While HEAD is still there, each staged path must
    hold its reviewed working-tree bytes (or be unchanged). Once HEAD moves, the commits must
    contain the whole reviewed content: a partial commit ships a combination nobody reviewed.
    """
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    def names(*args):
        # core.fileMode=true: compare modes even where the repository hides them.
        out = subprocess.check_output(["git", "-C", str(root), "-c", "core.fileMode=true", *args],
                                      stderr=subprocess.PIPE, env=env)
        return {os.fsdecode(name) for name in out.split(b"\0") if name}
    keep = lambda found: sorted(name for name in found if not tracker_record(name))
    if head_tree(root) == base:
        unstaged = names("diff", "--no-ext-diff", "--no-renames", "--name-only", "-z")
        raw = subprocess.check_output(["git", "-C", str(root), "-c", "core.fileMode=true", "diff", "--no-ext-diff", "--no-renames", "--cached",
                                       "--raw", "--full-index", "-z", base], stderr=subprocess.PIPE, env=env).split(b"\0")
        gaps = []
        for meta, raw_name in zip(raw[0::2], raw[1::2]):
            name = os.fsdecode(raw_name)
            if not meta.startswith(b":") or tracker_record(name):
                continue
            deleted = set(meta.split()[3].decode()) == {"0"}
            if (deleted and os.path.lexists(root / name)) or (not deleted and name in unstaged):
                gaps.append(name)
        return f"staged content differs from the reviewed working tree: {', '.join(gaps)}" if gaps else None
    pending = keep(names("diff", "--no-ext-diff", "--no-renames", "--name-only", "-z", "HEAD")
                   | names("diff", "--no-ext-diff", "--no-renames", "--cached", "--name-only", "-z", "HEAD")
                   | names("ls-files", "--others", "--exclude-standard", "-z"))
    return (f"HEAD moved since review without the whole reviewed content: {', '.join(pending)}"
            if pending else None)


def receipt_gap(root, receipt):
    """Why a receipt does not cover the current shipping state, or None."""
    base = receipt.get("base")
    if not isinstance(base, str) or not re.fullmatch(r"[0-9a-f]{40,64}", base):
        return "the receipt has no reviewed base; the reviewer re-records it"
    if receipt.get("state") != review_state(root):
        return "the shipping state changed since review"
    return shipping_gap(root, base)


CONTROL_NAMES = (".claude/settings.json", ".lean/scripts/quality-gate.sh", ".lean/scripts/gate_evidence.py",
                 ".lean/scripts/gate_lock.py", ".lean/scripts/contract_guard.py", ".lean/scripts/gate_mode.py",
                 ".codex/hooks.json", ".codex/hooks/quality_gate.py", ".codex/quality-gate.json")
PROJECT = ".lean/PROJECT.md"
TRUSTED_LINE = re.compile(r"(?m)^<!-- trusted-control-refs:(.*?)-->[ \t]*$")
TRUSTED_REF = re.compile(r"refs/remotes/[A-Za-z0-9._/-]+")


def project_controls(values, text):
    """Add the PROJECT.md parts that are gate controls: the gate block and any trusted refs line."""
    values["gate"] = text.split("<!-- gate:start -->", 1)[-1].split("<!-- gate:end -->", 1)[0]
    lines = TRUSTED_LINE.findall(text)
    if lines:
        # Absent unless configured, so projects that do not use it keep their recorded baseline.
        values["trusted_control_refs"] = [line.split() for line in lines]
    return values


def controls(root):
    names = list(CONTROL_NAMES)
    names += [str(path.relative_to(root)) for path in sorted((root / ".claude/hooks").glob("*.sh"))]
    values = {}
    for name in names:
        path = root / name
        values[name] = {"sha256": digest(path.read_bytes()), "mode": path.stat().st_mode & 0o777} if path.is_file() else None
    project = root / PROJECT
    return project_controls(values, project.read_text() if project.is_file() else "")


def controls_at(root, commit):
    """The controls() view of a commit's tree, so it can be compared with the working tree."""
    def entry(name):
        listed = git(root, "--no-replace-objects", "ls-tree", "-z", commit, "--", name).split(b"\0")[0]
        if not listed:
            return None, None
        meta, _ = listed.split(b"\t", 1)
        mode, kind, blob = meta.decode().split()
        if kind != "blob":
            return None, None
        if mode not in ("100644", "100755"):
            return {"unsupported": mode}, None  # A symlink or other entry never matches a local file.
        data = git(root, "--no-replace-objects", "cat-file", "blob", blob)
        return {"sha256": digest(data), "mode": int(mode[-3:], 8)}, data

    hooks = [os.fsdecode(name) for name in git(root, "--no-replace-objects", "ls-tree", "-z", "--name-only", commit, "--", ".claude/hooks/").split(b"\0")]
    names = list(CONTROL_NAMES) + sorted(name for name in hooks if fnmatch.fnmatch(name, ".claude/hooks/*.sh")
                                         and "/" not in name[len(".claude/hooks/"):])
    values = {name: entry(name)[0] for name in names}
    _, project = entry(PROJECT)
    return project_controls(values, project.decode() if project is not None else "")


def comparable(values):
    """Compare file bytes and the executable bit; other permission bits depend on the local umask."""
    return {name: dict(value, mode=bool(value["mode"] & 0o111)) if isinstance(value, dict) and "mode" in value else value
            for name, value in values.items()}


def trusted_match(root, current):
    """Return (ref, commit) when every control equals a configured trusted ref, else None.

    Only remote-tracking refs are accepted: a local branch, tag, HEAD or commit id is whatever
    the agent last wrote. Replace objects are ignored so the ref's own content is compared.
    This is drift detection, not a security boundary; moving a trusted ref (git update-ref,
    a push) still changes what is trusted.
    """
    refs = current.get("trusted_control_refs")
    if not refs:
        return None
    if len(refs) != 1:
        raise ValueError("PROJECT.md must have at most one trusted-control-refs line")
    for ref in refs[0]:
        if not TRUSTED_REF.fullmatch(ref) or ".." in ref or ref.endswith(("/", ".lock")):
            raise ValueError(f"trusted-control-refs accepts only refs/remotes/* names: {ref}")
    names = list(CONTROL_NAMES) + [PROJECT] + [str(path.relative_to(root)) for path in (root / ".claude/hooks").glob("*.sh")]
    if any((root / name).is_symlink() for name in names):
        return None
    for ref in refs[0]:
        if subprocess.run(["git", "-C", str(root), "show-ref", "--verify", "--quiet", ref]).returncode != 0:
            continue
        resolved = subprocess.run(["git", "-C", str(root), "--no-replace-objects", "rev-parse", "--verify", "--quiet",
                                   ref + "^{commit}"], capture_output=True)
        if resolved.returncode != 0:
            continue  # A ref that is not a commit matches nothing; try the next one.
        commit = resolved.stdout.decode().strip()
        if comparable(controls_at(root, commit)) == comparable(current):
            return ref, commit
    return None


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
                text = block.get("text", "")
                if text.strip():
                    text_seen = True
                    try:
                        return parse_contract(text.lstrip("\n").split("\n\n", 1)[0])[0]
                    except ValueError:
                        pass
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
    reasons = []  # Name what differs, so the reviewer can fix the receipt in one step.
    if receipt.get("schema") != 1 or not receipt.get("reviewer") or not receipt.get("evidence"):
        reasons.append("the receipt is malformed")
    if receipt.get("verdict") != "PASS":
        reasons.append(f"its verdict is {receipt.get('verdict')!r}, not PASS")
    if receipt.get("contract") != contract:
        reasons.append(f"its contract {receipt.get('contract')!r} is not the exact contract {contract!r}; "
                       "the reviewer re-records with that exact line")
    gap = receipt_gap(root, receipt)
    if gap:
        reasons.append(gap)
    if reasons:
        raise ValueError("Review receipt does not cover the current contract and shipping state: " + "; ".join(reasons))


def check_shipped(root):
    """A PASS receipt for exactly this shipping state, under any contract.

    The High-risk floor asks that the delta which ships was independently reviewed; a later
    contract that changes nothing (a status reply, say) ships that same reviewed state.
    """
    receipt = json.loads((root / ".agent-runtime/review.json").read_text())
    contract = CONTRACT.fullmatch(str(receipt.get("contract", "")))
    # Only a review at HIGH depth stands in for the floor: a PASS under a lower contract (a typo or a
    # receipt the author wrote) never required an independent reviewer.
    high = contract and (contract.group(1) == "HIGH" or contract.group(2) == "VERY_HIGH")
    if (receipt.get("schema") != 1 or receipt.get("verdict") != "PASS" or receipt_gap(root, receipt)
            or not high or not receipt.get("reviewer") or not receipt.get("evidence")):
        raise ValueError("No HIGH-depth PASS review receipt covers the current shipping state")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("guard-controls")
    accept = commands.add_parser("accept-controls")
    accept.add_argument("--reason", required=True)
    commands.add_parser("state", help="the shipping state a review receipt covers")
    commands.add_parser("gate-state", help="the state a gate cache and change baseline cover")
    commands.add_parser("high-risk")
    commands.add_parser("check-shipped")
    transcript = commands.add_parser("contract")
    transcript.add_argument("--transcript", required=True)
    field = commands.add_parser("hook-field")
    field.add_argument("--field", choices=("stop_hook_active", "transcript_path", "session_id"), required=True)
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
            else:
                old = json.loads(path.read_text())
                if old.get("controls") != current:
                    match = trusted_match(root, current)
                    if match is None:
                        hint = (" No trusted-control-refs entry matches them." if current.get("trusted_control_refs") else "")
                        raise ValueError("Protected gate controls changed. Inspect the diff; use accept-controls --reason "
                                         "only for an already user-approved change." + hint)
                    ref, commit = match
                    reason = f"automatic: controls match trusted ref {ref} at {commit}"
                    history = old.get("history", []) + [{"before": old.get("controls"), "after": current, "reason": reason}]
                    save(path, {"schema": 1, "controls": current, "history": history})
                    print(f"Gate evidence: protected gate controls accepted; they match {ref} ({commit[:12]}).", file=sys.stderr)
        elif args.command == "state":
            print(captured_state(root))
        elif args.command == "gate-state":
            print(state(root))
        elif args.command == "check-shipped":
            check_shipped(root)
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
                    raise ValueError(f"{args.field} must be a single-line string")
                print(value)
        else:
            if not CONTRACT.fullmatch(args.contract):
                raise ValueError("A real Task Contract is required")
            if args.command == "record-review":
                if not args.reviewer.strip() or not args.evidence.strip():
                    raise ValueError("Reviewer identity and review evidence are required")
                if args.state != captured_state(root):
                    raise ValueError("Shipping state or HEAD changed since review began; review the new delta "
                                     "(capture it with `gate_evidence.py state`)")
                current, base = review_state(root), head_tree(root)
                save(root / ".agent-runtime/review.json", {"schema": 1, "contract": args.contract,
                     "state": current, "base": base, "reviewer": args.reviewer, "verdict": args.verdict,
                     "evidence": args.evidence})
            else:
                check_review(root, args.contract)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.CalledProcessError) as error:
        print("Gate evidence: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
