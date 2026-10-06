#!/usr/bin/env python3
"""Auditable local workflow migration. Semantic decisions belong to the skill.

Sessions live outside the target. No target code runs here. Locks coordinate
cooperating local tools, not hostile processes replacing paths concurrently.
"""
import argparse
import base64
import contextlib
import fcntl
import hashlib
import importlib.util
import re
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
import time
import uuid


SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
             ".next", ".cache", ".agent-runtime"}
RUNTIME_DIRS = {".lean", ".claude", ".agents", ".cursor", ".windsurf", ".github", ".codex"}
MANIFESTS = {"package.json", "pyproject.toml", "Makefile", "Cargo.toml", "go.mod",
             "Gemfile", "justfile", ".gitignore", ".cursorrules", ".windsurfrules"}
RECORD_DIRS = ("docs/tracking/", ".agents/queue/")
RECORD_SUPPORT = {"docs/tracking/README.md", "docs/tracking/TEMPLATE.md",
                  ".agents/queue/README.md", ".agents/queue/schema/queue-item.schema.json"}


def fail(message):
    raise ValueError(message)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def json_digest(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def load(path):
    return json.loads(path.read_text())


def atomic(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fchmod(output.fileno(), mode)
            os.fsync(output.fileno())
        os.replace(temporary, path)
        # Persist the directory entry as well as the file before advancing a journal.
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save(path, value):
    atomic(path, (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode())


def plain_path(path):
    path = Path(os.path.abspath(path))
    for parent in (path, *path.parents):
        if parent.is_symlink():
            fail(f"symlink boundary: {parent}")
    return path


def external_path(value):
    # Explicit roots may use OS aliases (/tmp, /var on macOS). Canonicalize
    # their parents once; descendants of the recorded root remain no-follow.
    path = Path(os.path.abspath(value))
    if path.is_symlink():
        fail(f"symlink root: {path}")
    return plain_path(path.parent.resolve() / path.name)


def secret(relative):
    parts = PurePosixPath(relative).parts
    for part in parts:
        lower = part.lower()
        if (lower.startswith(".env") or lower in {"settings.local.json", "credentials", "secrets", ".ssh"}
                or lower.endswith((".pem", ".key", ".p12", ".pfx"))
                or lower in {"credentials.json", "secrets.json", "auth.json", "config.local.json"}
                or lower.startswith((".gate-", "transcript")) or lower.endswith(".jsonl")):
            return True
    return False


def relative_path(relative):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        fail("path must be a nonempty repository-relative POSIX path")
    path = PurePosixPath(relative)
    if path.is_absolute() or path.as_posix() != relative or any(p in {".", ".."} for p in path.parts):
        fail(f"invalid relative path: {relative}")
    if any(part in SKIP_DIRS for part in path.parts) or secret(relative):
        fail(f"protected path: {relative}")
    return relative


def target_path(root, relative):
    relative_path(relative)
    path = plain_path(root / relative)
    for parent in path.parents:
        if parent == root:
            break
        if (parent / ".git").exists():
            fail(f"nested repository boundary: {relative}")
    if path.exists() and not path.is_file():
        fail(f"not a regular file: {relative}")
    return path


def fingerprint(path):
    if not path.exists():
        return None
    if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_nlink != 1:
        fail(f"not an exclusive regular file: {path}")
    return {"sha256": digest(path.read_bytes()), "mode": stat.S_IMODE(path.stat().st_mode)}


def candidate(relative):
    path = PurePosixPath(relative)
    return (path.suffix.lower() == ".md" or path.name in MANIFESTS
            or path.parts[0] in RUNTIME_DIRS
            or (path.parts[0] in {"scripts", "ci"} and path.suffix in {".sh", ".py", ".yml", ".yaml"}))


def inventory(root):
    entries = {}
    def inaccessible(error):
        path = Path(error.filename)
        relative = path.relative_to(root).as_posix()
        entries[relative] = {"status": "blocked", "reason": "directory enumeration unavailable"}
    # Do not follow symlinks, including submodules with their own .git entry.
    for directory, directories, files in os.walk(root, followlinks=False, onerror=inaccessible):
        base = Path(directory)
        for name in list(directories):
            path = base / name
            relative = path.relative_to(root).as_posix()
            reason = None
            if path.is_symlink():
                reason = "symlink boundary; not followed"
            elif name in SKIP_DIRS or secret(relative):
                reason = "private/runtime/generated directory; not read"
            elif (path / ".git").exists():
                reason = "nested repository/submodule; separate scope required"
            if reason:
                directories.remove(name)
                entries[relative] = {"status": "excluded", "reason": reason}
        for name in files:
            path = base / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
                entries[relative] = {"status": "excluded", "reason": "symlink/special file; not read"}
            elif secret(relative) or name == ".git":
                entries[relative] = {"status": "excluded", "reason": "private/runtime file; not read"}
            elif not candidate(relative):
                entries[relative] = {"status": "excluded", "reason": "application file; promote if workflow references it"}
            else:
                try:
                    data = path.read_bytes()
                    data.decode("utf-8")
                    entries[relative] = {"status": "unread", "before": fingerprint(path), "size": len(data)}
                except (OSError, UnicodeError, ValueError) as error:
                    entries[relative] = {"status": "blocked", "reason": type(error).__name__}
    return dict(sorted(entries.items()))


def session_path(value, root=None):
    path = external_path(value)
    if root is not None and (path == root or root in path.parents):
        fail("session must be outside the target repository")
    if path.exists():
        for child in path.rglob("*"):
            if child.is_symlink():
                fail("session contains a symlink")
    return path


def open_session(value):
    session = session_path(value)
    manifest = load(session / "inventory.json")
    root = plain_path(manifest["target"])
    session_path(session, root)
    if not root.is_dir():
        fail("target is unavailable")
    return session, manifest, root


@contextlib.contextmanager
def locked(session, root=None):
    with (session / "lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if root is None:
            yield
        else:
            runtime = plain_path(root / ".agent-runtime")
            runtime.mkdir(exist_ok=True)
            path = plain_path(runtime / "queue.lock")
            with path.open("a+") as queue_lock:
                fcntl.flock(queue_lock, fcntl.LOCK_EX)
                yield


def no_active_claims(root):
    directory = plain_path(root / ".agent-runtime/claims")
    if not directory.exists():
        return
    for path in directory.iterdir():
        plain_path(path)
        if path.suffix != ".json" or not path.is_file():
            fail("unrecognized claim state; stop workers and resolve ownership")
        value = load(path)
        expiry = value.get("expires_at") if isinstance(value, dict) else None
        if type(expiry) not in (int, float) or not math.isfinite(expiry):
            fail("invalid claim state; stop workers and resolve ownership")
        if expiry > time.time():
            fail("active workflow claims; owning workers must complete or release them")


def initial(target, session_value):
    root = external_path(target)
    if not root.is_dir():
        fail("target must be an existing directory")
    session = session_path(session_value, root)
    if session.exists() and any(session.iterdir()):
        fail("session already exists; reuse it or choose a new directory")
    session.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = {"schema": 1, "id": str(uuid.uuid4()), "target": str(root), "files": inventory(root)}
    save(session / "inventory.json", manifest)
    save(session / "plan.json", {"schema": 1, "id": manifest["id"], "target": str(root),
         "baseline": None, "decisions": [], "unresolved": [], "acceptance": [],
         "dispositions": [], "rule_map": [], "operations": []})
    return {"session": str(session), "id": manifest["id"], "inventory": manifest}


def coverage(session, manifest, root, path, action, evidence):
    relative_path(path)
    if (session / "approval.json").exists() or (session / "journal.json").exists():
        fail("sealed session coverage is immutable; start a new plan")
    entry = manifest["files"].get(path)
    if action == "include":
        location = target_path(root, path)
        if not location.is_file():
            fail("included file is missing")
        data = location.read_bytes()
        data.decode("utf-8")
        manifest["files"][path] = {"status": "unread", "before": fingerprint(location), "size": len(data)}
    elif action == "exclude":
        if not entry or entry["status"] not in {"unread", "read", "blocked"} or not evidence.strip():
            fail("exclusion requires an inventoried file and reason")
        entry.update(status="excluded", reason=evidence)
    else:
        if not entry or entry["status"] not in {"unread", "read"}:
            fail("include the file before attesting its full read")
        if fingerprint(target_path(root, path)) != entry["before"] or evidence != entry["before"]["sha256"]:
            fail("read attestation does not match the current revision")
        entry["status"] = "read"
    save(session / "inventory.json", manifest)
    return {"path": path, "status": manifest["files"][path]["status"]}


def portable_files(source):
    # The release registry declares portable assets. Directory recursion would
    # silently import source-project scripts/templates placed beside them.
    registry = load(target_path(source, ".lean/assets.json"))
    names = registry.get("files") if isinstance(registry, dict) else None
    if (not isinstance(registry, dict) or registry.get("schema") != 1 or not isinstance(names, list) or not names
            or not all(isinstance(name, str) for name in names) or len(set(names)) != len(names)
            or ".lean/assets.json" not in names):
        fail("invalid portable asset registry")
    for name in names:
        relative_path(name)
        if (name in {".lean/PROJECT.md", ".lean/config.json", ".lean/model-catalog.json"}
                or name.startswith(RECORD_DIRS)
                or not (name in {"AGENTS.md", "CLAUDE.md"} or name.startswith((".lean/", ".claude/", ".agents/skills/")))):
            fail(f"project-owned file cannot be a portable asset: {name}")
        if not target_path(source, name).is_file():
            fail(f"missing portable asset: {name}")
    return sorted(names)


def draft(session, manifest, root, baseline):
    if (session / "approval.json").exists() or (session / "journal.json").exists():
        fail("cannot replace a sealed plan")
    plan = load(session / "plan.json")
    if plan["operations"] or plan["baseline"]:
        fail("draft already populated; edit the existing plan")
    source = external_path(baseline)
    if source == root or root in source.parents or source in root.parents:
        fail("baseline and target must be separate repositories")
    session_path(session, source)
    sources = {}
    for name in portable_files(source):
        path = target_path(source, name)
        sources[name] = fingerprint(path)
        content = path.read_text()
        if name in {"AGENTS.md", "CLAUDE.md"}:
            content = content.split("## Project additions", 1)[0] + "## Project additions\n\n"
        before = fingerprint(target_path(root, name))
        after = {"sha256": digest(content.encode()), "mode": sources[name]["mode"]}
        if before != after:
            plan["operations"].append({"path": name, "before": before, "content": content,
                                       "mode": after["mode"], "reason": "install portable Lean baseline"})
    plan["baseline"] = {"root": str(source), "files": sources}
    plan["unresolved"] = ["Reconcile project rules, permissions/hooks/CI, facts/gate, mode/execution, records and document routes."]
    save(session / "plan.json", plan)
    return {"plan": str(session / "plan.json"), "operations": len(plan["operations"]), "status": "DRAFT"}


def after_state(operation):
    if operation.get("content") is None:
        return None
    return {"sha256": digest(operation["content"].encode()), "mode": operation["mode"]}


def record_migration_sources(manifest, plan):
    """Explicit, lossless foreign-format mappings; never a blanket record override."""
    mappings = plan.get("record_migrations", [])
    if not isinstance(mappings, list):
        fail("record_migrations must be a list")
    operations = {op["path"]: op for op in plan["operations"]}
    decisions = {item["id"] for item in plan["decisions"]}
    decision_records = {item["id"]: item for item in plan["decisions"]}
    mapping_sources = {item.get("source"): item for item in mappings if isinstance(item, dict)}
    allowed, archives = set(), set()
    for mapping in mappings:
        if not isinstance(mapping, dict) or mapping.get("format") != "casetodian-v1":
            fail("unsupported foreign record format")
        source, archive = mapping.get("source"), mapping.get("archive")
        relative_path(source)
        relative_path(archive)
        if source in allowed or archive in archives or mapping.get("decision") not in decisions:
            fail("record mapping needs unique paths and an accepted decision")
        original = manifest["files"].get(source, {})
        change, saved = operations.get(source), operations.get(archive)
        if (original.get("status") != "read" or not change or not saved
                or saved.get("before") is not None or not isinstance(saved.get("content"), str)
                or digest(saved["content"].encode()) != original.get("before", {}).get("sha256")
                or saved.get("mode") != original["before"]["mode"]):
            fail("foreign mapping must retain the exact original bytes and mode at a new archive path")
        if plan["operations"].index(saved) >= plan["operations"].index(change):
            fail("archive must be written before foreign record conversion")
        text = saved["content"]
        if mapping.get("kind") == "queue":
            old = json.loads(text)
            if (not isinstance(old, dict) or "tracker" in old or not old.get("workset")
                    or not old.get("task") or not old.get("objective")
                    or source != f'.agents/queue/items/{old.get("id")}.json'
                    or old.get("status") not in {"TODO", "BLOCKED", "DONE", "CANCELLED"}):
                fail("source is not a supported foreign queue record; existing Lean records must remain intact")
            if old["status"] == "CANCELLED":
                if archive != f'.agents/queue/retired/{old["id"]}.txt' or change.get("content") is not None:
                    fail("CANCELLED must become reserved cancellation history, never DONE")
            else:
                if not archive.startswith("docs/history/agent-workflow/") or not archive.endswith(".txt"):
                    fail("foreign originals require inert history paths")
                new = json.loads(change.get("content") or "null")
                expected = {"id": old["id"], "title": old.get("title"), "tracker": old["workset"],
                            "status": "READY" if old["status"] == "TODO" else old["status"],
                            "dependencies": old.get("dependencies"), "scopes": old.get("exclusiveScopes"),
                            "legacy": old}
                expected["evidence"] = None
                for source_key, destination in (("createdAt", "created_at"), ("completedAt", "completed_at")):
                    value = old.get(source_key) if source_key == "createdAt" else old.get("completion", {}).get(source_key)
                    if value is not None:
                        expected[destination] = value
                if old["status"] == "DONE":
                    evidence = old.get("completion", {}).get("evidence")
                    if not isinstance(evidence, list) or not evidence or not all(isinstance(x, str) and x.strip() for x in evidence):
                        fail("foreign DONE needs original completion evidence")
                    expected["evidence"] = "\n".join(evidence)
                if (not isinstance(new, dict) or set(new) - set(expected)
                        or any(new.get(key) != value for key, value in expected.items())):
                    fail("foreign queue mapping changes status, scope, dependencies or evidence")
        elif mapping.get("kind") == "evidence-history":
            parent = mapping_sources.get(mapping.get("parent"), {})
            evidence_id = re.match(r"TCK[0-9]{3,}(?=[_.-])", Path(source).name)
            parent_id = re.match(r"TCK[0-9]{3,}(?=[_.-])", Path(parent.get("source", "")).name)
            named_owner = evidence_id and parent_id and evidence_id[0] == parent_id[0]
            declared_owner = re.search(r"(?m)^Referenced by:.*`" + re.escape(parent.get("source", "")) + r"`", text)
            if (not source.startswith("docs/tracking/evidence/") or not source.endswith(".md")
                    or not parent_id or not (named_owner or (not evidence_id and declared_owner))
                    or parent.get("kind") != "tracker" or parent.get("format") != "casetodian-v1"
                    or not archive.startswith("docs/history/agent-workflow/") or not archive.endswith(".txt")
                    or change.get("content") is not None):
                fail("evidence history requires its mapped foreign tracker and exact inert archival, never proof rewriting")
        elif mapping.get("kind") == "tracker":
            # This foreign contract used a Tasks/queue-mapping section. A
            # canonical Lean record cannot opt out simply by adding a mapping.
            syntax_text = text.replace("\r\n", "\n")
            if (not source.startswith("docs/tracking/TCK") or not source.endswith(".md")
                    or not re.search(r"(?m)^## Tasks(?: and queue mapping)?\n", syntax_text)
                    or (re.search(r"(?m)^Status: (?:PLANNED|IN_PROGRESS|VALIDATING|REVIEWING|DONE|BLOCKED|FAILED)$", syntax_text)
                        and "## Evidence\n" in syntax_text)
                    or not archive.startswith("docs/history/agent-workflow/") or not archive.endswith(".txt")):
                fail("source is not a supported foreign tracker; existing Lean records must remain intact")
            status = mapping.get("status")
            legacy_states = re.findall(r"\b[Ss]tatus:\s*[*`]*([A-Z_]+)", text)
            translated = {"TODO": "PLANNED", "REVIEW": "REVIEWING"}
            states = {translated.get(value, value) for value in legacy_states}
            resolution = decision_records.get(mapping.get("status_decision"), {})
            resolved = resolution.get("record_statuses", {})
            explicit_resolution = isinstance(resolved, dict) and resolved.get(source) == status
            if (not states or (states != {status} and not explicit_resolution)
                    or status not in {"PLANNED", "IN_PROGRESS", "VALIDATING", "REVIEWING", "DONE", "BLOCKED", "FAILED"}):
                fail("foreign tracker status is ambiguous; record a resolved source decision before mapping")
            if mapping.get("historical_only") is True:
                history = decision_records.get(mapping.get("history_decision"), {}).get("archived_trackers", [])
                if (status != "DONE" or change.get("content") is not None
                        or not isinstance(history, list) or source not in history):
                    fail("history-only tracker requires closed state, source-specific accepted decision and active deletion")
                allowed.add(source)
                archives.add(archive)
                continue
            result = change.get("content")
            if (not isinstance(result, str) or re.findall(r"(?m)^Status: ([A-Z_]+)$", result) != [status]
                    or archive not in result):
                fail("tracker mapping must retain status and route to its original")
            evidence = mapping.get("evidence", [])
            evidence_text = text
            evidence_source = mapping.get("evidence_source", source)
            if evidence_source != source:
                approved_sources = resolution.get("record_evidence_sources", {})
                other = mapping_sources.get(evidence_source, {})
                other_entry = manifest["files"].get(evidence_source, {})
                other_archive = operations.get(other.get("archive"), {})
                if (not explicit_resolution or not isinstance(approved_sources, dict)
                        or approved_sources.get(source) != evidence_source or other.get("kind") != "tracker"
                        or other_entry.get("status") != "read" or not isinstance(other_archive.get("content"), str)
                        or digest(other_archive["content"].encode()) != other_entry.get("before", {}).get("sha256")):
                    fail("cross-tracker evidence requires explicit source-bound resolution decision")
                evidence_text = other_archive["content"]
            sections = re.findall(
                r"(?im)^## (?:Validation(?: plan and evidence| evidence| and acceptance| and handoff)?|Evidence(?: and review)?|Acceptance(?: and evidence| and validation)?|Execution snapshot|Impact and validation)\s*\n(.*?)(?=^## |\Z)",
                evidence_text, re.DOTALL)
            original_lines = {line.strip() for section in sections for line in section.splitlines() if line.strip()}
            if (not isinstance(evidence, list) or not all(isinstance(line, str) and line.strip() and line == line.strip()
                    and "\n" not in line and "\r" not in line and line in original_lines for line in evidence)
                    or (status == "DONE" and not evidence)):
                fail("DONE mapping requires original tracker evidence; never invent completion proof")
            evidence_sections = re.findall(r"(?m)^## Evidence\n(.*?)(?=^## |\Z)", result, re.DOTALL)
            normalized = "\n".join("- " + line for line in evidence)
            if (len(evidence_sections) > 1 or (evidence and evidence_sections != [normalized + "\n"])
                    or (not evidence and any(section.strip() for section in evidence_sections))):
                fail("normalized evidence must contain only selected original tracker evidence")

        else:
            fail("unsupported record mapping kind")
        allowed.add(source)
        archives.add(archive)
    return allowed


def validate_plan(manifest, plan):
    if (plan.get("schema") != 1 or plan.get("id") != manifest["id"] or plan.get("target") != manifest["target"]):
        fail("plan identity mismatch")
    if plan.get("unresolved") != []:
        fail("unresolved decisions block apply")
    if not isinstance(plan.get("acceptance"), list) or not plan["acceptance"] or not all(isinstance(x, str) and x.strip() for x in plan["acceptance"]):
        fail("observable acceptance criteria are required")
    for key in ("decisions", "dispositions", "rule_map", "operations"):
        if not isinstance(plan.get(key), list):
            fail(f"plan needs {key}")
    decisions = set()
    for item in plan["decisions"]:
        if (not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip() for k in ("id", "choice", "evidence"))
                or item["id"] in decisions):
            fail("decisions require unique ids, choices and user evidence")
        decisions.add(item["id"])
    dispositions = {}
    for item in plan["dispositions"]:
        if (not isinstance(item, dict) or item.get("action") not in {"keep", "replace", "migrate", "retire"}
                or not isinstance(item.get("reason"), str) or not item["reason"].strip()
                or item.get("path") in dispositions):
            fail("invalid or duplicate disposition")
        dispositions[item["path"]] = item
    for name, entry in manifest["files"].items():
        if entry["status"] == "excluded":
            continue
        if entry["status"] != "read":
            fail(f"full read is not attested: {name}")
        if name not in dispositions:
            fail(f"missing semantic disposition: {name}")
    for rule in plan["rule_map"]:
        if not isinstance(rule, dict) or not all(isinstance(rule.get(k), str) and rule[k].strip() for k in ("source", "rule", "destination", "reason")):
            fail("rule map needs source, rule, destination and reason")
        if rule["source"] not in dispositions:
            fail("rule source is outside reviewed coverage")
    names = set()
    for op in plan["operations"]:
        if not isinstance(op, dict):
            fail("invalid operation")
        name = relative_path(op.get("path"))
        if name in names or any(name.startswith(previous + "/") or previous.startswith(name + "/") for previous in names):
            fail("duplicate or overlapping operation paths")
        names.add(name)
        if not isinstance(op.get("reason"), str) or not op["reason"].strip():
            fail("operation needs a reason")
        before = op.get("before")
        entry = manifest["files"].get(name)
        if before is not None:
            if not entry or entry["status"] != "read" or before != entry["before"]:
                fail(f"operation baseline not fully read: {name}")
            if dispositions[name]["action"] == "keep":
                fail(f"operation contradicts keep disposition: {name}")
        elif entry and entry["status"] != "excluded":
            fail(f"operation incorrectly claims a new path: {name}")
        if "content" not in op or (op["content"] is not None and not isinstance(op["content"], str)):
            fail("operation content must be UTF-8 text or null for deletion")
        if op["content"] is not None and (type(op.get("mode")) is not int or not 0 <= op["mode"] <= 0o777):
            fail("operation mode must be ordinary permission bits")
        if op["content"] is None and before is None:
            fail("cannot delete an absent file")
    permitted = record_migration_sources(manifest, plan)
    for op in plan["operations"]:
        if (op["path"].startswith(RECORD_DIRS) and op["before"] is not None
                and op["path"] not in RECORD_SUPPORT and op["path"] not in permitted):
            fail("existing Lean records must remain intact; use owning workflow tooling")
    return plan


def check_baseline(plan):
    baseline = plan.get("baseline")
    if not isinstance(baseline, dict) or not isinstance(baseline.get("files"), dict) or not baseline["files"]:
        fail("a fingerprinted Lean baseline is required")
    root = plain_path(baseline["root"])
    if set(portable_files(root)) != set(baseline["files"]):
        fail("baseline file set changed; regenerate the plan")
    for name, before in baseline["files"].items():
        if fingerprint(target_path(root, name)) != before:
            fail(f"baseline revision changed: {name}")


def check_target(manifest, plan, root, journal=None):
    current = inventory(root)
    ops = {op["path"]: op for op in plan["operations"]}
    touched = set(journal.get("started", [])) if journal else set()
    # Excluded symlink/nested-repo boundaries can introduce active instructions
    # without becoming ordinary readable candidates. Keep discovery coverage
    # stable as well as the hashes of fully read files.
    def discovered(files):
        return {name for name, item in files.items()
                if not any(part in SKIP_DIRS for part in PurePosixPath(name).parts)
                and ((candidate(name) and not secret(name))
                     or "boundary" in item.get("reason", "")
                     or "separate scope" in item.get("reason", ""))}
    footprint = discovered(manifest["files"])
    for name in touched:
        if ops[name]["content"] is None:
            footprint.discard(name)
        elif candidate(name):
            footprint.add(name)
    discovered_now = discovered(current)
    deletions = {name for name in touched if ops[name]["content"] is None}
    if (discovered_now - footprint) - deletions or (footprint - discovered_now) - touched:
        fail("workflow file set changed; refresh audit before applying")
    expected = {name for name, item in manifest["files"].items() if item["status"] != "excluded" and candidate(name)}
    for name, op in ops.items():
        if name in touched:
            if op["content"] is None:
                expected.discard(name)
            elif candidate(name):
                expected.add(name)
    actual = {name for name, item in current.items() if item["status"] != "excluded"
              and manifest["files"].get(name, {}).get("status") != "excluded"}
    # A started deletion can still be at its pre-write state after a crash.
    allowed_missing = {name for name in touched if ops[name]["content"] is None}
    if (actual - expected) - allowed_missing or (expected - actual) - touched:
        fail("workflow file set changed; refresh audit before applying")
    for name, entry in manifest["files"].items():
        if entry["status"] == "excluded":
            # Explicit exclusions of regular text must also remain at the audited revision.
            if "before" in entry and fingerprint(target_path(root, name)) != entry["before"]:
                fail(f"excluded file changed: {name}")
            continue
        state = fingerprint(target_path(root, name))
        allowed = [entry["before"]]
        if name in touched:
            allowed.append(after_state(ops[name]))
        if state not in allowed:
            fail(f"audited revision changed: {name}")
    for name, op in ops.items():
        state = fingerprint(target_path(root, name))
        allowed = [op["before"]]
        if name in touched:
            allowed.append(after_state(op))
        if state not in allowed:
            fail(f"operation precondition changed: {name}")


def stage(session, manifest, root):
    if (session / "approval.json").exists() or (session / "journal.json").exists():
        fail("stage before sealing; an approved session is immutable")
    plan = validate_plan(manifest, load(session / "plan.json"))
    check_baseline(plan)
    check_target(manifest, plan, root)
    directory = plain_path(session / "staging")
    # Build privately, publish only a complete tree and content manifest.
    temporary = Path(tempfile.mkdtemp(prefix="stage-", dir=session))
    try:
        for name, item in manifest["files"].items():
            if item["status"] == "read":
                original = target_path(root, name)
                atomic(target_path(temporary, name), original.read_bytes(), item["before"]["mode"])
        for op in plan["operations"]:
            path = target_path(temporary, op["path"])
            if op["content"] is None:
                if path.exists():
                    remove_file(path)
            else:
                atomic(path, op["content"].encode(), op["mode"])
        names = {name for name, item in manifest["files"].items() if item["status"] == "read"}
        for op in plan["operations"]:
            if op["content"] is None:
                names.discard(op["path"])
            else:
                names.add(op["path"])
        files = {name: fingerprint(target_path(temporary, name)) for name in sorted(names)}
        check_target(manifest, plan, root)
        if directory.exists():
            # Only this disposable, private staging tree is regenerated. Target
            # originals and recovery snapshots are never removed here.
            shutil.rmtree(directory)
        os.replace(temporary, directory)
        save(session / "staged.json", {"plan_sha256": json_digest(plan), "inventory_sha256": json_digest(manifest),
                                      "files": files, "validation": None})
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return {"status": "STAGED", "directory": str(directory), "files": len(files),
            "validation": "run safe deterministic workflow checks, then stage-check with evidence"}


def check_stage(session, manifest, plan):
    staged = load(session / "staged.json")
    if staged["plan_sha256"] != json_digest(plan) or staged["inventory_sha256"] != json_digest(manifest):
        fail("staging no longer matches the plan or coverage")
    directory = plain_path(session / "staging")
    if not directory.is_dir():
        fail("staging is unavailable")
    for name, expected in staged["files"].items():
        if fingerprint(target_path(directory, name)) != expected:
            fail(f"staged result changed: {name}")
    current = inventory(directory)
    # A controlled staging tree has no pre-existing excluded app/private files.
    # Reject added private settings by name without reading their contents.
    extras = {name for name in current
              if not any(part in SKIP_DIRS for part in PurePosixPath(name).parts)} - set(staged["files"])
    if extras:
        fail("staging has unreviewed workflow files")
    if plan.get("record_migrations"):
        # Run trusted Lean validation, never target-imported scripts or hooks.
        spec = importlib.util.spec_from_file_location("takeover_record_checks", Path(__file__).with_name("workflow.py"))
        workflow = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(workflow)
        workflow.validate_records(directory, "full", include_retained=True)
    return staged


def stage_check(session, manifest, root, evidence):
    if not evidence.strip():
        fail("record passed deterministic staging checks and their limits")
    if (session / "approval.json").exists():
        fail("staging evidence is immutable after sealing")
    plan = validate_plan(manifest, load(session / "plan.json"))
    check_baseline(plan)
    check_target(manifest, plan, root)
    staged = check_stage(session, manifest, plan)
    staged["validation"] = evidence
    save(session / "staged.json", staged)
    return {"status": "STAGE_CHECKED", "evidence": evidence}


def seal(session, manifest, root, evidence):
    if not evidence.strip():
        fail("record the user's matching plan approval")
    if (session / "journal.json").exists():
        fail("an applied session cannot be resealed")
    plan = validate_plan(manifest, load(session / "plan.json"))
    check_baseline(plan)
    check_target(manifest, plan, root)
    staged = check_stage(session, manifest, plan)
    if not isinstance(staged["validation"], str) or not staged["validation"].strip():
        fail("deterministic staging validation is required before sealing")
    receipt = {"plan_sha256": json_digest(plan), "inventory_sha256": json_digest(manifest),
               "staged_sha256": json_digest(staged), "evidence": evidence}
    save(session / "approval.json", receipt)
    return receipt


def approved(session, manifest):
    plan = validate_plan(manifest, load(session / "plan.json"))
    receipt = load(session / "approval.json")
    if receipt.get("plan_sha256") != json_digest(plan) or receipt.get("inventory_sha256") != json_digest(manifest):
        fail("approved plan or coverage changed")
    if receipt.get("staged_sha256") != json_digest(load(session / "staged.json")):
        fail("approved staging evidence changed")
    return plan, receipt


def backups(session, plan):
    snapshots = []
    for op in plan["operations"]:
        snapshots.append({"path": op["path"], "before": op["before"], "data": None})
    return snapshots


def restore_data(snapshot):
    if snapshot["before"] is None:
        if snapshot["data"] is not None:
            fail("invalid absent-file snapshot")
        return None
    data = base64.b64decode(snapshot["data"], validate=True)
    if digest(data) != snapshot["before"]["sha256"]:
        fail("snapshot checksum mismatch")
    return data


def remove_file(path):
    path.unlink()
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def apply_plan(session, manifest, root, receipt_hash):
    plan, receipt = approved(session, manifest)
    if receipt_hash != receipt["plan_sha256"]:
        fail("supply the sealed plan hash")
    journal_path = session / "journal.json"
    journal = load(journal_path) if journal_path.exists() else None
    if journal and journal["state"] in {"ROLLING_BACK", "ROLLED_BACK"}:
        fail("rollback has begun; finish rollback or start a new session")
    no_active_claims(root)
    check_baseline(plan)
    check_stage(session, manifest, plan)
    check_target(manifest, plan, root, journal)
    if journal is None:
        snapshots = backups(session, plan)
        directories = set()
        for snapshot in snapshots:
            path = target_path(root, snapshot["path"])
            if snapshot["before"] is not None:
                snapshot["data"] = base64.b64encode(path.read_bytes()).decode()
            for parent in path.parents:
                if parent == root:
                    break
                if not parent.exists():
                    directories.add(parent.relative_to(root).as_posix())
        journal = {"state": "APPLYING", "plan_sha256": receipt_hash, "started": [], "completed": [],
                   "snapshots": snapshots, "directories": sorted(directories), "restored": []}
        save(journal_path, journal)
    if journal["plan_sha256"] != receipt_hash:
        fail("journal does not match the approved plan")
    for snapshot in journal["snapshots"]:
        restore_data(snapshot)
    for op in plan["operations"]:
        name = op["path"]
        path = target_path(root, name)
        state = fingerprint(path)
        if name in journal["completed"]:
            if state != after_state(op):
                fail(f"completed operation changed: {name}")
            continue
        if name not in journal["started"]:
            if state != op["before"]:
                fail(f"operation changed before writing: {name}")
            journal["started"].append(name)
            save(journal_path, journal)
        if state != after_state(op):
            if state != op["before"]:
                fail(f"interrupted operation changed: {name}")
            if op["content"] is None:
                remove_file(path)
            else:
                atomic(path, op["content"].encode(), op["mode"])
        journal["completed"].append(name)
        save(journal_path, journal)
    journal["state"] = "APPLIED"
    save(journal_path, journal)
    return {"status": "APPLIED", "operations": len(plan["operations"]), "validation": "run target gate and independent review before DONE"}


def rollback(session, manifest, root):
    plan, receipt = approved(session, manifest)
    journal_path = session / "journal.json"
    journal = load(journal_path)
    if journal["plan_sha256"] != receipt["plan_sha256"]:
        fail("journal identity mismatch")
    no_active_claims(root)
    ops = {op["path"]: op for op in plan["operations"]}
    snapshots = {item["path"]: item for item in journal["snapshots"]}
    # Preflight every affected file before any restoration. Subsequent edits block rollback.
    for name in journal["started"]:
        snapshot = snapshots[name]
        restore_data(snapshot)
        state = fingerprint(target_path(root, name))
        allowed = [snapshot["before"]] if name in journal["restored"] else [snapshot["before"], after_state(ops[name])]
        if state not in allowed:
            fail(f"rollback would overwrite subsequent edits: {name}")
    journal["state"] = "ROLLING_BACK"
    save(journal_path, journal)
    for name in reversed(journal["started"]):
        if name in journal["restored"]:
            continue
        snapshot = snapshots[name]
        path = target_path(root, name)
        if fingerprint(path) != snapshot["before"]:
            if snapshot["before"] is None:
                remove_file(path)
            else:
                atomic(path, restore_data(snapshot), snapshot["before"]["mode"])
        journal["restored"].append(name)
        save(journal_path, journal)
    for name in sorted(journal["directories"], key=lambda value: len(PurePosixPath(value).parts), reverse=True):
        path = plain_path(root / name)
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    journal["state"] = "ROLLED_BACK"
    save(journal_path, journal)
    return {"status": "ROLLED_BACK", "restored": len(journal["restored"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("inventory", help="metadata/fingerprints only; does not attest a full read")
    init.add_argument("target")
    init.add_argument("--session", required=True)
    for name in ("include", "exclude", "cover"):
        command = commands.add_parser(name)
        command.add_argument("--session", required=True)
        command.add_argument("--path", required=True)
        command.add_argument("--evidence", default="")
    for name in ("draft", "check", "stage", "stage-check", "seal", "apply", "resume", "rollback", "status"):
        command = commands.add_parser(name)
        command.add_argument("--session", required=True)
        if name == "draft":
            command.add_argument("--baseline", required=True)
        if name in {"seal", "stage-check"}:
            command.add_argument("--evidence", required=True)
        if name in {"apply", "resume"}:
            command.add_argument("--approval", required=True)
    args = parser.parse_args()
    try:
        if args.command == "inventory":
            result = initial(args.target, args.session)
        else:
            session, manifest, root = open_session(args.session)
            mutation = args.command in {"apply", "resume", "rollback"}
            with locked(session, root if mutation else None):
                # Reload after acquiring the session lock.
                manifest = load(session / "inventory.json")
                if args.command in {"include", "exclude", "cover"}:
                    result = coverage(session, manifest, root, args.path, args.command, args.evidence)
                elif args.command == "draft":
                    result = draft(session, manifest, root, args.baseline)
                elif args.command == "check":
                    plan = validate_plan(manifest, load(session / "plan.json"))
                    check_baseline(plan)
                    check_target(manifest, plan, root)
                    result = {"status": "READY_FOR_APPROVAL", "plan_sha256": json_digest(plan)}
                elif args.command == "stage":
                    result = stage(session, manifest, root)
                elif args.command == "stage-check":
                    result = stage_check(session, manifest, root, args.evidence)
                elif args.command == "seal":
                    result = seal(session, manifest, root, args.evidence)
                elif args.command in {"apply", "resume"}:
                    result = apply_plan(session, manifest, root, args.approval)
                elif args.command == "rollback":
                    result = rollback(session, manifest, root)
                else:
                    journal = load(session / "journal.json") if (session / "journal.json").exists() else None
                    result = {"id": manifest["id"], "target": str(root),
                              "state": journal["state"] if journal else "PREVIEW",
                              "started": journal["started"] if journal else [],
                              "completed": journal["completed"] if journal else [],
                              "restored": journal["restored"] if journal else []}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
