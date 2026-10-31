"""Activity log: every source records timed events, `lean log` shows and exports them, and it never blocks work."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import commit, install, lean  # noqa: E402
from lean import activity, progress, testsel  # noqa: E402


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

    def test_task_filter_excludes_unrelated_non_phase_and_legacy_events(self):
        self.write(*[{"at": "2026-10-26T10:00:00Z", "event": kind, "task": task}
                     for kind in ("phase", "gate", "test", "spawn", "review", "contract")
                     for task in ("mine", "other", "")])
        events = activity.load(self.root, task="mine")
        self.assertEqual(len(events), 6)
        self.assertTrue(all(event["task"] == "mine" for event in events))

    def test_interleaved_same_task_phases_are_timed_per_session(self):
        self.write(*[{"at": f"2026-10-26T10:{minute}:00Z", "event": "phase",
                      "task": "shared", "session": session, "phase": phase}
                     for minute, session, phase in (("00", "a", "implement"), ("01", "b", "test"),
                                                   ("03", "a", "done"), ("05", "b", "done"))])
        durations = activity.phase_durations(activity.load(self.root))
        self.assertEqual(durations["shared [session a]"], [("implement", 180.0), ("done", 0.0)])
        self.assertEqual(durations["shared [session b]"], [("test", 240.0), ("done", 0.0)])
        self.assertEqual(len(activity.load(self.root, session="a")), 2)

    def test_record_uses_only_own_progress_and_preserves_explicit_empty_context(self):
        progress.update(self.root, "implement", task="mine", session="a")
        progress.update(self.root, "test", task="other", session="b")
        with patch.dict("os.environ", {"LEAN_SESSION_ID": "a"}):
            activity.record(self.root, "review", verdict="PASS")
            activity.record(self.root, "review", session="missing")
            activity.record(self.root, "review", session="", task="")
        reviews = [e for e in activity.load(self.root) if e["event"] == "review"]
        self.assertEqual((reviews[0]["task"], reviews[0]["session"]), ("mine", "a"))
        self.assertNotIn("task", reviews[1])
        self.assertEqual(reviews[1]["session"], "missing")
        self.assertNotIn("task", reviews[2])
        self.assertNotIn("session", reviews[2])

    def test_summary_labels_nested_durations_and_unknown_token_usage(self):
        events = [{"event": "gate", "result": "pass", "seconds": 10},
                  {"event": "gate-check", "seconds": 9},
                  {"event": "test", "seconds": 8},
                  {"event": "test-file", "seconds": 7}]
        summary = "\n".join(activity.summary(events))
        self.assertIn("10s gate wall time", summary)
        self.assertIn("8s test wall time", summary)
        self.assertIn("nested", summary)
        self.assertIn("token usage: unknown", summary)
        self.assertNotIn("34s", summary)
        self.assertIn("costs UNKNOWN task [UNKNOWN session]: gates 1 (10s wall), tests 1 (8s wall)", summary)

    def test_cost_rows_separate_tasks_sessions_and_preserve_unknown_legacy_bucket(self):
        events = [{"event": "gate", "result": "pass", "seconds": 10, "task": "shared", "session": "a"},
                  {"event": "test", "seconds": 8, "task": "shared", "session": "b"},
                  {"event": "test", "seconds": 5}]
        summary = activity.summary(events)
        self.assertIn("costs shared [a]: gates 1 (10s wall), tests 0 (0s wall)", summary)
        self.assertIn("costs shared [b]: gates 0 (0s wall), tests 1 (8s wall)", summary)
        self.assertIn("costs UNKNOWN task [UNKNOWN session]: gates 0 (0s wall), tests 1 (5s wall)", summary)

    def test_legacy_missing_costs_are_unknown_instead_of_zero(self):
        events = [{"event": "gate", "result": "pass"},
                  {"event": "test", "seconds": 4}, {"event": "test", "seconds": None}]
        summary = "\n".join(activity.summary(events))
        self.assertIn("unknown gate wall time", summary)
        self.assertIn("4s observed, 1 unknown test wall time", summary)
        self.assertIn("gates 1 (unknown wall), tests 2 (4s observed, 1 unknown wall)", summary)

    def test_test_file_timings_are_persisted_under_one_run_without_state_rereads(self):
        from types import SimpleNamespace
        with patch.object(testsel.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="")), \
                patch.object(progress, "load", return_value={"task": "t", "session": "s"}) as load, \
                patch.object(testsel.time, "monotonic", side_effect=[0, 1, 3, 4, 7, 10]), \
                patch.dict("os.environ", {"LEAN_SESSION_ID": "s"}):
            self.assertEqual(testsel.run_files(self.root, ["unit/test_a.py", "unit/test_b.py"],
                                              jobs=1, show=lambda _: None), 0)
        events = activity.load(self.root)
        run = next(e for e in events if e["event"] == "test")
        files = [e for e in events if e["event"] == "test-file"]
        self.assertEqual(len(files), 2)
        self.assertEqual({e["run_id"] for e in files}, {run["run_id"]})
        self.assertEqual(len({e["file_id"] for e in files}), 2)
        self.assertEqual({e["file"]: e["seconds"] for e in files},
                         {"unit/test_a.py": 2, "unit/test_b.py": 3})
        self.assertEqual(run["seconds"], 10)
        self.assertTrue(all(e["seconds"] >= 0 and e["task"] == "t" for e in files))
        self.assertEqual(load.call_count, 1)

    def test_context_failures_never_block_test_execution(self):
        from types import SimpleNamespace
        with patch.object(progress, "env_session", side_effect=RuntimeError("unavailable")), \
                patch.object(testsel.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="")):
            self.assertEqual(testsel.run_files(self.root, ["unit/test_a.py"], show=lambda _: None), 0)
        with patch.object(activity.uuid, "uuid4", side_effect=OSError("unavailable")):
            run = activity.run_context(self.root)
            self.assertTrue(run["run_id"])
            self.assertEqual((run["task"], run["session"]), ("", ""))

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
        check = self.events("gate-check")[-1]
        self.assertEqual(check["check_id"], gate["run_id"] + ":1")
        self.assertGreaterEqual(check["seconds"], 0)
        self.assertEqual(check["result"], "pass")
        (self.root / ".lean/PROJECT.md").write_text("<!-- gate:start -->\n```sh\nfalse # secret-value\n```\n<!-- gate:end -->\n")
        lean(self.root, "gate", "accept-controls", "--reason", "fixture")
        self.assertEqual(lean(self.root, "gate", "run").returncode, 2)
        refused = self.events("gate")[-1]
        self.assertEqual(refused["result"], "refused")
        self.assertIn("Quality Gate failed", refused["reason"])
        self.assertNotEqual(refused["run_id"], gate["run_id"])
        self.assertEqual(self.events("gate-check")[-1]["result"], "fail")
        self.assertNotIn("secret-value", activity.path(self.root).read_text())
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
        self.assertEqual(len(json.loads(lean(self.root, "log", "--json").stdout)), 3)
        exported = lean(self.root, "log", "--export", "docs/history/activity.md")
        self.assertEqual(exported.returncode, 0, exported.stderr)
        text = (self.root / "docs/history/activity.md").read_text()
        self.assertIn("## Timeline", text)
        self.assertIn("phase implement — demo", text)
        lean(self.root, "log", "--export", "docs/history/activity.jsonl")
        self.assertEqual(len((self.root / "docs/history/activity.jsonl").read_text().splitlines()), 3)

    def test_nested_test_run_is_linked_to_gate_and_uses_own_session_task(self):
        (self.root / ".lean/PROJECT.md").write_text(
            "<!-- gate:start -->\n```sh\npython3 .lean/bin/lean test unit/test_ok.py\n```\n<!-- gate:end -->\n")
        commit(self.root, "nested gate")
        environment = dict(os.environ, LEAN_SESSION_ID="mine")
        lean(self.root, "progress", "set", "test", "--task", "own task", env=environment)
        lean(self.root, "progress", "set", "gate", "--task", "other task",
             env=dict(environment, LEAN_SESSION_ID="other"))
        result = lean(self.root, "gate", "run", "--session", "mine",
                      env=dict(environment, LEAN_SESSION_ID="other"))
        self.assertEqual(result.returncode, 0, result.stderr)
        gate, test = self.events("gate")[-1], self.events("test")[-1]
        self.assertEqual(test["parent_run_id"], gate["run_id"])
        self.assertEqual((gate["task"], test["task"]), ("own task", "own task"))
        self.assertEqual((gate["session"], test["session"]), ("mine", "mine"))

    def test_claude_stop_uses_payload_session_for_gate_and_nested_tests(self):
        (self.root / ".lean/PROJECT.md").write_text(
            "<!-- gate:start -->\n```sh\npython3 .lean/bin/lean test unit/test_ok.py\n```\n<!-- gate:end -->\n")
        commit(self.root, "hook nested gate")
        progress.update(self.root, "gate", task="payload task", session="payload")
        progress.update(self.root, "gate", task="environment task", session="other")
        base_env = {key: value for key, value in os.environ.items()
                    if key not in ("LEAN_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "LEAN_ACTIVITY_SESSION_ID")}
        for environment in (base_env, dict(base_env, LEAN_SESSION_ID="other")):
            with self.subTest(session=environment.get("LEAN_SESSION_ID")):
                result = lean(self.root, "gate", "run", "--hook",
                              input=json.dumps({"session_id": "payload"}), env=environment)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                parent, nested = self.events("gate")[-1], self.events("test")[-1]
                self.assertEqual((parent["session"], nested["session"]), ("payload", "payload"))
                self.assertEqual((parent["task"], nested["task"]), ("payload task", "payload task"))
                self.assertEqual(nested["parent_run_id"], parent["run_id"])


if __name__ == "__main__":
    unittest.main()
