#!/usr/bin/env python3
"""Acquire pinned Lean releases outside the target; never apply or run source code."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True
import takeover

DEFAULT_SOURCE = "https://github.com/aussadawut-dev/lean-workflow-agent-by-asdw.git"
VERSION = re.compile(r"v?(\d+)\.(\d+)\.(\d+)\Z")


def git(*args):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull,
                             "-c", "protocol.ext.allow=never", *args],
                            env=env, text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError("Git acquisition failed: " + result.stderr.strip())
    return result.stdout.strip()


def remote_refs(source):
    if source.startswith("-") or "\n" in source:
        raise ValueError("invalid source")
    refs = {}
    for line in git("ls-remote", "--heads", "--tags", "--", source).splitlines():
        sha, name = line.split("\t", 1)
        refs[name] = sha
    return refs


def select(refs, requested=None):
    if requested is None:
        tags = [(tuple(map(int, VERSION.fullmatch(name[10:]).groups())), name)
                for name in refs if name.startswith("refs/tags/") and VERSION.fullmatch(name[10:])]
        if not tags:
            raise ValueError("no stable semantic-version tag; specify --ref deliberately")
        requested = max(tags)[1]
    if re.fullmatch(r"[0-9a-f]{40}", requested):
        return requested, requested
    candidates = [requested] if requested.startswith("refs/") else ["refs/tags/" + requested, "refs/heads/" + requested]
    matches = [name for name in candidates if name in refs and not name.endswith("^{}")]
    if len(matches) != 1:
        raise ValueError("unknown or ambiguous ref; use a full refs/tags/ or refs/heads/ name")
    name = matches[0]
    return name, refs.get(name + "^{}", refs[name])


def checkout(source, sha, destination):
    git("clone", "--no-checkout", "--", source, str(destination))
    git("-C", str(destination), "fetch", "--no-tags", "origin", sha)
    git("-C", str(destination), "checkout", "--detach", sha)
    if git("-C", str(destination), "rev-parse", "HEAD") != sha:
        raise ValueError("checkout revision mismatch")


def version(root):
    path = takeover.target_path(root, "AGENTS.md")
    text = path.read_text()
    match = re.search(r"Lean Workflow Baseline\s+(\d+\.\d+\.\d+)\b", text)
    if not match:
        raise ValueError("cannot identify Lean version from AGENTS.md")
    return match.group(1)


def prepare(target_value, workspace_value, source=DEFAULT_SOURCE, requested=None, installed_ref=None):
    target = takeover.external_path(target_value)
    current_version = version(target)
    workspace = takeover.session_path(workspace_value, target)
    # Also keep artifacts out of an enclosing superproject/Git metadata.
    for parent in (workspace, *workspace.parents):
        if (parent / ".git").exists() or parent.name == ".git":
            raise ValueError("workspace must be outside every Git checkout and Git metadata")
    if workspace.exists():
        raise ValueError("workspace already exists; retain it and choose a fresh path")
    refs = remote_refs(source)
    ref, sha = select(refs, requested)
    workspace.mkdir(parents=True, mode=0o700)
    baseline = workspace / "source"
    checkout(source, sha, baseline)
    new_version = version(baseline)
    if tuple(map(int, new_version.split("."))) < tuple(map(int, current_version.split("."))):
        raise ValueError("source is older than installed Lean; downgrade requires a separate accepted scope")
    if ref.startswith("refs/tags/"):
        tag_version = VERSION.fullmatch(ref[10:])
        if tag_version and tuple(map(int, tag_version.groups())) != tuple(map(int, new_version.split("."))):
            raise ValueError("tag and AGENTS baseline versions disagree")
    # Validate with the installed trusted tooling, never remote Python imports.
    assets = takeover.portable_files(baseline)
    previous = None
    metadata_path = takeover.target_path(target, ".lean/upstream.json")
    if installed_ref is None and metadata_path.exists():
        metadata = takeover.load(metadata_path)
        if not isinstance(metadata, dict):
            raise ValueError("invalid upstream provenance")
        if metadata.get("source") == source:
            installed_ref = metadata.get("commit")
            if metadata.get("schema") != 1 or not isinstance(installed_ref, str) or not re.fullmatch(r"[0-9a-f]{40}", installed_ref):
                raise ValueError("invalid upstream provenance commit/schema")
    if installed_ref:
        old_ref, old_sha = select(refs, installed_ref)
        previous = workspace / "previous"
        checkout(source, old_sha, previous)
        if version(previous) != current_version:
            raise ValueError("installed reference does not match installed baseline version")
        previous = {"root": str(previous), "ref": old_ref, "commit": old_sha}
    comparison = []
    for name in assets:
        incoming = takeover.fingerprint(takeover.target_path(baseline, name))
        local = takeover.fingerprint(takeover.target_path(target, name))
        base = takeover.fingerprint(takeover.target_path(Path(previous["root"]), name)) if previous else None
        comparison.append({"path": name, "local": local, "incoming": incoming, "base": base,
                           "identical": local == incoming})
    report = {"schema": 1, "target": str(target), "source": source, "ref": ref, "commit": sha,
              "installed_version": current_version, "incoming_version": new_version,
              "baseline": str(baseline), "previous": previous,
              "migration_session": str(workspace / "migration"), "comparison": comparison,
              "status": "INSPECT", "provenance": {"schema": 1, "source": source, "ref": ref, "commit": sha}}
    takeover.save(workspace / "release.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--ref")
    parser.add_argument("--installed-ref")
    args = parser.parse_args()
    try:
        report = prepare(args.target, args.workspace, args.source, args.ref, args.installed_ref)
        print(json.dumps(report, indent=2))
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
