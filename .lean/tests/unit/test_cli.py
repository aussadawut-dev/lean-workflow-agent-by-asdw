"""The command line: help, version, status surfaces and read-only behavior."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, install, lean  # noqa: E402
from lean import __version__  # noqa: E402

COMMANDS = ("version", "status", "watch", "progress", "contract", "hook", "gate", "evidence", "mode", "tracker",
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


if __name__ == "__main__":
    unittest.main()
