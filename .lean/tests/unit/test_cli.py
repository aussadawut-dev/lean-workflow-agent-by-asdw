"""The command line: help, version, status surfaces and read-only behavior."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, install, lean  # noqa: E402
from lean import __version__  # noqa: E402

COMMANDS = ("version", "status", "watch", "progress", "contract", "hook", "gate", "evidence", "mode", "tracker", "plan",
            "queue", "test", "lint", "attribution", "models", "spawn", "effort", "update")


class CliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        install(self.root, extra=(".lean/models.json",))
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def test_help_lists_every_command_group(self):
        result = lean(self.root, "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in COMMANDS:
            self.assertIn(name, result.stdout)
        self.assertEqual(lean(self.root, "version").stdout.strip(), __version__)

    def test_progress_drives_status_line_and_watch(self):
        shown = lean(self.root, "progress", "set", "implement", "--done", "2", "--total", "5", "--task", "add login")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertIn("implement 2/5 — add login", shown.stdout)
        bar = shown.stdout.split(" implement")[0]
        for args in (("status", "--line"), ("status",), ("watch", "--once"), ("progress", "show")):
            with self.subTest(args=args):
                result = lean(self.root, *args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(bar, result.stdout)
        self.assertIn("· gate NOT_RUN", lean(self.root, "status", "--line").stdout)
        report = json.loads(lean(self.root, "status", "--json").stdout)
        self.assertEqual((report["version"], report["progress"]["phase"]), (__version__, "implement"))
        self.assertEqual(lean(self.root, "progress", "set", "deploy").returncode, 2)
        self.assertEqual(lean(self.root, "progress", "clear").returncode, 0)
        self.assertIn("no task tracked", lean(self.root, "status", "--line").stdout)

    def test_read_only_commands_leave_the_checkout_unchanged(self):
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if ".git/" not in str(p))
        for args in (("version",), ("--help",), ("status", "--line"), ("watch", "--once"), ("models",),
                     ("models", "check"), ("gate", "mode"), ("gate", "status"), ("mode", "show"), ("effort",)):
            with self.subTest(args=args):
                self.assertEqual(lean(self.root, *args).returncode, 0)
        after = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if ".git/" not in str(p))
        self.assertEqual(before, after)

    def test_claude_status_line_is_wired_to_the_cli(self):
        settings = json.loads((ROOT / ".claude/settings.json").read_text())
        self.assertIn(".lean/bin/lean status --line", settings["statusLine"]["command"])

    def test_log_filters_task_and_session_across_all_event_types(self):
        runtime = self.root / ".agent-runtime"
        runtime.mkdir()
        events = [
            {"at": "2026-10-31T00:00:00Z", "event": "test", "task": "A", "session": "one", "files": 1},
            {"at": "2026-10-31T00:00:01Z", "event": "gate", "task": "B", "session": "one", "result": "PASS"},
            {"at": "2026-10-31T00:00:02Z", "event": "test", "task": "A", "session": "two", "files": 2},
            {"at": "2026-10-31T00:00:03Z", "event": "test", "files": 3},
        ]
        (runtime / "activity.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
        result = lean(self.root, "log", "--task", "A", "--session", "one", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), events[:1])
        unfiltered = lean(self.root, "log", "--json")
        self.assertEqual(json.loads(unfiltered.stdout), events)

    def test_plan_cli_explains_without_running_project_commands(self):
        project = self.root / ".lean/PROJECT.md"
        project.write_text("<!-- gate:start -->\n```sh\ntouch must-not-run\n```\n<!-- gate:end -->\n")
        tests = self.root / ".lean/tests"
        tests.mkdir()
        (tests / "impact.json").write_text(json.dumps({"scope": ["*"], "lint_only": ["*"], "rules": []}))
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = lean(self.root, "plan", "--explain")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("touch must-not-run", result.stdout)
        structured = lean(self.root, "plan", "--json")
        self.assertEqual(structured.returncode, 0, structured.stderr)
        self.assertIsInstance(json.loads(structured.stdout), dict)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_option_abbreviations_are_refused(self):
        # The guard reads exact option names; an abbreviation could otherwise hide a write.
        for args in (("log", "--exp", "a.md"), ("lint", "--write-reg"), ("target", "use", "--app", "https://h/a.git")):
            with self.subTest(args=args):
                result = lean(self.root, *args)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse((self.root / "a.md").exists())
        # Evidence subcommands too: only the abbreviation is wrong, so argparse alone must refuse it.
        contract = "Contract: risk=HIGH quality=HIGH acceptance=x works"
        checked = lean(self.root, "evidence", "check-review", "--contr", contract)
        self.assertEqual(checked.returncode, 2, checked.stderr)
        self.assertIn("the following arguments are required: --contract", checked.stderr)
        state = lean(self.root, "evidence", "state").stdout.strip()
        recorded = lean(self.root, "evidence", "record-" + "review", "--contr", contract, "--reviewer", "r",
                        "--evidence", "e", "--verdict", "PASS", "--state", state)
        self.assertEqual(recorded.returncode, 2, recorded.stderr)
        self.assertIn("--contract", recorded.stderr)
        self.assertFalse((self.root / ".agent-runtime/review.json").exists(), "an abbreviated option recorded a receipt")

    def test_errors_are_messages_not_tracebacks(self):
        result = lean(self.root, "tracker", "new", "--id", "TCK001", "--title", "x")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        result = lean(self.root, "spawn", "plan")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--tasks is required", result.stderr)


    def test_evidence_help_is_shown_not_refused(self):
        result = lean(self.root, "evidence", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: lean evidence", result.stdout)
        self.assertNotEqual(lean(self.root, "status", "--bogus").returncode, 0)  # Other commands stay strict.

    def test_contract_current_reads_the_session_from_the_environment(self):
        env = {key: value for key, value in os.environ.items()
               if key not in ("LEAN_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")}
        missing = lean(self.root, "contract", "current", env=env)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("--session", missing.stderr)
        result = lean(self.root, "contract", "current", env=dict(env, LEAN_SESSION_ID="session-a"))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("No Task Contract declared for this session", result.stderr)


if __name__ == "__main__":
    unittest.main()
