"""Progress state and the solid/shade bar every surface shows."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import support  # noqa: E402,F401
from lean import progress  # noqa: E402
from lean.util import LeanError  # noqa: E402


class RenderTests(unittest.TestCase):
    def test_bar_is_solid_then_shaded_with_a_percentage(self):
        self.assertEqual(progress.render(0.4), "████████░░░░░░░░░░░░ 40%")
        self.assertEqual(progress.render(0.0), "░" * 20 + " 0%")
        self.assertEqual(progress.render(1.0), "█" * 20 + " 100%")
        self.assertEqual(progress.render(0.5, width=10, percent=False), "█████░░░░░")

    def test_out_of_range_fractions_are_clamped(self):
        self.assertEqual(progress.render(-1), progress.render(0))
        self.assertEqual(progress.render(7), progress.render(1))

    def test_phase_and_counts_set_the_fraction(self):
        phases = len(progress.PHASES)
        self.assertAlmostEqual(progress.fraction({"phase": "contract"}), 0)
        self.assertAlmostEqual(progress.fraction({"phase": "implement", "done": 2, "total": 5}), 2.4 / phases)
        self.assertAlmostEqual(progress.fraction({"phase": "gate", "done": 1, "total": 1}), 1.0)
        self.assertEqual(progress.fraction({"phase": "done"}), 1.0)

    def test_line_names_phase_counts_note_and_task(self):
        line = progress.line({"phase": "test", "done": 3, "total": 8, "note": "unit", "task": "add login"})
        self.assertTrue(line.startswith(progress.render(progress.fraction({"phase": "test", "done": 3, "total": 8}))))
        self.assertIn("test 3/8 (unit) — add login", line)


class StateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_update_keeps_the_task_across_phases_and_clear_removes_it(self):
        self.assertIsNone(progress.load(self.root))
        progress.update(self.root, "contract", task="add login")
        state = progress.update(self.root, "implement", 1, 4)
        self.assertEqual((state["task"], state["phase"], state["done"], state["total"]), ("add login", "implement", 1, 4))
        self.assertEqual(progress.load(self.root)["phase"], "implement")
        progress.clear(self.root)
        self.assertIsNone(progress.load(self.root))

    def test_invalid_phases_and_counts_are_refused_without_writing(self):
        for args in (("ship",), ("test", 1, None), ("test", None, 2), ("test", 3, 2), ("test", -1, 2), ("test", 0, 0)):
            with self.subTest(args=args), self.assertRaises(LeanError):
                progress.update(self.root, *args)
        self.assertIsNone(progress.load(self.root))

    def test_a_corrupt_state_reads_as_no_task(self):
        path = self.root / ".agent-runtime/progress.json"
        path.parent.mkdir()
        for text in ("{not json", "[]", '{"phase": "ship"}'):
            path.write_text(text)
            self.assertIsNone(progress.load(self.root))

    def test_watch_frame_lists_the_task_and_each_agent(self):
        self.assertIn("no task tracked", progress.watch_frame(self.root))
        progress.update(self.root, "review", task="refactor")
        spawn = self.root / ".agent-runtime/spawn"
        spawn.mkdir(parents=True)
        (spawn / "current.json").write_text(
            '{"agents": [{"id": "api", "provider": "codex", "model": "m", "status": "done"},'
            ' {"id": "ui", "provider": "codex", "model": "m", "status": "running",'
            ' "progress": {"phase": "test", "done": 1, "total": 2}}]}')
        frame = progress.watch_frame(self.root).splitlines()
        self.assertIn("review — refactor", frame[0])
        self.assertEqual(frame[1], "agents:")
        self.assertTrue(frame[2].strip().startswith(progress.render(1.0)))
        self.assertIn("api [codex/m] done", frame[2])
        self.assertTrue(frame[3].strip().startswith(progress.render(3.5 / len(progress.PHASES))))


class SessionTests(unittest.TestCase):
    """TCK015: one session's progress is not shown as another's."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        saved = {name: os.environ.pop(name, None) for name in progress.SESSION_ENV}
        self.addCleanup(lambda: [os.environ.__setitem__(k, v) for k, v in saved.items() if v is not None])

    def test_each_session_keeps_its_own_progress(self):
        progress.update(self.root, "gate", task="other task", session="sess-b-123456")
        progress.update(self.root, "implement", task="my task", session="sess-a-123456")
        progress.update(self.root, "gate", task="other task", session="sess-b-123456")
        mine = progress.load(self.root, "sess-a-123456")
        self.assertEqual((mine["phase"], mine["task"]), ("implement", "my task"))
        self.assertEqual(progress.load(self.root, "sess-b-123456")["phase"], "gate")
        self.assertIn("implement — my task", progress.shown(self.root, "sess-a-123456"))
        self.assertNotIn("session", progress.shown(self.root, "sess-a-123456"))

    def test_phase_events_keep_the_explicit_session_even_when_environment_differs(self):
        from lean import activity
        os.environ["LEAN_SESSION_ID"] = "environment-session"
        self.addCleanup(os.environ.pop, "LEAN_SESSION_ID", None)
        progress.update(self.root, "implement", task="explicit task", session="explicit-session")
        event = activity.load(self.root)[-1]
        self.assertEqual((event["task"], event["session"]), ("explicit task", "explicit-session"))

    def test_another_sessions_progress_is_labelled(self):
        progress.update(self.root, "gate", task="other task", session="sess-b-123456")
        text = progress.shown(self.root, "sess-a-123456")
        self.assertTrue(text.startswith("session sess-b-1:"), text)
        self.assertIn("gate — other task", text)
        self.assertIsNone(progress.shown(self.root, "sess-a-123456", others=False))

    def test_environment_names_the_session_and_clear_is_per_session(self):
        os.environ["CLAUDE_CODE_SESSION_ID"] = "env-session-1"
        progress.update(self.root, "test", task="env task")
        self.assertEqual(progress.load(self.root, "env-session-1")["task"], "env task")
        self.assertEqual(progress.load(self.root)["task"], "env task")
        progress.update(self.root, "review", task="other", session="sess-b-123456")
        progress.clear(self.root)
        self.assertIsNone(progress.load(self.root, "env-session-1", others=False))
        self.assertEqual(progress.load(self.root, "sess-b-123456")["phase"], "review")

    def test_a_sessions_first_update_keeps_only_an_unowned_or_own_shared_task(self):
        progress.update(self.root, "scope", task="shared task", session="")
        self.assertEqual(progress.update(self.root, "implement", session="sess-a-123456")["task"], "shared task")
        progress.update(self.root, "scope", task="b task", session="sess-b-123456")
        self.assertEqual(progress.update(self.root, "implement", session="sess-c-123456")["task"], "")

    def test_hooks_show_the_payload_sessions_progress_and_label_others(self):
        import json
        from lean import hooks
        progress.update(self.root, "gate", task="other task", session="sess-b-123456")
        message = json.loads(hooks.status_message(self.root, "sess-a-123456"))["systemMessage"]
        self.assertIn("session sess-b-1: ", message)
        progress.update(self.root, "implement", task="my task", session="sess-a-123456")
        message = json.loads(hooks.status_message(self.root, "sess-a-123456"))["systemMessage"]
        self.assertIn("implement — my task", message)
        self.assertNotIn("other task", message)
        notices = "\n".join(hooks.notices(self.root, "sess-a-123456"))
        self.assertIn("implement — my task", notices)
        self.assertNotIn("other task", notices)

    def test_unsafe_session_ids_fall_back_to_the_shared_state(self):
        for bad in ("../x", "a/b", "", "x" * 200):
            with self.subTest(session=bad):
                state = progress.update(self.root, "scope", task="shared", session=bad)
                self.assertEqual(state["session"], "")
                self.assertEqual(list((self.root / ".agent-runtime").glob("progress/*")), [])

    def test_status_line_reads_the_status_line_session_from_stdin(self):
        import json, subprocess
        progress.update(self.root, "gate", task="other task", session="sess-b-123456")
        progress.update(self.root, "implement", task="my task", session="sess-a-123456")
        lean = Path(__file__).resolve().parents[2] / "bin/lean"
        env = {k: v for k, v in os.environ.items() if k not in progress.SESSION_ENV}
        result = subprocess.run([sys.executable, str(lean), "--root", str(self.root), "status", "--line"],
                                input=json.dumps({"session_id": "sess-a-123456"}), text=True,
                                capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("implement — my task", result.stdout)
        self.assertNotIn("other task", result.stdout)


if __name__ == "__main__":
    unittest.main()
