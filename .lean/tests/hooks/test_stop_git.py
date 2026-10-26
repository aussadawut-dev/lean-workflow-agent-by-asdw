"""Stop's Git queries: fewer processes, the same digests, changed-path sets and refusals.

Expected values come from an oracle that runs the Git commands the digests were defined with
(`rev-parse HEAD`, `ls-files --stage`, `ls-files --cached --others`, `ls-files --others`,
`rev-parse -q --verify HEAD`, the two `diff` calls), never from the code under test.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import commit, configured, install  # noqa: E402
from lean import evidence, util  # noqa: E402

GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}


def run(root, *args, check=True):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=check,
                          env=dict(os.environ, **GIT_ENV))


# The oracle: the digest and changed-path definitions as separate Git calls.
def oracle_entries(root):
    out = run(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout
    found = []
    for raw in sorted(set(out.split(b"\0")) - {b""}):
        name = os.fsdecode(raw)
        path = root / name
        if any((root / parent).is_symlink() for parent in Path(name).parents):
            continue
        if path.is_symlink():
            value = {"link": os.readlink(path)}
        elif path.is_file():
            value = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "mode": path.stat().st_mode & 0o777}
        elif path.is_dir():
            value = {"submodule": oracle_state(path)} if (path / ".git").exists() else {"directory": True}
        else:
            value = None
        found.append([name, value])
    return found


def oracle_state(root):
    head = run(root, "rev-parse", "HEAD", check=False).stdout.decode().strip()
    controls = evidence.controls(root)
    stage = run(root, "ls-files", "--stage", "-z").stdout.hex()
    return hashlib.sha256(json.dumps([head, controls, stage, oracle_entries(root)], ensure_ascii=True,
                                     sort_keys=True).encode()).hexdigest()


def oracle_changed(root, base):
    def names(*args):
        return set(run(root, *args).stdout.split(b"\0"))
    found = names("ls-files", "--others", "--exclude-standard", "-z")
    if run(root, "rev-parse", "-q", "--verify", "HEAD", check=False).returncode:
        found |= names("ls-files", "--cached", "-z")
    else:
        found |= names("diff", "--relative", "--name-only", "--no-renames", "-z", "HEAD")
        found |= names("diff", "--cached", "--relative", "--name-only", "--no-renames", "-z", "HEAD")
        if base == "":
            found |= names("ls-tree", "-r", "--name-only", "-z", "HEAD")
        elif base and run(root, "cat-file", "-e", base + "^{commit}", check=False).returncode == 0:
            found |= names("diff", "--relative", "--name-only", "--no-renames", "-z", base, "HEAD")
    return sorted(os.fsdecode(name) for name in found - {b""})


def oracle_in_git(root):
    return run(root, "rev-parse", "--is-inside-work-tree", check=False).returncode == 0


def oracle_head(root):
    result = run(root, "rev-parse", "-q", "--verify", "HEAD", check=False)
    return result.stdout.decode().strip() if result.returncode == 0 else ""


def write(path, data=b"x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class Fixtures:
    """Repositories covering the edge cases a shared Git query could get wrong."""

    def __init__(self, base):
        self.base = Path(base)

    def repo(self, name):
        root = self.base / name
        root.mkdir()
        run(root, "init", "-q")
        return root

    def all(self):
        made = {}
        for name in [name for name in dir(self) if name.startswith("make_")]:
            made[name[5:]] = getattr(self, name)()
        return made

    def make_unborn(self):
        root = self.repo("unborn")
        write(root / "staged.txt")
        write(root / "untracked file.txt")
        run(root, "add", "staged.txt")
        return [(root, base) for base in (None, "")]

    def make_unborn_head_file(self):
        root = self.repo("unborn head file")
        write(root / "HEAD", b"not a ref\n")  # `rev-parse HEAD` then exits 0 and prints "HEAD".
        return [(root, None)]

    def make_awkward_names(self):
        root = self.repo("awkward names")
        names = ["with space.txt", "new\nline.txt", "tab\there.txt", "ünïcode.txt", "? fake other", "H fake cached",
                 "100644 " + "0" * 40 + " 0\tspoof", "-dash", "HEAD"]
        for name in names:
            write(root / name)
        try:
            write(root / os.fsdecode(b"bad-\xff-utf8.txt"))
        except OSError:
            pass  # APFS refuses names that are not UTF-8.
        run(root, "config", "core.quotepath", "true")
        commit(root)
        for name in names[:4]:
            write(root / name, b"changed\n")
        write(root / "? untracked other")
        write(root / "M untracked", b"y\n")
        write(root / "new\nuntracked")
        return [(root, None)]

    def make_deleted_and_reverted(self):
        root = self.repo("deleted and reverted")
        for name in ("deleted.txt", "staged-deleted.txt", "unindexed.txt", "reverted.txt", "mode.sh", "ita.txt"):
            write(root / name)
        os.symlink("deleted.txt", root / "link")
        commit(root)
        first = run(root, "rev-parse", "HEAD").stdout.decode().strip()
        write(root / "later.txt")
        commit(root, "later")
        write(root / "later.txt", b"changed\n")
        (root / "deleted.txt").unlink()
        run(root, "rm", "-q", "staged-deleted.txt")
        run(root, "rm", "-q", "--cached", "unindexed.txt")
        write(root / "reverted.txt", b"staged\n")
        run(root, "add", "reverted.txt")
        write(root / "reverted.txt")  # Staged then reverted: only the index differs from HEAD.
        (root / "mode.sh").chmod(0o755)
        write(root / "intent.txt")
        run(root, "add", "-N", "intent.txt")
        (root / "link").unlink()
        os.symlink("reverted.txt", root / "link")
        return [(root, base) for base in (None, "", first, "0" * 40, "not-a-commit")]

    def make_ignored(self):
        root = self.repo("ignored")
        write(root / ".gitignore", b"*.log\nbuild/\n")
        write(root / "tracked.log")
        run(root, "add", "-f", "tracked.log")
        commit(root)
        write(root / "tracked.log", b"changed\n")  # Ignored but tracked: still visible and changed.
        write(root / "untracked.log")
        write(root / "build/out.bin")
        write(root / "kept.txt")
        return [(root, None)]

    def make_gitlinks(self):
        root = self.repo("gitlinks")
        sub = self.repo("gitlinks/sub")
        write(sub / "inner.txt")
        commit(sub)
        run(root, "add", "sub")  # An embedded repository is indexed as a gitlink.
        commit(root)
        write(sub / "inner.txt", b"dirty\n")
        nested = self.repo("gitlinks/nested")  # An untracked nested repository lists as "nested/".
        write(nested / "a.txt")
        return [(root, None)]

    def make_conflict_and_skip_worktree(self):
        root = self.repo("conflict")
        write(root / "both.txt", b"base\n")
        write(root / "skipped.txt")
        commit(root)
        run(root, "checkout", "-q", "-b", "other")
        write(root / "both.txt", b"other\n")
        commit(root, "other")
        run(root, "checkout", "-q", "-")
        write(root / "both.txt", b"main\n")
        commit(root, "main")
        run(root, "merge", "-q", "other", check=False)  # Leaves unmerged stages 1-3.
        run(root, "update-index", "--skip-worktree", "skipped.txt")
        run(root, "update-index", "--assume-unchanged", ".gitignore", check=False)
        return [(root, None)]

    def make_subdirectory(self):
        root = self.repo("subdirectory")
        write(root / "app/inner.txt")
        write(root / "outside.txt")
        commit(root)
        write(root / "app/inner.txt", b"changed\n")
        write(root / "outside.txt", b"changed\n")
        write(root / "app/new.txt")
        write(root / "stray.txt")
        return [(root / "app", None)]

    def make_workflow(self):
        root = self.repo("workflow")
        install(root)
        write(root / ".lean/PROJECT.md", b"<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n")
        commit(root)
        write(root / ".lean/PROJECT.md", b"changed\n")
        return [(root, None)]

    def make_not_git(self):
        root = self.base / "not git"
        write(root / "file.txt")
        return [(root, None)]

    def make_git_dir(self):
        root = self.repo("git dir")
        write(root / "a.txt")
        commit(root)
        return [(root / ".git", None)]


def outcome(call):
    try:
        return "value", call()
    except subprocess.CalledProcessError as error:
        return "error", type(error).__name__


class StopGitEquivalenceTests(unittest.TestCase):
    """The public results match the separate-call definitions on every fixture."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="lean stop git ")
        cls.cases = Fixtures(cls.temp.name).all()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def each(self):
        for name, cases in sorted(self.cases.items()):
            for root, base in cases:
                yield name, root, base

    def test_state_digest_matches_separate_calls(self):
        for name, root, _ in self.each():
            with self.subTest(name):
                self.assertEqual(outcome(lambda: evidence.state(root)), outcome(lambda: oracle_state(root)))

    def test_changed_paths_match_separate_calls(self):
        for name, root, base in self.each():
            with self.subTest(name, base=base):
                self.assertEqual(outcome(lambda: evidence.changed_paths(root, base=base)),
                                 outcome(lambda: oracle_changed(root, base)))

    def test_in_git_and_head_match_separate_calls(self):
        for name, root, _ in self.each():
            with self.subTest(name):
                self.assertEqual(util.in_git(root), oracle_in_git(root))
                self.assertEqual(util.head(root), oracle_head(root))

    def test_high_risk_changes_match_separate_calls(self):
        for name, root, _ in self.each():
            if not (root / ".lean").is_dir():
                continue
            (root / ".lean/PROJECT.md").write_text("## High-risk areas\n\n- `.lean/`\n- `*.txt`\n")
            with self.subTest(name):
                expected = [] if not oracle_in_git(root) else evidence.matching_risk(
                    oracle_changed(root, None), evidence.high_risk_areas(root))
                self.assertEqual(evidence.high_risk_changes(root), sorted(set(expected)))

    def test_shared_view_matches_separate_calls(self):
        view = getattr(util, "GitView", None)
        if view is None:
            self.skipTest("no shared Git view in this version")
        for name, root, base in self.each():
            with self.subTest(name, base=base):
                # One view per root and window, consulted in the Stop's order and in reverse.
                for order, fallback in (((0, 1, 2), False), ((2, 1, 0), False), ((0, 1, 2), True)):
                    shared = view(root)
                    if fallback:
                        shared._listing = False  # An unrecognized listing falls back to the defining calls.
                    calls = [lambda: shared.in_git(), lambda: evidence.state(root, shared),
                             lambda: evidence.changed_paths(root, base=base, view=shared)]
                    expected = [lambda: oracle_in_git(root), lambda: oracle_state(root),
                                lambda: oracle_changed(root, base)]
                    for index in order:
                        self.assertEqual(outcome(calls[index]), outcome(expected[index]))
                    self.assertEqual(shared.head(), oracle_head(root))


class StopGitCountTests(unittest.TestCase):
    """One cached Stop on a changed checkout starts few Git processes and still refuses changes."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean stop count ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        install(self.root)
        write(self.root / ".lean/PROJECT.md", b"<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n")
        write(self.root / "work.txt", b"a\n")
        run(self.root, "init", "-q")
        commit(self.root)
        write(self.root / "work.txt", b"changed\n")
        self.shim = Path(self.temp.name) / "shim"
        self.shim.mkdir()
        self.log = self.shim / "calls"
        real = shutil.which("git")
        (self.shim / "git").write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{self.log}"\nexec "{real}" "$@"\n')
        (self.shim / "git").chmod(0o755)

    def stop(self, logged=False):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        env.pop("LEAN_GATE_FORCE", None)
        env.pop("LEAN_GATE_LOCK_FD", None)
        if logged:
            env["PATH"] = f"{self.shim}{os.pathsep}{env['PATH']}"
        payload = {"session_id": "b", "cwd": str(self.root), "hook_event_name": "Stop", "stop_hook_active": False}
        return subprocess.run(["sh", "-c", configured(self.root, "claude", "Stop")], cwd=self.root, env=env,
                              input=json.dumps(payload), text=True, capture_output=True)

    def test_cached_stop_starts_at_most_four_git_processes(self):
        for _ in range(2):
            result = self.stop()
            self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)
        result = self.stop(logged=True)
        self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)
        calls = self.log.read_text().splitlines()
        self.assertLessEqual(len(calls), 4, "\n".join(calls))

    def test_cached_stop_still_reruns_after_a_change(self):
        marker = "printf 'run\\n' >> .agent-runtime/check-runs"
        write(self.root / ".lean/PROJECT.md",
              f"<!-- gate:start -->\n```sh\n{marker}\n```\n<!-- gate:end -->\n".encode())
        for _ in range(2):
            self.assertEqual(self.stop().returncode, 0)
        runs = self.root / ".agent-runtime/check-runs"
        self.assertEqual(runs.read_text().splitlines(), ["run"])
        for change in (lambda: write(self.root / "new file.txt"), lambda: run(self.root, "add", "new file.txt"),
                       lambda: write(self.root / "new file.txt", b"edited\n"),
                       lambda: commit(self.root, "move HEAD")):
            change()
            before = len(runs.read_text().splitlines())
            self.assertEqual(self.stop().returncode, 0)
            self.assertEqual(len(runs.read_text().splitlines()), before + 1)
            self.assertEqual(self.stop().returncode, 0)
            self.assertEqual(len(runs.read_text().splitlines()), before + 1)


if __name__ == "__main__":
    unittest.main()
