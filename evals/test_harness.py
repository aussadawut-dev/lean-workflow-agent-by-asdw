"""Grader and transcript tests on fake Claude stream-json and Codex exec --json sessions; no model calls."""
import json
import os
import tempfile
import unittest
from pathlib import Path

import cases
from harness import CodexTranscript, Transcript, agent_command, build_fixture, changed_files, read_transcript


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


def codex_item(ident, kind, done=True, **fields):
    return json.dumps({"type": "item.completed" if done else "item.started", "item": {"id": ident, "type": kind,
                                                                                      **fields}})


def codex_text(ident, value):
    return codex_item(ident, "agent_message", text=value)


def codex_shell(ident, command, output="", code=0):
    return codex_item(ident, "command_execution", command=f"/bin/zsh -lc '{command}'", aggregated_output=output,
                      exit_code=code, status="completed" if code == 0 else "failed")


def codex_patch(ident, *paths, kind="update"):
    return codex_item(ident, "file_change", changes=[{"path": path, "kind": kind} for path in paths],
                      status="completed")


def rollout_spawn(task_name, fork_turns="none"):
    arguments = json.dumps({"task_name": task_name, "fork_turns": fork_turns, "message": "gAAAA-encrypted"})
    return json.dumps({"type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent",
                                                            "arguments": arguments}})


def codex_session(lines, *rollout):
    session = CodexTranscript(lines)
    session.attach_rollout(list(rollout))
    return session


def codex_turn(input_tokens, output_tokens):
    return json.dumps({"type": "turn.completed", "usage": {"input_tokens": input_tokens,
                                                           "output_tokens": output_tokens}})


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

    def test_ignores_events_whose_message_or_blocks_are_not_objects(self):
        session = Transcript([json.dumps({"type": "system", "message": "hook output"}),
                              json.dumps({"type": "assistant", "message": "plain"}),
                              json.dumps({"type": "assistant", "message": {"content": ["raw", text(CONTRACT)]}}),
                              json.dumps(["not", "an", "object"]),
                              final("end")])
        self.assertEqual([event["kind"] for event in session.events], ["text"])
        self.assertEqual(session.final_text, "end")

    def test_command_never_loads_user_settings_and_takes_prompt_on_stdin(self):
        command = agent_command("sonnet", 1.5)
        self.assertEqual(command[command.index("--setting-sources") + 1], "project,local")
        self.assertEqual(command[command.index("--max-budget-usd") + 1], "1.50")
        self.assertNotIn("bypassPermissions", command)
        # The fixture's Stop hook reads the session transcript; without one every case is BLOCKED.
        self.assertNotIn("--no-session-persistence", command)
        # Agents and the reviewer prefix commands with `cd "<project>" &&`.
        self.assertIn("Bash(cd:*)", command)

    def test_codex_home_holds_only_a_private_credential_copy_and_fixture_trust(self):
        from harness import codex_home
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as fixture:
            Path(source, "auth.json").write_text('{"token": "secret"}')
            Path(source, "config.toml").write_text('[projects."/"]\ntrust_level = "trusted"\n')
            with codex_home(fixture, source) as home:
                self.assertEqual(sorted(path.name for path in home.iterdir()), ["auth.json", "config.toml"])
                self.assertEqual((home / "auth.json").stat().st_mode & 0o777, 0o600)
                self.assertEqual((home / "auth.json").read_text(), '{"token": "secret"}')
                config = (home / "config.toml").read_text()
                self.assertIn(f'[projects.{json.dumps(os.path.realpath(fixture))}]', config)
                self.assertNotIn('[projects."/"]', config)
                self.assertIn("hooks = true", config)
            self.assertFalse(home.exists())
            with self.assertRaises(SystemExit):
                with codex_home(fixture, Path(source, "missing")):
                    pass

    def test_codex_command_keeps_sessions_and_takes_prompt_on_stdin(self):
        command = agent_command("gpt-test", None, "codex")
        self.assertEqual(command[:3], ["codex", "exec", "--json"])
        # Ignoring user config also drops project trust, so no project hook would load.
        self.assertNotIn("--ignore-user-config", command)
        self.assertEqual(command[command.index("--sandbox") + 1], "workspace-write")
        self.assertEqual(command[command.index("--model") + 1], "gpt-test")
        # Subagent threads, including the reviewer, cannot spawn from an ephemeral session.
        self.assertNotIn("--ephemeral", command)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)
        self.assertEqual(command[-1], "-")
        self.assertEqual(agent_command("sonnet", 1.5), agent_command("sonnet", 1.5, "claude"))

    def test_codex_transcript_maps_items_onto_claude_events_and_sums_tokens(self):
        session = CodexTranscript([
            "not json", json.dumps({"type": "thread.started", "thread_id": "t"}),
            codex_item("e0", "error", message="hook trust bypassed"),
            codex_text("m1", CONTRACT), codex_item("c1", "command_execution", done=False, command="ls"),
            codex_shell("c1", "python3 -m unittest", "FAILED (errors=1)", code=1),
            codex_patch("p1", "/x/calc.py", "/x/tests/test_calc.py"),
            codex_item("w1", "collab_tool_call", tool="wait", prompt=None),
            codex_turn(100, 5), codex_text("m2", "Status: BLOCKED"), codex_turn(40, 2)])
        self.assertEqual(session.provider, "codex")
        self.assertEqual([event["kind"] for event in session.events],
                         ["text", "tool", "tool_result", "tool", "tool", "text"])
        self.assertEqual(session.result_for("c1"), {"kind": "tool_result", "id": "c1", "text": "FAILED (errors=1)",
                                                    "is_error": True})
        self.assertEqual(session.tools("Bash")[0][1]["input"]["command"], "/bin/zsh -lc 'python3 -m unittest'")
        self.assertEqual(session.first_write("calc.py"), 3)
        self.assertEqual(session.first_write("test_calc.py"), 4)
        self.assertEqual(session.final_text, "Status: BLOCKED")
        self.assertEqual(session.tokens, 147)
        self.assertIsNone(session.cost)

    def test_codex_spawns_come_from_the_session_rollout(self):
        thread = "01a145a6-68a4-7d53-b494-67158f10bfef"
        lines = [json.dumps({"type": "thread.started", "thread_id": thread}), codex_text("m1", CONTRACT)]
        with tempfile.TemporaryDirectory() as home:
            self.assertFalse(read_transcript("codex", lines, home).rollout_found)
            day = Path(home, "sessions/2026/10/16")
            day.mkdir(parents=True)
            (day / f"rollout-2026-10-16T23-58-16-{thread}.jsonl").write_text(
                "\n".join(["not json", json.dumps({"type": "session_meta", "payload": {"id": thread}}),
                           rollout_spawn("independent_review", "all"),
                           json.dumps({"type": "response_item", "payload": {"type": "function_call",
                                                                            "name": "wait_agent",
                                                                            "arguments": "{}"}})]))
            session = read_transcript("codex", lines, home)
        self.assertTrue(session.rollout_found)
        self.assertEqual(session.spawns, [{"task_name": "independent_review", "fork_turns": "all"}])
        self.assertIsInstance(read_transcript("claude", [final("x")]), Transcript)

    def test_shell_writes_are_detected_from_the_command_text(self):
        def first_write(command, suffix=None):
            return CodexTranscript([codex_shell("c1", command)]).first_write(suffix)
        for command in ("printf x > calc.py", "echo y >> calc.py", "sed -i.bak s/a/b/ calc.py",
                        "python3 - <<EOF\nopen(\"calc.py\", \"w\").write(src)\nEOF", "cat new.py | tee calc.py"):
            self.assertEqual(first_write(command, "calc.py"), 0, command)
        for command in ("cat calc.py", "python3 -m unittest discover -s tests 2>&1", "ls >/dev/null 2>&1",
                        "grep -n retrun calc.py"):
            self.assertIsNone(first_write(command), command)
        self.assertIsNone(first_write("printf x > tests/test_calc.py", "calc.py"))
        # Claude shell writes count the same way.
        claude = Transcript([assistant(tool("b1", "Bash", command="cat > calc.py <<EOF\nx\nEOF"))])
        self.assertEqual(claude.first_write("calc.py"), 0)

    def test_harness_problems_are_detected_in_raw_lines(self):
        from harness import harness_problems
        self.assertEqual(harness_problems([final("fine")]), [])
        noisy = [json.dumps({"type": "system", "subtype": "hook_response",
                             "output": "Gate evidence: Contract transcript unreadable"})]
        self.assertTrue(harness_problems(noisy))
        self.assertTrue(harness_problems(["Contract transcript unreadable: /tmp/x"]))
        self.assertTrue(harness_problems([codex_item("e1", "error", message="transcript unreadable")]))
        # The agent printing a script that mentions the fault is not a harness fault.
        source = 'echo "Contract transcript unreadable: $transcript"'
        self.assertEqual(harness_problems([result("t1", source), assistant(text(source)),
                                           codex_shell("c1", "sed -n 1,200p gate.sh", source),
                                           codex_text("m1", source)]), [])


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
        block = "Contract:\ntopic: multiply\nrisk: LOW\nquality: STANDARD\nacceptance: tests pass\n\nPlan."
        self.assertEqual(self.check(cases.contract_first, [assistant(text(block))]), [])
        placeholder = "Contract:\nrisk: LOW\nquality: STANDARD\nacceptance: <observable check>"
        self.assertTrue(self.check(cases.contract_first, [assistant(text(placeholder))]))

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

    def test_requests_input_accepts_a_question_or_a_plain_request(self):
        grade = cases.requests_input
        self.assertEqual(self.check(grade, [final("Which convention should I use?")]), [])
        self.assertEqual(self.check(grade, [final("I need the naming convention, or an old-to-new mapping.")]), [])
        self.assertEqual(self.check(grade, [final("Once you send the convention, I'll do the rename.")]), [])
        self.assertTrue(self.check(grade, [final("Renamed everything to camelCase.")]))

    def test_reviewer_dispatch(self):
        hit = [assistant(tool("a1", "Agent", subagent_type="reviewer", prompt="review"))]
        self.assertEqual(self.check(cases.reviewer_dispatched, hit), [])
        miss = [assistant(tool("a1", "Agent", subagent_type="general-purpose", prompt="review"))]
        self.assertTrue(self.check(cases.reviewer_dispatched, miss))
        # Claude must use the named type; a prompt mention is not enough.
        mention = [assistant(tool("a1", "Agent", prompt="act as the reviewer"))]
        self.assertTrue(self.check(cases.reviewer_dispatched, mention))

    def check_codex(self, grader, lines):
        return grader(CodexTranscript(lines), self.root)

    def test_codex_reviewer_dispatch_needs_a_fresh_review_spawn(self):
        grade, text = cases.reviewer_dispatched, [codex_text("m1", CONTRACT)]
        self.assertEqual(grade(codex_session(text, rollout_spawn("independent_review")), self.root), [])
        self.assertEqual(grade(codex_session(text, rollout_spawn("review", "all"), rollout_spawn("Reviewer")),
                               self.root), [])
        forked = grade(codex_session(text, rollout_spawn("independent_review", "all")), self.root)
        self.assertEqual(forked, ["reviewer was spawned with fork_turns=all, so it saw the author's reasoning"])
        self.assertEqual(grade(codex_session(text, rollout_spawn("implement_owner")), self.root),
                         ["no `reviewer` subagent was dispatched"])
        self.assertTrue(grade(CodexTranscript(text), self.root)[0].startswith("HARNESS:"))

    def test_codex_contract_and_regression_order(self):
        good = [codex_text("m1", CONTRACT + "\nPlan."), codex_patch("p1", "calc.py")]
        self.assertEqual(self.check_codex(cases.contract_first, good), [])
        late = [codex_shell("c1", "printf x > calc.py"), codex_text("m1", CONTRACT)]
        self.assertIn("contract line came after the first file write", self.check_codex(cases.contract_first, late))
        run = "python3 -m unittest discover -s tests -t ."
        order = [codex_patch("p1", "/p/tests/test_calc.py"), codex_shell("c1", run, "FAILED (errors=1)", code=1),
                 codex_patch("p2", "/p/calc.py"), codex_shell("c2", run, "OK")]
        grade = cases.failing_test_before_fix("calc.py")
        self.assertEqual(self.check_codex(grade, order), [])
        self.assertTrue(self.check_codex(grade, [order[2], *order[:2], order[3]]))


class ResultsDirectoryTests(unittest.TestCase):
    def test_runs_started_in_the_same_second_get_separate_directories(self):
        import run_evals
        with tempfile.TemporaryDirectory() as base:
            stamp = "20261017T000000Z"
            first = run_evals.new_results_dir(Path(base), stamp, "claude")
            second = run_evals.new_results_dir(Path(base), stamp, "codex")
            third = run_evals.new_results_dir(Path(base), stamp, "codex")
            self.assertEqual(len({first, second, third}), 3)
            self.assertTrue(all(path.is_dir() and path.parent == Path(base) for path in (first, second, third)))
            self.assertEqual(second.name, f"{stamp}-codex")


class CaseTableTests(unittest.TestCase):
    def test_cases_are_named_uniquely_and_graded(self):
        names = [case["name"] for case in cases.CASES]
        self.assertEqual(len(names), len(set(names)))
        for case in cases.CASES:
            self.assertTrue(case["prompt"] and case["graders"], case["name"])


if __name__ == "__main__":
    unittest.main()
