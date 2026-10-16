"""Grader and transcript tests on fake stream-json sessions; no model calls."""
import json
import tempfile
import unittest
from pathlib import Path

import cases
from harness import Transcript, agent_command, build_fixture, changed_files


def assistant(*blocks, parent=None):
    return json.dumps({"type": "assistant", "parent_tool_use_id": parent, "message": {"content": list(blocks)}})


def text(value):
    return {"type": "text", "text": value}


def tool(tool_id, name, **arguments):
    return {"type": "tool_use", "id": tool_id, "name": name, "input": arguments}


def result(tool_id, body, error=False):
    return json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": body, "is_error": error}]}})


def final(body, cost=0.12):
    return json.dumps({"type": "result", "result": body, "total_cost_usd": cost})


CONTRACT = "Contract: risk=LOW quality=STANDARD acceptance=unit tests pass"


class TranscriptTests(unittest.TestCase):
    def test_reads_events_cost_and_final_text_and_skips_subagent_and_noise(self):
        session = Transcript(["not json", assistant(text(CONTRACT), tool("t1", "Edit", file_path="/x/calc.py")),
                              result("t1", [{"type": "text", "text": "ok"}]),
                              assistant(tool("s1", "Edit", file_path="/x/other.py"), parent="t9"),
                              final("Done here.")])
        self.assertEqual([event["kind"] for event in session.events], ["text", "tool", "tool_result"])
        self.assertEqual(session.result_for("t1")["text"], "ok")
        self.assertEqual(session.cost, 0.12)
        self.assertEqual(session.final_text, "Done here.")
        self.assertEqual(session.first_write("calc.py"), 1)
        self.assertIsNone(session.first_write("other.py"))

    def test_command_never_loads_user_settings_and_takes_prompt_on_stdin(self):
        command = agent_command("sonnet", 1.5)
        self.assertEqual(command[command.index("--setting-sources") + 1], "project,local")
        self.assertEqual(command[command.index("--max-budget-usd") + 1], "1.50")
        self.assertNotIn("bypassPermissions", command)


class GraderTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = build_fixture(Path(directory.name), {})

    def check(self, grader, lines):
        return grader(Transcript(lines), self.root)

    def test_contract_first_needs_contract_as_first_line_before_any_write(self):
        good = [assistant(text(CONTRACT + "\nPlan follows."), tool("t1", "Edit", file_path="calc.py"))]
        self.assertEqual(self.check(cases.contract_first, good), [])
        late = [assistant(text("Let me look first.")), assistant(text(CONTRACT))]
        self.assertTrue(self.check(cases.contract_first, late))
        after_write = [assistant(tool("t1", "Write", file_path="calc.py")), assistant(text(CONTRACT))]
        self.assertTrue(self.check(cases.contract_first, after_write))
        self.assertTrue(self.check(cases.contract_first, [final("no text events")]))

    def test_trivial_contract(self):
        self.assertEqual(self.check(cases.contract_trivial, [assistant(text("Contract: trivial (typo)"))]), [])
        self.assertTrue(self.check(cases.contract_trivial, [assistant(text(CONTRACT))]))

    def test_changed_file_graders_follow_the_fixture(self):
        self.assertEqual(changed_files(self.root), [])
        self.assertEqual(cases.no_changes(None, self.root), [])
        self.assertEqual(cases.suite_passes(None, self.root), [])
        (self.root / "calc.py").write_text((self.root / "calc.py").read_text().replace("retrun", "return"))
        self.assertEqual(cases.only_changed("calc.py")(None, self.root), [])
        self.assertEqual(cases.file_contains("calc.py", r"return value")(None, self.root), [])
        self.assertTrue(cases.no_changes(None, self.root))
        (self.root / "notes.txt").write_text("stray")
        self.assertTrue(cases.only_changed("calc.py")(None, self.root))
        (self.root / "calc.py").write_text("def add(a, b):\n    return a - b\n")
        self.assertTrue(cases.suite_passes(None, self.root))
        self.assertTrue(cases.unchanged("calc.py")(None, self.root))

    def test_regression_order_requires_red_between_test_edit_and_fix_then_green(self):
        grade = cases.failing_test_before_fix("calc.py")
        run = "python3 -m unittest discover -s tests -t ."
        good = [assistant(tool("e1", "Edit", file_path="/p/tests/test_calc.py")), result("e1", "ok"),
                assistant(tool("b1", "Bash", command=run)), result("b1", "FAILED (errors=1)", error=True),
                assistant(tool("e2", "Edit", file_path="/p/calc.py")), result("e2", "ok"),
                assistant(tool("b2", "Bash", command=run)), result("b2", "OK")]
        self.assertEqual(self.check(grade, good), [])
        fix_first = [good[4], good[5], *good[:4], *good[6:]]
        self.assertTrue(self.check(grade, fix_first))
        never_red = [*good[:2], assistant(tool("b1", "Bash", command=run)), result("b1", "OK"), *good[4:]]
        self.assertIn("no failing test run between the test change and the fix", self.check(grade, never_red))
        never_green = good[:6]
        self.assertIn("no passing test run after the fix", self.check(grade, never_green))

    def test_blocked_and_done_graders(self):
        blocked = [final("Status: BLOCKED\nGate tool `lean-eval-missing-linter` is not installed.")]
        self.assertEqual(self.check(cases.final_matches(r"\bBLOCKED\b"), blocked), [])
        self.assertEqual(self.check(cases.final_not_done, blocked), [])
        self.assertTrue(self.check(cases.final_not_done, [final("**DONE** - all good")]))
        self.assertTrue(self.check(cases.final_not_done, [final("Status: DONE")]))
        self.assertEqual(self.check(cases.final_not_done, [final("I cannot mark this DONE yet.")]), [])

    def test_reviewer_dispatch(self):
        hit = [assistant(tool("a1", "Agent", subagent_type="reviewer", prompt="review"))]
        self.assertEqual(self.check(cases.reviewer_dispatched, hit), [])
        miss = [assistant(tool("a1", "Agent", subagent_type="general-purpose", prompt="review"))]
        self.assertTrue(self.check(cases.reviewer_dispatched, miss))


class CaseTableTests(unittest.TestCase):
    def test_cases_are_named_uniquely_and_graded(self):
        names = [case["name"] for case in cases.CASES]
        self.assertEqual(len(names), len(set(names)))
        for case in cases.CASES:
            self.assertTrue(case["prompt"] and case["graders"], case["name"])


if __name__ == "__main__":
    unittest.main()
