"""Update Lean from a pinned upstream release: preview a plan, apply it with snapshots, roll back.

Preview fetches the release into an external workspace and writes nothing to the target.
Apply refuses a target that changed since preview, snapshots every path it touches and journals
each step; rollback restores that snapshot. Project-owned files are preserved or merged, never
replaced. A 4.x installation migrates to the v5 layout (hooks, gate block, gate mode, links).
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from . import structure
from .structure import LINK_TREES, RETIRED_SKILLS
from .util import LeanError, read_json, write_json, write_text

DEFAULT_SOURCE = "https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw.git"
VERSION_TAG = re.compile(r"v?(\d+)\.(\d+)\.(\d+)\Z")
BASELINE = re.compile(r"Lean Workflow Baseline\s+(\d+\.\d+\.\d+)\b")
ADDITIONS = "## Project additions"
# Never replaced from upstream: the project's own facts, settings and records.
PROJECT_OWNED = (".lean/PROJECT.md", ".lean/config.json", ".lean/models.json", ".lean/skill-effort.json",
                 ".lean/gate.json", ".lean/upstream.json", ".gitignore")
MERGED = ("AGENTS.md", "CLAUDE.md", ".claude/settings.json", ".codex/hooks.json")
# What 4.x scripts became, for migration notes.
V5_COMMANDS = {"workflow.py": "`python3 .lean/bin/lean mode|tracker|queue`",
               "submodule.py": "`python3 .lean/bin/lean target`",
               "contract_guard.py": "`python3 .lean/bin/lean contract`",
               "gate_evidence.py": "`python3 .lean/bin/lean evidence`",
               "quality-gate.sh": "`python3 .lean/bin/lean gate run`",
               "gate_mode.py": "`python3 .lean/bin/lean gate mode`",
               "skill_effort.py": "`python3 .lean/bin/lean effort`",
               "model_catalog.py": "`python3 .lean/bin/lean models`"}
LEGACY_PATH = re.compile(r"\.lean/scripts/[\w.-]+|\.claude/hooks/[\w.-]+|\.codex/hooks/[\w.-]+"
                         r"|\.lean/tests/[\w-]+\.(?:sh|py)\b")
# 4.x gate commands and their v5 equivalents; any other gate line is the project's own and stays.
GATE_REWRITES = (
    (re.compile(r"^shellcheck .*\.claude/hooks/\*\.sh.*$"), None),
    (re.compile(r"^\.lean/scripts/check-structure\.sh\s*$"), "python3 .lean/bin/lean lint"),
    (re.compile(r"^python3 \.lean/scripts/workflow\.py --root \. check\s*$"), "python3 .lean/bin/lean --root . mode check"),
    (re.compile(r"^python3 \.lean/scripts/workflow\.py check\s*$"), "python3 .lean/bin/lean mode check"),
    (re.compile(r"^python3 \.lean/scripts/model_catalog\.py --root \. check\s*$"),
     "python3 .lean/bin/lean --root . models check"),
    (re.compile(r"^python3 \.lean/scripts/model_catalog\.py check\s*$"), "python3 .lean/bin/lean models check"),
    (re.compile(r"^python3 \.lean/scripts/model_drift\.py.*$"), None),
    (re.compile(r"^python3 (?:-m unittest discover -s \.lean/tests.*|\.lean/tests/run_tests\.py.*)$"),
     "python3 .lean/bin/lean test --changed"),
    (re.compile(r"^python3 tools/check_commit_attribution\.py.*$"), "python3 .lean/bin/lean attribution"),
    (re.compile(r"^python3 -m unittest discover -s tools .*$"), None),  # Lean's own repository tools.
)


def sha(path):
    """Fingerprint of a path as it stands: file bytes and mode, a link target, or absence."""
    path = Path(path)
    if path.is_symlink():
        return "link:" + os.readlink(path)
    if path.is_file():
        return "file:" + hashlib.sha256(path.read_bytes()).hexdigest() + f":{path.stat().st_mode & 0o111 != 0}"
    if path.exists():
        return "other"
    return None


def git(*args, cwd=None, timeout=120):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-c", "protocol.ext.allow=never", *args],
                            cwd=cwd, env=environment, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise LeanError("Git acquisition failed: " + result.stderr.strip())
    return result.stdout.strip()


def remote_refs(source):
    if source.startswith("-") or "\n" in source:
        raise LeanError("invalid source")
    refs = {}
    for line in git("ls-remote", "--heads", "--tags", "--", source).splitlines():
        commit, name = line.split("\t", 1)
        refs[name] = commit
    return refs


def select(refs, requested=None):
    """(ref name, commit) for a requested ref, or the highest stable semantic-version tag."""
    if requested is None:
        tags = [(tuple(map(int, VERSION_TAG.fullmatch(name[10:]).groups())), name)
                for name in refs if name.startswith("refs/tags/") and VERSION_TAG.fullmatch(name[10:])]
        if not tags:
            raise LeanError("no stable semantic-version tag; specify --ref deliberately")
        requested = max(tags)[1]
    if re.fullmatch(r"[0-9a-f]{40}", requested):
        return requested, requested
    candidates = [requested] if requested.startswith("refs/") else ["refs/tags/" + requested, "refs/heads/" + requested]
    found = [name for name in candidates if name in refs]
    if len(found) != 1:
        raise LeanError("unknown or ambiguous ref; use a full refs/tags/ or refs/heads/ name")
    return found[0], refs.get(found[0] + "^{}", refs[found[0]])


def checkout(source, commit, destination):
    # --no-local: a local source is read through Git's pack transport, not copied file by file, so a pack or
    # gc running in the source repository at the same time cannot leave the copy without an object.
    git("clone", "-q", "--no-local", "--no-checkout", "--", source, str(destination))
    git("-C", str(destination), "checkout", "-q", "--detach", commit)
    if git("-C", str(destination), "rev-parse", "HEAD") != commit:
        raise LeanError("checkout revision mismatch")


def version_of(root):
    path = Path(root) / "AGENTS.md"
    match = BASELINE.search(path.read_text()) if path.is_file() else None
    if not match:
        raise LeanError(f"cannot identify the Lean version from {path}")
    return match.group(1)


def as_tuple(version):
    return tuple(map(int, version.split(".")))


def inside(target, name, kind="path"):
    """target/name, refusing absolute paths, `..`, and symlinked parents: plans and registries are data."""
    relative = Path(name)
    if not name or relative.is_absolute() or ".." in relative.parts or relative.parts[:1] == (".git",):
        raise LeanError(f"{kind} outside the target: {name!r}")
    path = Path(target)
    for part in relative.parts[:-1]:
        path = path / part
        if path.is_symlink():
            raise LeanError(f"{kind} outside the target (through a symlink): {name!r}")
    return Path(target) / relative


LINK_TARGET = re.compile(r"\.\./\.\./\.lean/skills/[A-Za-z0-9_-]+")


def registry(root):
    """(files, links) a release or installation declares as workflow-owned."""
    data = read_json(Path(root) / ".lean/assets.json")
    files = data.get("files", [])
    links = data.get("links") or {}
    if data.get("schema") == 3 and not links:
        links = {f"{tree}/{name}": f"../../.lean/skills/{name}" for tree in (".claude/skills", ".agents/skills")
                 for name in data.get("skills", [])}
    if not isinstance(files, list) or not isinstance(links, dict):
        raise LeanError(f"invalid asset registry in {root}")
    for name in list(files) + list(links):
        inside(root, str(name), "registry path")
    for destination in links.values():
        if not LINK_TARGET.fullmatch(str(destination)):
            raise LeanError(f"registry link outside the target: {destination!r}")
    return [name for name in files if name not in PROJECT_OWNED + MERGED], links


def outside_checkouts(path):
    for parent in (path, *path.parents):
        if (parent / ".git").exists() or parent.name == ".git":
            raise LeanError(f"workspace must be outside every Git checkout: {parent}")


def additions(text):
    """The project's own section of an entrypoint, kept across updates."""
    return text.split(ADDITIONS, 1)[1] if ADDITIONS in text else "\n"


def merge_entrypoint(local, incoming):
    if not local.is_file():
        return incoming.read_text()
    return incoming.read_text().split(ADDITIONS, 1)[0] + ADDITIONS + additions(local.read_text())


LEAN_COMMAND = re.compile(r"\.lean/|\.claude/hooks/|\.codex/hooks/")


def lean_owned(entry):
    """Whether a hook group or status line runs Lean (any version), as opposed to the project's own."""
    hooks = entry.get("hooks", []) if isinstance(entry, dict) and "hooks" in entry else [entry]
    return any(isinstance(hook, dict) and LEAN_COMMAND.search(str(hook.get("command", ""))) for hook in hooks)


def merge_settings(local, incoming, notes):
    """Lean's hook entries and status line from upstream; the project's own hooks, status line and
    every other key (permissions, env) are kept."""
    merged = json.loads(local.read_text()) if local.is_file() else {}
    upstream = json.loads(incoming.read_text())
    own = {event: [group for group in groups if not lean_owned(group)]
           for event, groups in (merged.get("hooks") or {}).items() if isinstance(groups, list)}
    hooks = {event: list(groups) + own.pop(event, []) for event, groups in (upstream.get("hooks") or {}).items()}
    hooks.update({event: groups for event, groups in own.items() if groups})
    merged["hooks"] = hooks
    status = merged.get("statusLine")
    if "statusLine" in upstream:
        if status and not lean_owned(status):
            notes.append("kept your status line in .claude/settings.json; Lean's is "
                         f"{upstream['statusLine'].get('command', '')!r}")
        else:
            merged["statusLine"] = upstream["statusLine"]
    return json.dumps(merged, indent=2) + "\n"


def migrate_project(text, notes):
    """Rewrite known 4.x gate commands; project-specific lines stay as they are."""
    if "<!-- gate:start -->" not in text or "<!-- gate:end -->" not in text:
        return text
    head, rest = text.split("<!-- gate:start -->", 1)
    block, tail = rest.split("<!-- gate:end -->", 1)
    lines, seen = [], set()
    for line in block.split("\n"):
        replacement = line
        for pattern, new in GATE_REWRITES:
            if pattern.match(line.strip()):
                replacement = new
                notes.append(f"gate: {line.strip()} -> {new or '(removed: no longer part of Lean)'}")
                break
        if replacement is None or (replacement != line and replacement in seen):
            continue
        seen.add(replacement)
        lines.append(replacement)
    block = "\n".join(lines)
    text = head + "<!-- gate:start -->" + block + "<!-- gate:end -->" + tail
    return text.replace(".lean/scripts/workflow.py", ".lean/bin/lean mode").replace(
        ".lean/scripts/quality-gate.sh", ".lean/bin/lean gate run")


def preview(root, target=None, source=None, ref=None, workspace=None):
    target = Path(target or root).resolve()
    installed = version_of(target)
    workspace = Path(workspace or Path(tempfile.gettempdir()) / f"lean-update-{time.strftime('%Y%m%d-%H%M%S')}").resolve()
    outside_checkouts(workspace)
    if workspace.exists():
        raise LeanError("workspace already exists; choose a fresh path")
    source = source or DEFAULT_SOURCE
    if Path(source).is_dir():
        source = str(Path(source).resolve())
    release_ref, commit = select(remote_refs(source), ref)
    workspace.mkdir(parents=True, mode=0o700)
    release = workspace / "release"
    checkout(source, commit, release)
    incoming = version_of(release)
    if as_tuple(incoming) < as_tuple(installed):
        raise LeanError(f"release {incoming} is older than installed {installed}; a downgrade needs its own scope")
    if release_ref.startswith("refs/tags/") and VERSION_TAG.fullmatch(release_ref[10:]):
        if tuple(map(int, VERSION_TAG.fullmatch(release_ref[10:]).groups())) != as_tuple(incoming):
            raise LeanError("tag and AGENTS.md baseline versions disagree")
    new_files, new_links = registry(release)
    old_files, old_links = registry(target) if (target / ".lean/assets.json").is_file() else ([], {})
    previous = None
    provenance = target / ".lean/upstream.json"
    if provenance.is_file():
        recorded = read_json(provenance)
        if recorded.get("source") == source and re.fullmatch(r"[0-9a-f]{40}", str(recorded.get("commit", ""))):
            previous = workspace / "previous"
            checkout(source, recorded["commit"], previous)
    operations, notes = [], []

    def add(path, action, content=None, link=None, mode=None, reason=""):
        operations.append({"path": path, "action": action, "content": content, "link": link, "mode": mode,
                           "reason": reason, "before": sha(target / path)})

    for name in sorted(set(new_files)):
        source_path, local = release / name, target / name
        if sha(local) == sha(source_path):
            continue
        executable = os.access(source_path, os.X_OK)
        if not local.exists():
            add(name, "write", source_path.read_text(), mode=executable, reason="new in this release")
        elif previous and sha(local) == sha(previous / name):
            add(name, "write", source_path.read_text(), mode=executable, reason="unmodified locally")
        elif name in old_files and not previous and as_tuple(installed)[0] < as_tuple(incoming)[0]:
            add(name, "write", source_path.read_text(), mode=executable, reason="major-version migration")
        else:
            add(name, "conflict", source_path.read_text(), mode=executable,
                reason="changed locally and upstream; kept unless --take names it")
    for name in sorted(set(old_files) - set(new_files)):
        local = target / name
        if not local.exists():
            continue
        if previous and sha(local) != sha(previous / name):
            add(name, "keep", reason="retired upstream but modified locally; review and delete by hand")
        else:
            add(name, "delete", reason="retired by this release")
    for link, destination in sorted(new_links.items()):
        if (target / link).is_symlink() and os.readlink(target / link) == destination:
            continue
        add(link, "link", link=destination, reason="skill discovery link")
    retired = set()
    for link, destination in sorted(old_links.items()):
        if link not in new_links and (target / link).is_symlink():
            retired.add(link)
            add(link, "delete", reason="retired skill discovery link")
    # Optional 4.x skills were linked outside the registry (skill_pack); remove links to retired skills too.
    for tree in LINK_TREES:
        for skill in RETIRED_SKILLS:
            link = f"{tree}/{skill}"
            path = target / link
            if (link not in retired and link not in new_links and path.is_symlink()
                    and os.readlink(path) == f"../../.lean/skills/{skill}"):
                add(link, "delete", reason="retired skill discovery link")
    for name in MERGED:
        if not (release / name).is_file():
            continue
        if name.endswith(".json"):
            merged = merge_settings(target / name, release / name, notes)
            reason = "merged: Lean's hook entries updated; your permissions, other hooks and settings kept"
        else:
            merged = merge_entrypoint(target / name, release / name)
            reason = "merged: upstream body, your Project additions kept"
        if not (target / name).is_file() or merged != (target / name).read_text():
            add(name, "write", merged, reason=reason)
        if name.endswith(".md"):
            for legacy in sorted(set(LEGACY_PATH.findall(additions(merged)))):
                notes.append(f"{name} Project additions still name the 4.x path {legacy}; replace it with "
                             f"{V5_COMMANDS.get(Path(legacy).name, 'the matching lean command')}")
    project = target / ".lean/PROJECT.md"
    if project.is_file():
        migrated = migrate_project(project.read_text(), notes)
        if migrated != project.read_text():
            add(".lean/PROJECT.md", "write", migrated, reason="gate block migrated to the lean CLI")
        for legacy in sorted(set(LEGACY_PATH.findall(migrated))):
            notes.append(f"PROJECT.md still names the 4.x path {legacy}; update it (lean lint reports it)")
    # Preserve project prose; warn about current Purpose declarations, never historical sections.
    projects = [project] + sorted((target / ".lean/targets").glob("*/.lean/PROJECT.md"))
    for document in projects:
        relative = str(document.relative_to(target))
        if any(part.is_symlink() for part in (document, *document.parents) if part != target):
            continue
        if not document.is_file():
            continue
        purpose = re.search(r"(?ms)^## Purpose[ \t]*\n(.*?)(?=^## |\Z)", document.read_text())
        if purpose:
            for version in sorted(set(BASELINE.findall(purpose.group(1)))):
                if version != incoming:
                    notes.append(f"{relative} Purpose names Lean Workflow Baseline {version}; incoming is {incoming}. "
                                 "Review the project-owned wording; it is preserved.")
    # Project documents PROJECT.md routes agents to are linted too, and nothing the update writes reaches them.
    visible = set(structure.git_visible(target) or [])  # What lint reads; never a path outside the target.
    for route in structure.routed_documents(target):
        for name in (route, ".lean/" + route):
            if name not in visible or name in new_files:
                continue
            try:  # Read what lint reads, a link included, but never a file outside the target.
                if not (target / name).resolve().is_relative_to(target.resolve()):
                    continue
                text = (target / name).read_text()
            except UnicodeDecodeError:
                notes.append(f"{name} is not UTF-8 text; lean lint reports it as unreadable")
                continue
            except (OSError, RuntimeError):  # RuntimeError: a link loop before 3.13.
                continue
            for legacy in sorted(set(LEGACY_PATH.findall(text))):
                notes.append(f"{name} still names the 4.x path {legacy}; update it (lean lint reports it)")
    # A project's own file inside a workflow-owned folder survives the update, and lint then rejects it.
    deleted = {operation["path"] for operation in operations if operation["action"] == "delete"}
    for name in sorted(visible):
        if name.startswith(structure.WORKFLOW_DIRS) and name not in new_files and name not in deleted:
            notes.append(f"{name} is not part of Lean but sits in a workflow-owned folder; the update keeps it and "
                         "lean lint rejects it: move it out (or delete it) after review")
    legacy_gate = target / ".codex/quality-gate.json"
    if legacy_gate.is_file() and not (target / ".lean/gate.json").exists():
        add(".lean/gate.json", "write", legacy_gate.read_text(), reason="gate mode moved from .codex/quality-gate.json")
        add(".codex/quality-gate.json", "delete", reason="gate mode moved to .lean/gate.json")
    if not (target / ".lean/models.json").exists() and (release / ".lean/models.json").is_file():
        add(".lean/models.json", "write", (release / ".lean/models.json").read_text(), reason="default model list")
    ignore = target / ".gitignore"
    lines = ignore.read_text().splitlines() if ignore.is_file() else []
    if ".agent-runtime/" not in lines:
        add(".gitignore", "write", "\n".join(lines + ["", "# Lean runtime state", ".agent-runtime/"]) + "\n",
            reason="ignore local runtime state")
    add(".lean/upstream.json", "write", json.dumps({"schema": 1, "source": source, "ref": release_ref, "commit": commit},
                                                   indent=2) + "\n", reason="upstream provenance")
    plan = {"schema": 1, "target": str(target), "source": source, "ref": release_ref, "commit": commit,
            "installed_version": installed, "incoming_version": incoming, "operations": operations,
            "notes": notes, "status": "PREVIEW"}
    write_json(workspace / "plan.json", plan)
    return workspace, plan


def report(workspace, plan):
    counts = {}
    for operation in plan["operations"]:
        counts[operation["action"]] = counts.get(operation["action"], 0) + 1
    lines = [f"Lean update {plan['installed_version']} -> {plan['incoming_version']} ({plan['ref']} {plan['commit'][:12]})",
             "operations: " + ", ".join(f"{count} {action}" for action, count in sorted(counts.items()))]
    quiet = ("new in this release", "unmodified locally", "skill discovery link")
    for operation in plan["operations"]:
        action, reason = operation["action"], operation["reason"]
        if action == "write" and operation["before"] is not None and reason not in quiet:
            # An existing file is overwritten: name every one, not just the count.
            action = ("replace" if reason == "major-version migration" else
                      "merge" if reason.startswith("merged") else "write")
        elif action not in ("conflict", "keep", "delete"):
            continue
        lines.append(f"  {action:<8} {operation['path']} — {reason}")
    lines += [f"  note: {note}" for note in plan["notes"]]
    lines.append(f"plan: {workspace / 'plan.json'}")
    entry = Path(__file__).resolve().parents[1] / "bin/lean"
    lines.append(f"apply: python3 {entry} update apply --workspace {workspace}")
    return "\n".join(lines)


def apply(workspace, take=()):
    workspace = Path(workspace).resolve()
    plan = read_json(workspace / "plan.json")
    if plan.get("status") != "PREVIEW":
        raise LeanError(f"plan status is {plan.get('status')}; preview again for a new update")
    target = Path(plan["target"])
    for op in plan["operations"]:
        inside(target, op["path"], "plan path")
        if op["action"] == "link" and not LINK_TARGET.fullmatch(str(op.get("link"))):
            raise LeanError(f"plan link outside the target: {op.get('link')!r}")
    drift = [op["path"] for op in plan["operations"] if sha(target / op["path"]) != op["before"]]
    if drift:
        raise LeanError("target changed since preview; preview again: " + ", ".join(drift[:10]))
    unknown = set(take) - {op["path"] for op in plan["operations"] if op["action"] == "conflict"}
    if unknown:
        raise LeanError("--take names no conflict in the plan: " + ", ".join(sorted(unknown)))
    snapshot = workspace / "snapshot"
    snapshot.mkdir()
    journal = []
    for op in plan["operations"]:
        action = "write" if op["action"] == "conflict" and op["path"] in take else op["action"]
        if action in ("conflict", "keep"):
            continue
        path = target / op["path"]
        saved = snapshot / op["path"]
        saved.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            os.symlink(os.readlink(path), saved)
        elif path.is_file():
            shutil.copy2(path, saved)
        journal.append({"path": op["path"], "existed": path.exists() or path.is_symlink()})
        write_json(workspace / "journal.json", {"schema": 1, "entries": journal, "complete": False})
        if action == "delete":
            path.unlink()
        elif action == "link":
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_symlink() or path.is_file():
                path.unlink()
            os.symlink(op["link"], path)
        else:
            write_text(path, op["content"])
            if op.get("mode") is not None:  # Release files carry the release's executable bit.
                current = path.stat().st_mode
                path.chmod(current | 0o111 if op["mode"] else current & ~0o111)
        journal[-1]["after"] = sha(path)
    write_json(workspace / "journal.json", {"schema": 1, "entries": journal, "complete": True})
    plan["status"] = "APPLIED"
    write_json(workspace / "plan.json", plan)
    remove_empty(target, [entry["path"] for entry in journal])
    entry = Path(__file__).resolve().parents[1] / "bin/lean"
    return f"applied {len(journal)} operation(s); rollback: python3 {entry} update rollback --workspace {workspace}"


def remove_empty(target, paths):
    for name in paths:
        parent = (target / name).parent
        while parent != target and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent


def rollback(workspace):
    workspace = Path(workspace).resolve()
    plan = read_json(workspace / "plan.json")
    journal = read_json(workspace / "journal.json")
    target = Path(plan["target"])
    changed = [entry["path"] for entry in journal["entries"]
               if "after" in entry and sha(target / entry["path"]) != entry["after"]]
    if changed:
        raise LeanError("files changed after the update; restore them by hand first: " + ", ".join(changed[:10]))
    for entry in journal["entries"]:
        inside(target, entry["path"], "journal path")
    for entry in reversed(journal["entries"]):
        path, saved = target / entry["path"], workspace / "snapshot" / entry["path"]
        if path.is_symlink() or path.is_file():
            path.unlink()
        if entry["existed"]:
            path.parent.mkdir(parents=True, exist_ok=True)
            if saved.is_symlink():
                os.symlink(os.readlink(saved), path)
            else:
                shutil.copy2(saved, path)
    plan["status"] = "ROLLED_BACK"
    write_json(workspace / "plan.json", plan)
    return f"restored {len(journal['entries'])} path(s) from {workspace / 'snapshot'}"


def command(root, args):
    if args.action == "preview":
        workspace, plan = preview(root, args.target, args.source, args.ref, args.workspace)
        print(report(workspace, plan))
    elif args.action == "apply":
        print(apply(args.workspace, args.take))
    else:
        print(rollback(args.workspace))
    return 0
