"""Activity log: every source records timed events, `lean log` shows and exports them, and it never blocks work."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import commit, install, lean  # noqa: E402
from lean import activity  # noqa: E402


class LogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, *events):
        log = self.root / ".agent-runtime/activity.jsonl"
        log.parent.mkdir(exist_ok=True)
        log.write_text("".join(json.dumps(event) + "\n" for event in events))

    def test_phase_durations_follow_consecutive_phases_of_each_task(self):
        self.write({"at": "2026-10-26T10:00:00Z", "event": "phase", "phase": "contract", "task": "a"},
                   {"at": "2026-10-26T10:00:30Z", "event": "phase", "phase": "implement", "task": "a"},
                   {"at": "2026-10-26T10:05:00Z", "event": "phase", "phase": "contract", "task": "b"},
                   {"at": "2026-10-26T10:10:30Z", "event": "phase", "phase": "done", "task": "a"},
                   {"at": "2026-10-26T10:11:00Z", "event": "gate", "result": "pass", "checks": 3, "seconds": 4})
        durations = activity.phase_durations(activity.load(self.root))
        self.assertEqual(durations["a"], [("contract", 30.0), ("implement", 600.0), ("done", 0.0)])
        self.assertEqual(durations["b"], [("contract", None)])
        summary = activity.summary(activity.load(self.root))
        self.assertIn("a: 10m30s in phases", summary)
        self.assertIn("  implement  10m00s", summary)
        self.assertIn("gate runs: 1 pass", summary)

    def test_since_and_task_filters_and_unreadable_lines(self):
        self.write({"at": "2026-10-26T09:00:00Z", "event": "phase", "phase": "test", "task": "old"},
                   {"at": "2026-10-26T11:00:00Z", "event": "phase", "phase": "test", "task": "new"})
        with (self.root / ".agent-runtime/activity.jsonl").open("a") as out:
            out.write("{not json\n" + json.dumps({"event": "no time"}) + "\n")
        self.assertEqual(len(activity.load(self.root)), 2)
        self.assertEqual([e["task"] for e in activity.load(self.root, since="2026-10-26T10:00:00Z")], ["new"])
        self.assertEqual([e["task"] for e in activity.load(self.root, task="old")], ["old"])

    def test_times_without_a_zone_are_utc_instead_of_a_crash(self):
        self.write({"at": "2026-10-26T09:00:00", "event": "phase", "phase": "test", "task": "naive"},
                   {"at": "2026-10-26T11:00:00Z", "event": "phase", "phase": "done", "task": "naive"})
        self.assertEqual(len(activity.load(self.root, since="2026-10-26")), 2)
        self.assertEqual(len(activity.load(self.root, since="2026-10-26T10:00:00")), 1)
        self.assertIn("naive: 2h00m in phases", activity.summary(activity.load(self.root)))

    def test_recording_never_raises_and_respects_a_symlinked_runtime(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / ".agent-runtime").symlink_to(outside)
        activity.record(self.root, "phase", phase="test")
        self.assertEqual(list(outside.iterdir()), [])

    def test_the_log_rotates_instead_of_growing_without_bound(self):
        log = self.root / ".agent-runtime/activity.jsonl"
        log.parent.mkdir()
        log.write_text("x" * (activity.MAX_BYTES + 1))
        activity.record(self.root, "phase", phase="test", task="t")
        self.assertTrue((self.root / ".agent-runtime/activity.1.jsonl").is_file())
        self.assertEqual(len(log.read_text().splitlines()), 1)


class SourceTests(unittest.TestCase):
    """Each workflow command records its own event."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        install(self.root)
        (self.root / ".lean/PROJECT.md").write_text("<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n")
        tests = self.root / ".lean/tests/unit"
        tests.mkdir(parents=True)
        (tests / "test_ok.py").write_text("import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n"
                                          "        pass\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        commit(self.root, "base")

    def events(self, kind):
        return [event for event in activity.load(self.root) if event["event"] == kind]

    def test_phases_gate_tests_contracts_and_reviews_are_recorded(self):
        self.assertEqual(lean(self.root, "progress", "set", "contract", "--task", "demo").returncode, 0)
        self.assertEqual(lean(self.root, "progress", "set", "test", "--done", "1", "--total", "2").returncode, 0)
        self.assertEqual([(e["phase"], e["task"]) for e in self.events("phase")], [("contract", "demo"), ("test", "demo")])
        self.assertEqual(lean(self.root, "gate", "run").returncode, 0)
        gate = self.events("gate")[-1]
        self.assertEqual((gate["result"], gate["checks"]), ("pass", 1))
        (self.root / ".lean/PROJECT.md").write_text("<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n")
        lean(self.root, "gate", "accept-controls", "--reason", "fixture")
        self.assertEqual(lean(self.root, "gate", "run").returncode, 2)
        refused = self.events("gate")[-1]
        self.assertEqual(refused["result"], "refused")
        self.assertIn("Quality Gate failed", refused["reason"])
        self.assertEqual(lean(self.root, "test", "unit/test_ok.py").returncode, 0)
        test = self.events("test")[-1]
        self.assertEqual((test["files"], test["failed"]), (1, 0))
        declared = lean(self.root, "hook", "claude", "pre-tool", input=json.dumps({
            "session_id": "s", "tool_name": "Bash",
            "tool_input": {"command": "python3 .lean/bin/lean contract declare --contract 'Contract: trivial (log)'"}}))
        self.assertEqual(declared.returncode, 0, declared.stderr)
        self.assertEqual(self.events("contract")[-1]["contract"], "Contract: trivial (log)")
        state = lean(self.root, "evidence", "state").stdout.strip()
        self.assertEqual(lean(self.root, "evidence", "record-" + "review", "--contract", "Contract: trivial (log)",
                              "--reviewer", "r", "--evidence", "e", "--verdict", "PASS", "--state", state).returncode, 0)
        self.assertEqual(self.events("review")[-1]["verdict"], "PASS")

    def test_log_command_shows_summarises_and_exports(self):
        lean(self.root, "progress", "set", "implement", "--task", "demo")
        lean(self.root, "gate", "run")
        timeline = lean(self.root, "log")
        self.assertEqual(timeline.returncode, 0, timeline.stderr)
        self.assertIn("phase implement — demo", timeline.stdout)
        self.assertIn("gate pass (1 checks", timeline.stdout)
        self.assertIn("gate runs: 1 pass", lean(self.root, "log", "--summary").stdout)
        self.assertEqual(len(json.loads(lean(self.root, "log", "--json").stdout)), 2)
        exported = lean(self.root, "log", "--export", "docs/history/activity.md")
        self.assertEqual(exported.returncode, 0, exported.stderr)
        text = (self.root / "docs/history/activity.md").read_text()
        self.assertIn("## Timeline", text)
        self.assertIn("phase implement — demo", text)
        lean(self.root, "log", "--export", "docs/history/activity.jsonl")
        self.assertEqual(len((self.root / "docs/history/activity.jsonl").read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
