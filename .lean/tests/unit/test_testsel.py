"""Impact selection: run only the tests a change can affect, never silently skip."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, commit, git, install, lean  # noqa: E402
from lean import testsel  # noqa: E402
from lean.util import LeanError  # noqa: E402


class ShippedImpactMapTests(unittest.TestCase):
    def test_every_rule_names_real_tests_and_every_test_is_reachable(self):
        data = testsel.impact(ROOT)
        available = set(testsel.all_files(ROOT))
        reachable = set()
        for rule in data["rules"]:
            for test in rule["tests"]:
                if test in testsel.CATEGORIES:
                    reachable.update(testsel.all_files(ROOT, (test,)))
                else:
                    self.assertIn(test, available, f"impact.json names a missing test: {test}")
                    reachable.add(test)
        self.assertEqual(sorted(available - reachable), [], "tests no impact rule reaches run only in full runs")

    def test_rules_win_over_lint_only_globs(self):
        # A template or agent definition is Markdown that code reads: its rule must still select tests.
        self.assertIn("unit/test_records.py", testsel.select(ROOT, [".lean/templates/tracker.md"])[0])
        self.assertIn("unit/test_structure.py", testsel.select(ROOT, [".claude/agents/reviewer.md"])[0])
        self.assertEqual(testsel.select(ROOT, ["docs/workflow.md"]), ([], "lint"))

    def test_target_and_queue_work_records_are_lint_only(self):
        records = [
            ".lean/targets/casetodian-next-v2/.agents/queue/items/Q9801.json",
            ".lean/targets/casetodian-next-v2/context.json",
            ".lean/targets/casetodian-next-v2/.lean/config.json",
            ".agents/queue/items/Q0001.json",
            ".agents/queue/history/Q0000.json",
            "docs/tracking/TCK001.md",
        ]
        for path in records:
            with self.subTest(path=path):
                self.assertEqual(testsel.select(ROOT, [path]), ([], "lint"))
        self.assertEqual(testsel.select(ROOT, records), ([], "lint"))
        self.assertIn("unit/test_records.py", testsel.select(ROOT, [".lean/templates/queue-item.json"])[0])
        self.assertIn("unit/test_structure.py", testsel.select(ROOT, [".agents/skills/lean-task/SKILL.md"])[0])

    def test_moving_the_pin_runs_lint_only(self):
        # asdw-harness: every `lean update` pin move ran the full suite (no rule covered the pin file).
        self.assertEqual(testsel.select(ROOT, [".lean/upstream.json"]), ([], "lint"))

    def test_every_workflow_code_file_is_covered(self):
        data = testsel.impact(ROOT)
        for path in sorted((ROOT / ".lean/lean").glob("*.py")):
            relative = str(path.relative_to(ROOT))
            self.assertTrue(any(testsel.matches(relative, rule["paths"]) for rule in data["rules"]), relative)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        tests = self.root / ".lean/tests"
        for name in ("unit/test_a.py", "unit/test_b.py", "hooks/test_h.py", "e2e/test_e.py"):
            (tests / name).parent.mkdir(parents=True, exist_ok=True)
            (tests / name).write_text("import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n"
                                      "        pass\n")
        (tests / "impact.json").write_text(json.dumps({
            "scope": ["src/*", ".lean/*", "*.md", "docs/*"],
            "lint_only": ["*.md", "docs/*"],
            "rules": [{"paths": ["src/a.py"], "tests": ["unit/test_a.py"]},
                      {"paths": ["src/hook/*"], "tests": ["hooks"]}]}))

    def test_rules_categories_docs_and_uncovered_paths(self):
        self.assertEqual(testsel.select(self.root, []), ([], "no changes"))
        # A project's own application code cannot affect the workflow's tests.
        self.assertEqual(testsel.select(self.root, ["app/main.go", "web/x.js"]), ([], "no workflow changes"))
        self.assertEqual(testsel.select(self.root, ["app/main.go", "src/a.py"])[0], ["unit/test_a.py"])
        self.assertEqual(testsel.select(self.root, ["README.md", "docs/guide/x.png"]), ([], "lint"))
        self.assertEqual(testsel.select(self.root, ["src/a.py", "notes.md"])[0], ["unit/test_a.py"])
        self.assertEqual(testsel.select(self.root, ["src/hook/deep/x.py"])[0], ["hooks/test_h.py"])
        self.assertEqual(testsel.select(self.root, [".lean/tests/unit/test_b.py"])[0], ["unit/test_b.py"])
        files, reason = testsel.select(self.root, ["src/a.py", "src/unmapped.py"])
        self.assertEqual(files, sorted(testsel.all_files(self.root)))
        self.assertIn("src/unmapped.py", reason)

    def test_a_rule_naming_a_missing_test_is_an_error(self):
        path = self.root / ".lean/tests/impact.json"
        path.write_text(json.dumps({"scope": ["*"], "lint_only": [],
                                    "rules": [{"paths": ["x"], "tests": ["unit/test_gone.py"]}]}))
        with self.assertRaises(LeanError):
            testsel.select(self.root, ["x"])
        path.write_text(json.dumps({"rules": []}))
        with self.assertRaises(LeanError):
            testsel.impact(self.root)

    def test_changed_paths_cover_worktree_index_untracked_and_unpushed_commits(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "src").mkdir()
        for name in ("pushed.py", "committed.py", "edited.py", "staged.py"):
            (self.root / "src" / name).write_text("x = 1\n")
        commit(self.root, "base")
        remote = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, remote)
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        git(self.root, "remote", "add", "origin", str(remote))
        git(self.root, "push", "-q", "origin", "HEAD:refs/heads/main")
        git(self.root, "fetch", "-q", "origin")
        self.assertEqual(testsel.changed(self.root), [])
        (self.root / "src/committed.py").write_text("x = 2\n")
        commit(self.root, "unpushed")
        (self.root / "src/edited.py").write_text("x = 3\n")
        (self.root / "src/staged.py").write_text("x = 4\n")
        git(self.root, "add", "src/staged.py")
        (self.root / "src/new.py").write_text("y = 1\n")
        self.assertEqual(testsel.changed(self.root),
                         ["src/committed.py", "src/edited.py", "src/new.py", "src/staged.py"])


class NoRemoteTests(unittest.TestCase):
    def test_commits_still_count_when_the_repository_has_no_remote(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / "a.txt").write_text("1\n")
        commit(root, "base")
        (root / "a.txt").write_text("2\n")
        (root / "b.txt").write_text("new\n")
        commit(root, "work")
        found = testsel.changed(root)
        self.assertIn("a.txt", found)
        self.assertIn("b.txt", found)


class CommandTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        install(self.root)
        tests = self.root / ".lean/tests/unit"
        tests.mkdir(parents=True)
        (tests / "test_pass.py").write_text("import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n"
                                            "        pass\n")
        (tests / "test_fail.py").write_text("import unittest\n\nclass T(unittest.TestCase):\n    def test_bad(self):\n"
                                            "        self.fail('boom')\n")
        (self.root / ".lean/tests/impact.json").write_text(json.dumps({
            "scope": ["*"], "lint_only": ["*.md"], "rules": [{"paths": ["ok.py"], "tests": ["unit/test_pass.py"]}]}))
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        commit(self.root, "base")
        remote = Path(tempfile.mkdtemp())  # The base is pushed, so only later work counts as changed.
        self.addCleanup(shutil.rmtree, remote)
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        git(self.root, "remote", "add", "origin", str(remote))
        git(self.root, "push", "-q", "origin", "HEAD:refs/heads/main")
        git(self.root, "fetch", "-q", "origin")

    def test_changed_runs_the_selection_with_a_bar_and_reports_failures(self):
        (self.root / "ok.py").write_text("x = 1\n")
        listed = lean(self.root, "test", "--changed", "--list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("unit/test_pass.py", listed.stdout)
        self.assertNotIn("unit/test_fail.py", listed.stdout)
        ran = lean(self.root, "test", "--changed")
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        self.assertIn("Tests ████████████████████ 100% 1/1 unit/test_pass.py ok", ran.stdout)
        failed = lean(self.root, "test", "--all")
        self.assertEqual(failed.returncode, 1, failed.stdout)
        self.assertIn("unit/test_fail.py FAIL", failed.stdout)
        self.assertIn("boom", failed.stdout)
        summary = failed.stdout.strip().splitlines()[-1]
        self.assertRegex(summary, r"^1/2 test files passed in [\d.]+s; failed: unit/test_fail\.py$")

    def test_named_tests_accept_tiers_and_repository_paths(self):
        for names, expected in ((["unit"], "unit/test_fail.py\nunit/test_pass.py"),
                                ([".lean/tests/unit/test_pass.py"], "unit/test_pass.py"),
                                (["./.lean/tests/unit/test_pass.py", "unit/test_pass.py"], "unit/test_pass.py")):
            with self.subTest(names=names):
                listed = lean(self.root, "test", "--list", *names)
                self.assertEqual(listed.returncode, 0, listed.stderr)
                self.assertEqual(listed.stdout.split("\n", 1)[1].strip(), expected)
        ran = lean(self.root, "test", ".lean/tests/unit/test_pass.py")
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        for wrong in ("unit/test_missing.py", "e2e", "../unit/test_pass.py", "unit/../unit/test_pass.py"):
            with self.subTest(wrong=wrong):
                refused = lean(self.root, "test", "--list", wrong)
                if wrong == "e2e":  # An empty tier is a valid, empty selection.
                    self.assertEqual(refused.returncode, 0, refused.stderr)
                    self.assertIn("Selected 0 test file(s)", refused.stdout)
                    continue
                self.assertEqual(refused.returncode, 2, refused.stdout)
                self.assertIn("no such test file", refused.stderr)

    def test_a_documentation_only_change_runs_lint_only(self):
        (self.root / "notes.md").write_text("words\n")
        result = lean(self.root, "test", "--changed", "--list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Documentation-only change: lint only.", result.stdout)
        self.assertNotIn("test_", result.stdout)



class GateScopeTests(unittest.TestCase):
    """`lean gate scope` skips a check only when the change is work records alone; anything else runs it."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        install(self.root)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "src").mkdir()
        (self.root / "src/app.py").write_text("x = 1\n")
        for record in ("docs/tracking/TCK001.md", ".agents/queue/items/Q0001.json",
                       ".lean/targets/app/docs/tracking/TCK002.md", ".lean/targets/app/.agents/queue/items/Q0002.json"):
            (self.root / record).parent.mkdir(parents=True, exist_ok=True)
            (self.root / record).write_text("v1\n")
        commit(self.root, "base")
        remote = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, remote)
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        git(self.root, "remote", "add", "origin", str(remote))
        git(self.root, "push", "-q", "origin", "HEAD:refs/heads/main")
        git(self.root, "fetch", "-q", "origin")
        git(self.root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        self.remote = remote
        self.marker = self.root.parent / (self.root.name + ".ran")
        self.addCleanup(lambda: self.marker.unlink(missing_ok=True))

    def scope(self, *options, env=None, cwd=None):
        """Run a check that leaves a marker; return (result, whether the check ran)."""
        self.marker.unlink(missing_ok=True)
        command = [sys.executable, "-c", f"open({str(self.marker)!r}, 'w').close()"]
        result = lean(self.root, "gate", "scope", *options, "--", *command,
                      env=dict(os.environ, **(env or {})), cwd=cwd)
        return result, self.marker.exists()

    def test_record_only_changes_skip_and_everything_else_runs(self):
        result, ran = self.scope()
        self.assertEqual((result.returncode, ran), (0, True), "a clean tree is no evidence: run")
        (self.root / "docs/tracking/TCK001.md").write_text("v2\n")
        (self.root / ".agents/queue/items/Q0003.json").write_text("{}\n")
        (self.root / ".lean/targets/app/docs/tracking/TCK002.md").write_text("v2\n")
        git(self.root, "add", ".lean/targets/app/docs/tracking/TCK002.md")
        result, ran = self.scope()
        self.assertEqual((result.returncode, ran), (0, False), result.stdout + result.stderr)
        self.assertIn("gate scope: skipped", result.stdout)
        self.assertIn("3 changed path(s) are work records only", result.stdout)
        result, ran = self.scope(env={"LEAN_GATE_SCOPE": "full"})
        self.assertTrue(ran, "LEAN_GATE_SCOPE=full forces the check")
        result, ran = self.scope(cwd=self.root / "docs")
        self.assertFalse(ran, "paths are judged from the repository top, not the working directory")
        (self.root / "src/app.py").write_text("x = 2\n")
        result, ran = self.scope()
        self.assertTrue(ran, "an application change beside records runs the check")

    def test_unpushed_commits_and_renames_count(self):
        (self.root / "docs/tracking/TCK001.md").write_text("v2\n")
        commit(self.root, "records")
        result, ran = self.scope()
        self.assertFalse(ran, "an unpushed record-only commit still skips")
        (self.root / "src/app.py").write_text("x = 3\n")
        commit(self.root, "code")
        result, ran = self.scope()
        self.assertTrue(ran, "an unpushed code commit runs the check")
        git(self.root, "push", "-q", "origin", "HEAD:refs/heads/main")
        git(self.root, "fetch", "-q", "origin")
        git(self.root, "mv", "src/app.py", "docs/tracking/app.py")
        result, ran = self.scope()
        self.assertTrue(ran, "a rename out of the code tree counts its source path")

    def test_only_and_always_globs(self):
        (self.root / "notes.txt").write_text("n\n")
        result, ran = self.scope()
        self.assertTrue(ran)
        result, ran = self.scope("--only", "notes.txt")
        self.assertFalse(ran, "--only adds a path that alone does not need the check")
        (self.root / "docs/tracking/TCK001.md").write_text("v2\n")
        result, ran = self.scope("--only", "notes.txt", "--always", "docs/tracking/TCK001.md")
        self.assertTrue(ran, "--always wins over records and --only")

    def test_undecidable_states_run_the_check(self):
        (self.root / "docs/tracking/TCK001.md").write_text("v2\n")
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside)
        result, ran = self.scope(cwd=outside)
        self.assertTrue(ran, "outside a repository nothing is known: run")
        git(self.root, "remote", "remove", "origin")
        result, ran = self.scope()
        self.assertTrue(ran, "without a remote every tracked file counts: run")

    def test_the_check_status_and_missing_commands_pass_through(self):
        (self.root / "src/app.py").write_text("x = 2\n")
        failed = lean(self.root, "gate", "scope", "--", sys.executable, "-c", "raise SystemExit(3)")
        self.assertEqual(failed.returncode, 3)
        missing = lean(self.root, "gate", "scope", "--", "lean-no-such-command")
        self.assertEqual(missing.returncode, 127)
        self.assertIn("command not found: lean-no-such-command", missing.stderr)
        empty = lean(self.root, "gate", "scope")
        self.assertEqual(empty.returncode, 2)
        self.assertIn("needs a command", empty.stderr)

    def test_pushed_unmerged_commits_still_count(self):
        git(self.root, "checkout", "-q", "-b", "feat")
        (self.root / "src/app.py").write_text("x = 5\n")
        commit(self.root, "code")
        git(self.root, "push", "-q", "origin", "feat")
        git(self.root, "fetch", "-q", "origin")
        (self.root / "docs/tracking/TCK001.md").write_text("v2\n")
        result, ran = self.scope()
        self.assertTrue(ran, "a pushed feature branch is not merged, so its code commit still counts")
        git(self.root, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
        git(self.root, "update-ref", "-d", "refs/remotes/origin/main")
        result, ran = self.scope()
        self.assertTrue(ran, "without a resolvable default branch: run")

    def test_submodule_changes_count_whatever_the_ignore_settings(self):
        app = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, app)
        subprocess.run(["git", "init", "-q", str(app)], check=True)
        (app / "main.py").write_text("x = 1\n")
        commit(app, "app")
        subprocess.run(["git", "-C", str(self.root), "-c", "protocol.file.allow=always", "submodule", "add", "-q",
                        str(app), "targets/app"], check=True, capture_output=True)
        commit(self.root, "pointer")
        git(self.root, "push", "-q", "origin", "HEAD:refs/heads/main")
        git(self.root, "fetch", "-q", "origin")
        git(self.root, "config", "submodule.targets/app.ignore", "all")
        git(self.root, "config", "diff.ignoreSubmodules", "all")
        (self.root / "docs/tracking/TCK001.md").write_text("v2\n")
        result, ran = self.scope()
        self.assertFalse(ran, result.stdout + result.stderr)
        (self.root / "targets/app/new.py").write_text("y = 1\n")
        result, ran = self.scope()
        self.assertTrue(ran, "an untracked file inside the submodule is an application change")
        (self.root / "targets/app/new.py").unlink()
        (self.root / "targets/app/main.py").write_text("x = 2\n")
        commit(self.root / "targets/app", "app change")
        result, ran = self.scope()
        self.assertTrue(ran, "a new submodule commit counts even with ignore=all")


if __name__ == "__main__":
    unittest.main()
