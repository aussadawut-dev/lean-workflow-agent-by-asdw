"""Categorised tests with impact selection: run only what a change can affect.

Tests live in .lean/tests/<category>/test_*.py (unit, hooks, e2e). `.lean/tests/impact.json`
maps changed paths to test files or categories. Only paths in its workflow `scope` can affect
these tests (a project's own application code cannot); paths listed as lint-only (documentation,
project/target work records and settings) run lint only when no rule matches, a changed test file
runs itself, and an in-scope path no rule covers runs everything, so selection never silently skips.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

from .progress import render
from .util import LeanError, read_json

CATEGORIES = ("unit", "hooks", "e2e")
TESTS = ".lean/tests"
FAILED_NAME = re.compile(r"(?:FAIL|ERROR): \S")
# Work records: trackers and queue items, of the workspace and of each target. A gate check scoped
# with `lean gate scope` is skipped when the change touches nothing else.
RECORDS = ("docs/tracking/*", ".agents/queue/*", ".lean/targets/*/docs/tracking/*", ".lean/targets/*/.agents/queue/*")
SCOPE_ENV = "LEAN_GATE_SCOPE"


def all_files(root, categories=CATEGORIES):
    base = Path(root) / TESTS
    return [f"{category}/{path.name}" for category in categories
            for path in sorted((base / category).glob("test_*.py"))]


def impact(root):
    data = read_json(Path(root) / TESTS / "impact.json")
    if (not isinstance(data, dict) or not isinstance(data.get("lint_only"), list)
            or not isinstance(data.get("scope"), list) or not isinstance(data.get("rules"), list)):
        raise LeanError("impact.json needs \"scope\" and \"lint_only\" globs and \"rules\"")
    for rule in data["rules"]:
        if (not isinstance(rule, dict) or not isinstance(rule.get("paths"), list)
                or not isinstance(rule.get("tests"), list) or not rule["paths"] or not rule["tests"]):
            raise LeanError(f"impact rule needs paths and tests: {rule!r:.80}")
    return data


def smoke(root):
    """The short `smoke` list from impact.json: what a project using Lean runs of Lean's own tests."""
    listed = impact(root).get("smoke", [])
    if not isinstance(listed, list) or not all(isinstance(name, str) for name in listed):
        raise LeanError("impact.json \"smoke\" must be a list of test files")
    available = set(all_files(root))
    for name in listed:
        if name not in available:
            raise LeanError(f"impact.json smoke names a missing test: {name}")
    return list(dict.fromkeys(listed))


def names(output):
    return {line for line in output.split("\0") if line}


def changed(root, base=None):
    """Paths changed in the working tree, the index, untracked files and unpushed commits."""
    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
        if result.returncode:
            raise LeanError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout
    found = names(git("ls-files", "--others", "--exclude-standard", "-z"))
    if subprocess.run(["git", "-C", str(root), "rev-parse", "-q", "--verify", "HEAD"],
                      capture_output=True).returncode:
        return sorted(found | names(git("ls-files", "--cached", "-z")))
    found |= names(git("diff", "--name-only", "--no-renames", "-z", "HEAD"))
    found |= names(git("diff", "--cached", "--name-only", "--no-renames", "-z", "HEAD"))
    if base is None:
        # Commits no remote branch has yet: CI has not run on them. Without a remote, nothing has.
        unpushed = git("rev-list", "HEAD", "--not", "--remotes").split()
        if unpushed and not git("remote").strip():
            return sorted(found | names(git("ls-files", "--cached", "-z")))
        if unpushed:
            parent = subprocess.run(["git", "-C", str(root), "rev-parse", "-q", "--verify", unpushed[-1] + "^"],
                                    capture_output=True, text=True)
            base = parent.stdout.strip() if parent.returncode == 0 else None
            if base is None:
                return sorted(found | names(git("ls-files", "--cached", "-z")))
    if base:
        found |= names(git("diff", "--name-only", "--no-renames", "-z", base, "HEAD"))
    return sorted(found)


def matches(path, patterns):
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def select(root, paths):
    """(test files, reason) for changed paths; an empty list with reason 'lint' means docs only."""
    data = impact(root)
    if not paths:
        return [], "no changes"
    paths = [path for path in paths if matches(path, data["scope"])]
    if not paths:
        return [], "no workflow changes"
    available = set(all_files(root))
    chosen, uncovered, counted = set(), [], 0
    for path in paths:
        hit = False
        own = path[len(TESTS) + 1:] if path.startswith(TESTS + "/") else ""
        if own in available:
            chosen.add(own)  # A changed test file runs itself, plus whatever its rules add.
            hit = True
        for rule in data["rules"]:
            if matches(path, rule["paths"]):
                hit = True
                for test in rule["tests"]:
                    if test in CATEGORIES:
                        chosen.update(all_files(root, (test,)))
                    elif test in available:
                        chosen.add(test)
                    else:
                        raise LeanError(f"impact.json names a missing test: {test}")
        if hit:
            counted += 1
        elif not matches(path, data["lint_only"]):
            uncovered.append(path)  # Rules win; lint-only covers only what no rule names.
    if uncovered:
        return sorted(available), "no impact rule covers: " + ", ".join(uncovered[:5])
    if not counted:
        return [], "lint"
    return sorted(chosen), f"{counted} changed path(s)"


def named(root, names):
    """Test files for names given on the command line: a tier (`e2e`), `hooks/test_x.py`, or the same path
    from the repository root (`.lean/tests/hooks/test_x.py`); raises LeanError for anything else."""
    files = []
    for name in names:
        if name in CATEGORIES:
            files += all_files(root, (name,))
            continue
        relative = name.removeprefix("./").removeprefix(TESTS + "/")
        category, _, filename = relative.partition("/")
        if (category not in CATEGORIES or "/" in filename or not re.fullmatch(r"test_\w+\.py", filename)
                or not (Path(root) / TESTS / relative).is_file()):
            raise LeanError(f"no such test file: {name} (use a tier {', '.join(CATEGORIES)} or "
                            "<tier>/test_<name>.py)")
        files.append(relative)
    return sorted(set(files))


def run_files(root, files, jobs=None, show=None, reason=""):
    """Run each test file in its own process, several at a time; return the number of failures."""
    root = Path(root)
    show = show or (lambda text: print(text, flush=True))
    base = root / TESTS
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    jobs = jobs or os.cpu_count() or 1

    def one(name):
        category, filename = name.split("/", 1)
        command = [sys.executable, "-m", "unittest", "discover", "-s", str(base / category), "-p", filename,
                   "-t", str(base / category)]
        began = time.monotonic()
        result = subprocess.run(command, cwd=root, env=environment, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return name, result.returncode, time.monotonic() - began, result.stdout

    failures, done = [], 0
    began = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, min(jobs, len(files)))) as pool:
        futures = [pool.submit(one, name) for name in files]
        for future in as_completed(futures):
            name, code, seconds, output = future.result()
            done += 1
            verdict = "ok" if code == 0 else "FAIL"
            show(f"Tests {render(done / len(files), width=20)} {done}/{len(files)} {name} {verdict} ({seconds:.1f}s)")
            if code:
                failures.append((name, output))
    for name, output in failures:
        show(f"\n===== {name} =====\n" + "\n".join(output.splitlines()[-60:]))
    seconds = time.monotonic() - began
    named = "; failed: " + ", ".join(sorted(name for name, _ in failures)) if failures else ""
    show(f"{len(files) - len(failures)}/{len(files)} test files passed in {seconds:.1f}s{named}")
    from . import activity
    activity.record(root, "test", files=len(files), failed=len(failures), seconds=round(seconds, 1), selection=reason,
                    failures=[name for name, _ in failures] or None)
    return len(failures)


def scope_paths(cwd):
    """Every path changed since the remote default branch, or None when that branch is unknown.

    Unlike changed(), pushed commits still count until they reach the default branch (a pushed
    feature branch is not validated), and submodule changes count whatever the ignore settings
    (untracked files inside an application submodule are application changes).
    """
    def git(*args):
        return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                              check=True).stdout
    top = git("rev-parse", "--show-toplevel").strip()
    cwd = top
    base = None
    for remote in git("remote").split():
        for ref in (f"refs/remotes/{remote}/HEAD", f"refs/remotes/{remote}/main", f"refs/remotes/{remote}/master"):
            if subprocess.run(["git", "-C", top, "rev-parse", "-q", "--verify", ref + "^{commit}"],
                              capture_output=True).returncode == 0:
                base = ref
                break
        if base:
            break
    if base is None:
        return None
    merge = git("merge-base", base, "HEAD").strip()
    found = names(git("diff", "--name-only", "--no-renames", "-z", "--ignore-submodules=none", merge))
    found |= names(git("diff", "--cached", "--name-only", "--no-renames", "-z", "--ignore-submodules=none", merge))
    found |= names(git("ls-files", "--others", "--exclude-standard", "-z"))
    return sorted(found)


def scope_skip(cwd, only=(), always=()):
    """Why a scoped gate check may be skipped, or None to run it.

    The change is scope_paths() of the repository holding `cwd`. The check is skipped only when every
    changed path is a work record (RECORDS) or matches `only`, and none matches `always`. Anything
    undecidable runs it: LEAN_GATE_SCOPE=full, no change, no repository, no remote default branch
    or a Git error.
    """
    if os.environ.get(SCOPE_ENV) == "full":
        return None
    try:
        paths = scope_paths(cwd)
    except (OSError, subprocess.CalledProcessError, LeanError):
        return None
    if not paths:
        return None
    patterns = RECORDS + tuple(only)
    if any(matches(path, always) or not matches(path, patterns) for path in paths):
        return None
    return f"{len(paths)} changed path(s) are work records only"


def scoped(cwd, command, only=(), always=()):
    """Run one gate check unless scope_skip() allows skipping it; return its exit status."""
    if not command:
        raise LeanError("gate scope needs a command after --")
    reason = scope_skip(cwd, only, always)
    if reason:
        print(f"gate scope: skipped {shlex.join(command)}; {reason} ({SCOPE_ENV}=full runs it)", flush=True)
        return 0
    try:
        return subprocess.run(command, cwd=cwd).returncode
    except FileNotFoundError:
        print(f"gate scope: command not found: {command[0]}", file=sys.stderr)
        return 127
    except OSError as error:
        print(f"gate scope: cannot run {command[0]}: {error}", file=sys.stderr)
        return 126
