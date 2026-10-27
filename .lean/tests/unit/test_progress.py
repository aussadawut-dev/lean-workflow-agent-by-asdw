"""Progress state and the solid/shade bar every surface shows."""
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


if __name__ == "__main__":
    unittest.main()
