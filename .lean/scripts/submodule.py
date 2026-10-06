#!/usr/bin/env python3
"""Use application repositories as submodules of a Lean workspace."""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def fail(message):
    raise ValueError(message)


def safe_path(root, relative):
    path = root
    for part in Path(relative).parts:
        if part in ("..", "") or Path(relative).is_absolute():
            fail("path must remain inside the Lean workspace")
        path = path / part
        if path.is_symlink():
            fail(f"symlink boundary: {path}")
    return path


def git(root, *args, optional=False):
    result = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)
    if result.returncode and not optional:
        fail(result.stderr.strip() or f"git command failed: {args[0]}")
    return result.stdout.strip() if not result.returncode else None


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as output:
        json.dump(value, output, indent=2)
        output.write("\n")
        temporary = output.name
    os.replace(temporary, path)


def load(path):
    return json.loads(path.read_text())


def remote_name(remote):
    if not remote or remote.startswith("-") or any(c.isspace() or ord(c) < 32 for c in remote):
        fail("remote must be a URL without whitespace or control characters")
    if "://" in remote:
        parsed = urlsplit(remote)
        if parsed.scheme not in ("https", "ssh", "git", "file"):
            fail("supported remote schemes: https, ssh, git, file")
        if parsed.password or (parsed.scheme == "https" and parsed.username):
            fail("use a Git credential helper; do not put credentials in the URL")
        if parsed.query or parsed.fragment or (parsed.scheme != "file" and not parsed.hostname):
            fail("invalid remote URL")
        tail = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    elif re.fullmatch(r"(?:[A-Za-z0-9._-]+@)?[A-Za-z0-9.-]+:.+", remote):
        tail = remote.split(":", 1)[1].rstrip("/").rsplit("/", 1)[-1]
    else:
        fail("use a remote URL, not a local checkout path")
    name = tail[:-4] if tail.endswith(".git") else tail
    if not NAME.fullmatch(name) or name.endswith("."):
        fail("remote does not have a safe repository name")
    return name


def workspace(root):
    if git(root, "rev-parse", "--show-toplevel") != str(root):
        fail("run this command at the Lean repository root")
    for name in ("AGENTS.md", ".lean/PROJECT.md", ".lean/scripts/workflow.py"):
        if not safe_path(root, name).is_file():
            fail(f"not a Lean workspace: missing {name}")
    if git(root, "check-ignore", ".agent-runtime/active-target.json", optional=True) is None:
        fail("Lean runtime state must be ignored by Git before selecting a target")


def registrations(root):
    modules = safe_path(root, ".gitmodules")
    if not modules.exists():
        return []
    result = subprocess.run(["git", "config", "-z", "--file", str(modules),
                             "--get-regexp", r"^submodule\..*\.path$"],
                            text=True, capture_output=True)
    if result.returncode not in (0, 1):
        fail("invalid .gitmodules")
    values = []
    for entry in result.stdout.split("\0"):
        if not entry:
            continue
        key, path = entry.split("\n", 1)
        url = git(root, "config", "--file", str(modules), "--get", key[:-4] + "url")
        values.append((path, url))
    return values


def plan(root, remote):
    workspace(root)
    name = remote_name(remote)
    path = "targets/" + name
    safe_path(root, path)
    safe_path(root, ".lean/targets/" + name)
    safe_path(root, ".agent-runtime/active-target.json")
    for suffix in ("context.json", ".lean/PROJECT.md", ".lean/config.json", ".gitignore"):
        safe_path(root, ".lean/targets/" + name + "/" + suffix)
    manifest = root / ".lean/targets" / name / "context.json"
    if manifest.exists() and load(manifest) != {"schema": 1, "name": name, "remote": remote}:
        fail("existing target records belong to another context")
    ensure_switchable(root, name)
    entries = registrations(root)
    same = [p for p, url in entries if url == remote]
    if same and same != [path]:
        fail("remote already registered at a different path; select it explicitly outside this installer")
    if any(p == path and url != remote for p, url in entries):
        fail(f"target name collision: {path} belongs to another remote")
    reuse = (path, remote) in entries
    if not reuse and safe_path(root, path).exists():
        fail("target path already exists; existing checkouts are never moved or overwritten")
    if not reuse:
        if (root / ".gitmodules").exists() and not git(root, "ls-files", "--", ".gitmodules"):
            fail("untracked .gitmodules must be reviewed before adding a target")
        for args in (("diff", "--name-only", "--", ".gitmodules"),
                     ("diff", "--cached", "--name-only", "--", ".gitmodules")):
            if git(root, *args):
                fail(".gitmodules has pending changes; preserve them before adding a target")
        if git(root, "ls-files", "--", path):
            fail("target path is already tracked")
        if git(root, "check-ignore", path, optional=True) is not None:
            fail("target path is ignored by Git")
    return {"name": name, "remote": remote, "target": path, "reuse": reuse,
            "records": ".lean/targets/" + name,
            "stages": [] if reuse else [".gitmodules", path]}


@contextlib.contextmanager
def locked(root):
    runtime = safe_path(root, ".agent-runtime")
    runtime.mkdir(exist_ok=True)
    path = safe_path(root, ".agent-runtime/submodule.lock")
    with path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def validate_target(root, name, remote=None):
    if not isinstance(name, str) or not NAME.fullmatch(name) or name.endswith("."):
        fail("invalid active target name")
    path = "targets/" + name
    matches = [url for p, url in registrations(root) if p == path]
    if len(matches) != 1 or (remote is not None and matches[0] != remote):
        fail("active target does not match .gitmodules")
    index = git(root, "ls-files", "--stage", "--", path)
    if not index.startswith("160000 ") or "\n" in index:
        fail("target is not an indexed Git submodule")
    target = safe_path(root, path)
    if not safe_path(root, path + "/.git").is_file() or git(target, "rev-parse", "--show-toplevel") != str(target):
        fail("target submodule is not initialized; run git submodule update --init")
    if git(target, "config", "--get", "remote.origin.url") != matches[0]:
        fail("target origin differs from its registered remote")
    return target


def context(root):
    active = safe_path(root, ".agent-runtime/active-target.json")
    if not active.exists():
        return {"workflow_root": str(root), "project_root": str(root), "record_root": str(root),
                "project_file": str(root / ".lean/PROJECT.md"), "target": None}
    data = load(active)
    if not isinstance(data, dict) or data.get("schema") != 1:
        fail("invalid active target selection")
    name = data.get("name")
    target = validate_target(root, name)
    records = safe_path(root, ".lean/targets/" + name)
    metadata = load(safe_path(root, ".lean/targets/" + name + "/context.json"))
    remote = next(url for path, url in registrations(root) if path == "targets/" + name)
    if metadata != {"schema": 1, "name": name, "remote": remote}:
        fail("target metadata differs from registration")
    project = safe_path(root, str(records.relative_to(root)) + "/.lean/PROJECT.md")
    if not project.is_file():
        fail("missing target PROJECT.md")
    return {"workflow_root": str(root), "project_root": str(target), "record_root": str(records),
            "project_file": str(project), "target": name}


def ensure_switchable(root, new_name):
    active = safe_path(root, ".agent-runtime/active-target.json")
    if not active.exists():
        if new_name is None:
            return
        records = root
    else:
        selection = load(active)
        if isinstance(selection, dict) and selection == {"schema": 1, "name": new_name}:
            return
        if (not isinstance(selection, dict) or set(selection) != {"schema", "name"}
                or selection["schema"] != 1 or not isinstance(selection["name"], str)
                or not NAME.fullmatch(selection["name"]) or selection["name"].endswith(".")):
            fail("invalid active target selection")
        # Deselecting a missing/deinitialized target still checks its retained work.
        records = safe_path(root, ".lean/targets/" + selection["name"])
    import workflow
    workflow.validate_project_paths(records)
    if workflow.active_claims(records, cleanup=False):
        fail("active target has live claims; finish or release them before switching")
    for path in (records / "docs/tracking").glob("TCK*.md"):
        if re.search(r"(?m)^Status: (?:IN_PROGRESS|VALIDATING|REVIEWING)\s*$", path.read_text()):
            fail("active target has an active tracker; finish or pause its work before switching")


def use(root, remote):
    plan(root, remote)  # Invalid inputs must not even create coordination state.
    with locked(root):
        proposal = plan(root, remote)
        target = root / proposal["target"]
        if not proposal["reuse"]:
            git(root, "submodule", "add", "--", remote, proposal["target"])
        else:
            # Initialization is explicit and restricted to this one registered target.
            if not (target / ".git").exists():
                git(root, "submodule", "update", "--init", "--", proposal["target"])
        validate_target(root, proposal["name"], remote)
        branch = git(target, "symbolic-ref", "--quiet", "--short", "HEAD", optional=True)
        if branch is None:
            if git(target, "status", "--porcelain"):
                fail("detached target has pending changes; choose a branch without discarding them")
            default = git(target, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", optional=True)
            if not default or not default.startswith("refs/remotes/origin/"):
                fail("remote default branch is unavailable; choose a target branch manually and rerun")
            pinned = git(target, "rev-parse", "HEAD")
            branch = default[len("refs/remotes/origin/"):]
            local = git(target, "rev-parse", "--verify", "refs/heads/" + branch, optional=True)
            if git(target, "rev-parse", "--verify", default) != pinned or local not in (None, pinned):
                branch = "codex/lean-" + proposal["name"]
                local = git(target, "rev-parse", "--verify", "refs/heads/" + branch, optional=True)
                if local is not None and local != pinned:
                    fail("pinned-commit branch already points elsewhere; choose a target branch manually")
            if local is None:
                git(target, "switch", "-c", branch, "--", pinned)
            else:
                git(target, "switch", "--", branch)
        metadata = {"schema": 1, "name": proposal["name"], "remote": remote}
        manifest = safe_path(root, proposal["records"] + "/context.json")
        if manifest.exists() and load(manifest) != metadata:
            fail("existing target records belong to another context")
        project = safe_path(root, proposal["records"] + "/.lean/PROJECT.md")
        config = safe_path(root, proposal["records"] + "/.lean/config.json")
        ignore = safe_path(root, proposal["records"] + "/.gitignore")
        project.parent.mkdir(parents=True, exist_ok=True)
        if not project.exists():
            project.write_text(f"# Project: {proposal['name']}\n\n## Purpose\nNot defined yet.\n\n"
                               "## Quality Gate\nFill with verified application checks; commands run in the target.\n\n"
                               "<!-- gate:start -->\n```sh\n```\n<!-- gate:end -->\n")
        if not config.exists():
            atomic_json(config, {"mode": "standard", "configured": False, "execution": "direct"})
        if not ignore.exists():
            ignore.write_text(".agent-runtime/\n")
        if not manifest.exists():
            atomic_json(manifest, metadata)
        atomic_json(safe_path(root, ".agent-runtime/active-target.json"),
                    {"schema": 1, "name": proposal["name"]})
        return {**context(root), "branch": branch, "stages": proposal["stages"],
                "target_status": git(target, "status", "--short"),
                "lean_status": git(root, "status", "--short")}


def gate(root, optional=False):
    paths = context(root)
    if paths["target"] is None:
        if optional:
            return 0
        fail("no active target")
    content = Path(paths["project_file"]).read_text()
    start, end = "<!-- gate:start -->", "<!-- gate:end -->"
    if content.count(start) != 1 or content.count(end) != 1 or content.index(start) >= content.index(end):
        fail("target gate markers must appear once and in order")
    block = content.split(start)[1].split(end)[0]
    commands = [line for line in block.splitlines()
                if line.strip() and not line.startswith("```") and not line.lstrip().startswith("#")]
    if not commands:
        print("Target Quality Gate is undefined; fill " + paths["project_file"], file=sys.stderr)
        return 2
    if git(Path(paths["project_root"]), "symbolic-ref", "--quiet", "HEAD", optional=True) is None:
        fail("target is detached; choose a branch before application work")
    for command in commands:
        result = subprocess.run(["bash", "-c", command], cwd=paths["project_root"])
        if result.returncode:
            print(f"Target Quality Gate failed ({result.returncode}): {command}", file=sys.stderr)
            return 2
    return 0


def main():
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("use")
    install.add_argument("remote")
    choice = install.add_mutually_exclusive_group()
    choice.add_argument("--apply", action="store_true")
    choice.add_argument("--dry-run", action="store_true")
    commands.add_parser("context")
    commands.add_parser("clear")
    run_gate = commands.add_parser("gate")
    run_gate.add_argument("--optional", action="store_true")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.command == "use":
            result = use(root, args.remote) if args.apply else plan(root, args.remote)
        elif args.command == "context":
            result = context(root)
        elif args.command == "clear":
            workspace(root)
            with locked(root):
                ensure_switchable(root, None)
                safe_path(root, ".agent-runtime/active-target.json").unlink(missing_ok=True)
            result = context(root)
        else:
            return gate(root, args.optional)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(f"submodule error: {error}", file=sys.stderr)
        if args.command == "use" and args.apply:
            print("Any partial checkout/registration is preserved. Inspect Git status, resolve the cause and rerun; no commit or push was performed.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
