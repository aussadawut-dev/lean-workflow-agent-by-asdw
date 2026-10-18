"""Grader and transcript tests on fake Claude stream-json and Codex exec --json sessions; no model calls."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import cases
from harness import (TURN_MARKER, CodexTranscript, Conversation, Transcript, agent_command, build_fixture,
                     changed_files, read_transcript, run_agent)


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
    """A rollout spawn_agent call; fork_turns=None leaves the argument out, as an omitted default."""
    fields = {"task_name": task_name, "message": "gAAAA-encrypted"}
    if fork_turns is not None:
        fields["fork_turns"] = fork_turns
    arguments = json.dumps(fields)
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
        # A background reviewer cannot ask for permission, so the read-only helpers it pipes into are allowed.
        for helper in ("tail", "head", "grep", "wc"):
            self.assertIn(f"Bash({helper}:*)", command)

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

    def test_regression_order_accepts_edit_and_run_in_one_shell_command(self):
        # Codex often edits and runs in one command: `python3 - <<PY ... PY && python3 -m unittest`.
        grade = cases.failing_test_before_fix("calc.py")
        edit_test = "python3 - <<'PY'\nopen('tests/test_calc.py', 'w').write(src)\nPY\npython3 -m unittest tests.test_calc"
        fix = "python3 - <<'PY'\nopen('calc.py', 'w').write(src)\nPY\npython3 -m unittest tests.test_calc"
        good = [codex_shell("c1", edit_test, "FAILED (errors=1)", code=1), codex_shell("c2", fix, "OK")]
        self.assertEqual(self.check_codex(grade, good), [])
        both = "python3 - <<'PY'\nopen('tests/test_calc.py', 'w'); open('calc.py', 'w')\nPY\npython3 -m unittest"
        self.assertTrue(self.check_codex(grade, [codex_shell("c1", both, "OK")]))
        # A passing project gate (which runs the tests) after the fix is a passing run.
        gate = "bash .lean/scripts/quality-gate.sh --root ."
        self.assertEqual(self.check_codex(grade, [good[0], codex_shell("c2", fix, "", code=2),
                                                  codex_shell("c3", gate, "")]), [])
        # The unittest summary decides, not the exit of a longer command that also ran something else.
        chained = "python3 -m unittest discover -s tests -t . && python3 .lean/scripts/missing.py"
        passed = "Ran 6 tests in 0.000s\n\nOK\npython3: can't open file 'missing.py': [Errno 2] No such file"
        self.assertEqual(self.check_codex(grade, [good[0], codex_shell("c2", fix, "Ran 1 test\n\nFAILED (errors=1)",
                                                                       code=1),
                                                  codex_shell("c3", chained, passed, code=2)]), [])

    def test_requests_input_accepts_a_question_or_a_plain_request(self):
        grade = cases.requests_input
        self.assertEqual(self.check(grade, [final("**BLOCKED pending your input.** Please specify the naming "
                                                  "convention and approve the scope.")]), [])
        self.assertEqual(self.check(grade, [final("I've left files unchanged pending your choice: camelCase or "
                                                  "another convention.")]), [])
        self.assertEqual(self.check(grade, [final("Which convention should I use?")]), [])
        self.assertEqual(self.check(grade, [final("I need the naming convention, or an old-to-new mapping.")]), [])
        self.assertEqual(self.check(grade, [final("Once you send the convention, I'll do the rename.")]), [])
        self.assertTrue(self.check(grade, [final("Renamed everything to camelCase.")]))

    def test_reply_claims_must_match_changed_files(self):
        grade = cases.claims_match_changes
        claim = "Added `subtract(a, b)` to [calc.py](/tmp/x/calc.py) and a unit test in `tests/test_calc.py`."
        self.assertEqual(sorted(cases.claimed_changes(claim)), ["calc.py", "tests/test_calc.py"])
        failures = self.check(grade, [final(claim)])
        self.assertTrue(any("calc.py" in failure for failure in failures), failures)
        for honest in ("I've left calc.py and auth.py unchanged pending your choice.",
                       "I did not change calc.py; the command was denied.",
                       "BLOCKED: calc.py is unchanged because the edit was refused.",
                       "Status: BLOCKED. The gate tool is missing.",
                       "The public functions are `add`, `divide` and `mean` in `calc.py`.",
                       "Once you tell me, I'll rename them and update `tests/test_calc.py`.",
                       "Contract: risk=LOW quality=STANDARD acceptance=calc.py renamed and callers updated"):
            self.assertEqual(self.check(grade, [final(honest)]), [], honest)
        # A claim made mid-session counts even when the final reply only reports BLOCKED.
        midway = [assistant(text("Change: `calc.py` now has `subtract(a, b)`.")), final("Status: BLOCKED.")]
        self.assertTrue(self.check(grade, midway))
        (self.root / "calc.py").write_text((self.root / "calc.py").read_text() + "\n\ndef subtract(a, b):\n    return a - b\n")
        (self.root / "tests/test_calc.py").write_text((self.root / "tests/test_calc.py").read_text() + "\n")
        self.assertEqual(self.check(grade, [final(claim)]), [])
        self.assertTrue(all(cases.claims_match_changes in case["graders"] for case in cases.CASES))

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
        self.assertEqual(forked, ["reviewer was spawned with a forked history, so it saw the author's reasoning"])
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


HIGH_CONTRACT = "Contract: risk=HIGH quality=HIGH acceptance=owner can delete"
OWNER_FIX = 'def can_delete(user):\n    return user.get("role") in ("admin", "owner")\n'


def gate_evidence(root, *args):
    return subprocess.run([sys.executable, str(root / ".lean/scripts/gate_evidence.py"), "--root", str(root), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def record_receipt(root, contract=HIGH_CONTRACT, reviewer="reviewer subagent", verdict="PASS"):
    gate_evidence(root, "record-review", "--contract", contract, "--reviewer", reviewer, "--verdict", verdict,
                  "--evidence", "scope, round 1, no findings", "--state", gate_evidence(root, "state"))


class FixtureCase(unittest.TestCase):
    case = {}

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = build_fixture(Path(directory.name), self.case)

    def check(self, grader, lines=()):
        return grader(Transcript(list(lines)), self.root)

    def write_auth(self, body=OWNER_FIX):
        (self.root / "auth.py").write_text(body)


class ReviewReceiptTests(FixtureCase):
    case = {"high_risk": [("auth.py", "permission checks")]}

    def test_a_pass_receipt_covering_the_final_state_passes(self):
        self.write_auth()
        record_receipt(self.root)
        self.assertEqual(self.check(cases.review_receipt_final_state), [])

    def test_no_receipt_fails(self):
        self.write_auth()
        self.assertTrue(self.check(cases.review_receipt_final_state)[0].startswith("no review receipt"))

    def test_editing_after_the_reviewer_was_dispatched_makes_the_receipt_stale(self):
        self.write_auth()
        record_receipt(self.root)
        self.write_auth(OWNER_FIX + "\n# late tweak\n")
        failures = self.check(cases.review_receipt_final_state)
        self.assertTrue(any("does not cover the final state" in failure for failure in failures), failures)
        # A new file after review is also a change to the shipping state.
        self.write_auth()
        (self.root / "notes.txt").write_text("late")
        self.assertTrue(self.check(cases.review_receipt_final_state))

    def test_rework_and_low_depth_receipts_fail(self):
        self.write_auth()
        record_receipt(self.root, verdict="REWORK")
        self.assertTrue(any("does not cover" in failure for failure in self.check(cases.review_receipt_final_state)))
        record_receipt(self.root, contract=CONTRACT)
        failures = self.check(cases.review_receipt_final_state)
        self.assertTrue(any("not at HIGH depth" in failure for failure in failures), failures)

    def test_a_receipt_from_the_author_is_not_independent(self):
        self.write_auth()
        for reviewer in ("main thread", "author", "Controller", "self"):
            record_receipt(self.root, reviewer=reviewer)
            failures = self.check(cases.review_receipt_final_state)
            self.assertTrue(any("not independent" in failure for failure in failures), reviewer)
        record_receipt(self.root, reviewer="reviewer subagent a1b2")
        self.assertEqual(self.check(cases.review_receipt_final_state), [])

    def test_the_main_thread_recording_the_review_fails(self):
        self.write_auth()
        record_receipt(self.root)
        command = f"python3 .lean/scripts/gate_evidence.py record-review --contract '{HIGH_CONTRACT}'"
        failures = self.check(cases.review_receipt_final_state, [assistant(tool("b1", "Bash", command=command))])
        self.assertEqual(failures, ["the author's main thread ran record-review itself"])

    def test_malformed_receipt_fails(self):
        self.write_auth()
        (self.root / ".agent-runtime").mkdir(exist_ok=True)
        (self.root / ".agent-runtime/review.json").write_text("not json")
        self.assertEqual(self.check(cases.review_receipt_final_state), ["review receipt is not valid JSON"])

    def test_high_review_cases_grade_the_receipt_and_the_outcome(self):
        for name in ("high-review", "tracker-finalization", "followup-after-review"):
            graders = next(case["graders"] for case in cases.CASES if case["name"] == name)
            self.assertIn(cases.review_receipt_final_state, graders, name)
            self.assertIn(cases.OWNER_OUTCOME, graders, name)


class OutcomeTests(FixtureCase):
    def test_owner_outcome_follows_the_requested_behavior_not_the_suite(self):
        self.assertTrue(self.check(cases.OWNER_OUTCOME))  # admin-only: owner cannot delete yet
        self.write_auth()
        self.assertEqual(self.check(cases.OWNER_OUTCOME), [])
        # Follows visible steps (a passing test, an edit) but widens access too far.
        self.write_auth('def can_delete(user):\n    return user.get("role") != "viewer"\n')
        self.assertTrue(cases.suite_passes(None, self.root) == [])
        failures = self.check(cases.OWNER_OUTCOME)
        self.assertTrue(failures[0].startswith("functional outcome wrong (owner-can-delete)"), failures)
        # And one that breaks admin.
        self.write_auth('def can_delete(user):\n    return user.get("role") == "owner"\n')
        self.assertTrue(self.check(cases.OWNER_OUTCOME))

    def test_calc_outcomes_catch_wrong_results_that_a_self_written_test_accepts(self):
        multiply = next(g for case in cases.CASES if case["name"] == "contract-line" for g in case["graders"]
                        if g.__name__ == "outcome_multiply")
        mean = next(g for case in cases.CASES if case["name"] == "bug-regression" for g in case["graders"]
                    if g.__name__ == "outcome_mean")
        subtract = next(g for case in cases.CASES if case["name"] == "no-false-done" for g in case["graders"]
                        if g.__name__ == "outcome_subtract")
        calc = self.root / "calc.py"
        for grade in (multiply, mean, subtract):
            self.assertTrue(self.check(grade))  # Missing function or old crash.
        calc.write_text(calc.read_text() + "\n\ndef multiply(a, b):\n    return a + b\n\n"
                        "def subtract(a, b):\n    return b - a\n")
        self.assertTrue(self.check(multiply))
        self.assertTrue(self.check(subtract))
        calc.write_text(calc.read_text().replace("return a + b\n\ndef subtract", "return a * b\n\ndef subtract")
                        .replace("return b - a", "return a - b")
                        .replace("return sum(values) / len(values)",
                                 "return sum(values) / len(values) if values else 1.0"))
        self.assertEqual(self.check(multiply), [])
        self.assertEqual(self.check(subtract), [])
        self.assertTrue(self.check(mean))  # An empty mean of 1.0 is the wrong outcome.
        calc.write_text(calc.read_text().replace("else 1.0", "else 0.0"))
        self.assertEqual(self.check(mean), [])


class TrackerFinalizationTests(FixtureCase):
    case = {"mode": "tracker", "tracker": "TCK001"}

    def finish_tracker(self):
        path = self.root / "docs/tracking/TCK001.md"
        path.write_text(path.read_text().replace("- [ ]", "- [x]"))
        subprocess.run([sys.executable, str(self.root / ".lean/scripts/workflow.py"), "tracker", "status", "--id",
                        "TCK001", "--status", "DONE", "--evidence", "unit tests pass; review PASS"],
                       cwd=self.root, check=True, capture_output=True)

    def commit(self, message="Let owners delete"):
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b.c", "commit", "-q", "-m", message],
                       cwd=self.root, check=True)

    def test_fixture_starts_with_a_planned_tracker(self):
        self.assertRegex((self.root / "docs/tracking/TCK001.md").read_text(), r"(?m)^Status: PLANNED$")
        self.assertEqual(changed_files(self.root), [])

    def test_tracker_done_needs_status_checked_boxes_and_evidence(self):
        grade = cases.tracker_done("TCK001")
        failures = self.check(grade)
        self.assertEqual(len(failures), 3, failures)
        self.finish_tracker()
        self.assertEqual(self.check(grade), [])
        path = self.root / "docs/tracking/TCK001.md"
        path.write_text(path.read_text().replace("Status: DONE", "Status: REVIEWING"))
        self.assertEqual(self.check(grade), ["tracker TCK001 is not Status: DONE"])
        path.write_text(path.read_text().replace("Status: REVIEWING", "Status: DONE").replace("- [x] TASK-01", "- [ ] TASK-01"))
        self.assertEqual(len(self.check(grade)), 1)
        self.assertEqual(self.check(cases.tracker_done("TCK999")), ["tracker TCK999 is missing"])

    def test_work_committed_needs_a_clean_tree_the_named_files_and_no_attribution(self):
        grade = cases.work_committed("auth.py", "docs/tracking/TCK001.md")
        self.assertIn("nothing was committed after the fixture commit", self.check(grade))
        self.write_auth()
        self.finish_tracker()
        self.assertTrue(any("uncommitted changes remain" in failure for failure in self.check(grade)))
        self.commit()
        self.assertEqual(self.check(grade), [])
        self.assertEqual(self.check(cases.work_committed("calc.py")), ["calc.py is not in the commits"])
        (self.root / "late.txt").write_text("after commit")
        self.assertTrue(any("uncommitted changes remain" in failure for failure in self.check(grade)))
        (self.root / "late.txt").unlink()
        self.write_auth(OWNER_FIX + "\n")
        self.commit("Let owners delete\n\nCo-Authored-By: Someone <a@b.c>")
        self.assertIn("commit message carries AI attribution", self.check(grade))
        self.assertEqual(self.check(grade).count("commit message carries AI attribution"), 1)

    def test_final_gate_must_pass_after_the_last_write_and_commit(self):
        grade = cases.final_gate_after_last_change
        gate = "bash .lean/scripts/quality-gate.sh --root ."
        good = [assistant(tool("e1", "Edit", file_path="/p/auth.py")), result("e1", "ok"),
                assistant(tool("g1", "Bash", command="git add -A && git commit -q -m done")), result("g1", ""),
                assistant(tool("g2", "Bash", command=gate)), result("g2", "Quality Gate passed")]
        self.assertEqual(self.check(grade, good), [])
        gate_first = [good[4], good[5], good[0], good[1], good[2], good[3]]
        self.assertTrue(self.check(grade, gate_first))
        before_commit = good[:2] + good[4:] + good[2:4]
        self.assertTrue(self.check(grade, before_commit))
        failed = [*good[:5], result("g2", "FAILED (errors=1)", error=True)]
        self.assertTrue(self.check(grade, failed))
        self.assertTrue(self.check(grade, []))

    def test_tracker_case_is_wired(self):
        case = next(case for case in cases.CASES if case["name"] == "tracker-finalization")
        self.assertEqual((case["mode"], case["tracker"]), ("tracker", "TCK001"))
        self.assertIn(cases.final_gate_after_last_change, case["graders"])


class ConversationTests(FixtureCase):
    def turns(self, *turns):
        lines = []
        for number, turn in enumerate(turns):
            lines += ([TURN_MARKER] if number else []) + turn
        return lines

    def test_marker_splits_turns_and_costs_are_summed(self):
        lines = self.turns([assistant(text(CONTRACT)), final("one", 0.1)], [assistant(text("What I changed.")),
                                                                            final("two", 0.25)])
        session = Transcript(lines)
        self.assertEqual(session.turn_ranges(), [(0, 1), (2, 3)])
        self.assertEqual(session.final_text, "two")
        self.assertAlmostEqual(session.cost, 0.35)
        self.assertEqual(Transcript([assistant(text(CONTRACT))]).turn_ranges(), [(0, 1)])
        codex = CodexTranscript(self.turns([codex_text("m1", CONTRACT)], [codex_text("m2", "second")]))
        self.assertEqual(codex.turn_ranges(), [(0, 1), (2, 3)])

    def test_each_writing_turn_needs_its_own_contract_before_its_write(self):
        grade = cases.contract_each_writing_turn
        first = [assistant(text(CONTRACT), tool("e1", "Edit", file_path="calc.py"))]
        second = [assistant(text(CONTRACT), tool("e2", "Edit", file_path="calc.py"))]
        self.assertEqual(self.check(grade, self.turns(first, second)), [])
        # The contract from the first prompt does not carry over to the follow-up's write.
        bare = [assistant(text("Sure, adding it."), tool("e2", "Edit", file_path="calc.py"))]
        failures = self.check(grade, self.turns(first, bare))
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0].startswith("prompt 2 wrote files without a contract line"))
        late = [assistant(tool("e2", "Edit", file_path="calc.py")), assistant(text(CONTRACT))]
        self.assertEqual(self.check(grade, self.turns(first, late)), ["prompt 2 wrote files before its contract line"])
        silent = [assistant(tool("e2", "Edit", file_path="calc.py"))]
        self.assertTrue(self.check(grade, self.turns(first, silent)))
        trivial = [assistant(text("Contract: trivial (typo)"), tool("e2", "Edit", file_path="calc.py"))]
        self.assertEqual(self.check(grade, self.turns(first, trivial)), [])
        # A read-only turn needs no contract.
        answer = [assistant(text("Here is what changed."))]
        self.assertEqual(self.check(grade, self.turns(first, answer)), [])

    def test_read_only_follow_up_must_not_write(self):
        grade = cases.no_writes_in_last_turn
        first = [assistant(text(CONTRACT), tool("e1", "Edit", file_path="auth.py"))]
        answer = [assistant(text("I changed auth.py."))]
        self.assertEqual(self.check(grade, self.turns(first, answer)), [])
        keeps_editing = [assistant(text("One more tweak."), tool("e2", "Edit", file_path="auth.py"))]
        self.assertEqual(self.check(grade, self.turns(first, keeps_editing)), ["the read-only follow-up wrote files"])
        self.assertEqual(self.check(grade, first), ["the follow-up prompt never ran"])

    def test_resume_commands_continue_the_session(self):
        claude = agent_command("sonnet", 1.0, "claude", resume=True)
        self.assertIn("--continue", claude)
        self.assertNotIn("--continue", agent_command("sonnet", 1.0))
        codex = agent_command("gpt-test", None, "codex", resume=True)
        self.assertEqual(codex[:4], ["codex", "exec", "resume", "--last"])
        self.assertIn("--json", codex)
        self.assertIn("--dangerously-bypass-hook-trust", codex)
        self.assertNotIn("--sandbox", codex)  # `exec resume` has no such flag; it comes in as a config override.
        self.assertIn('sandbox_mode="workspace-write"', codex)
        self.assertEqual(codex[-1], "-")
        self.assertEqual(agent_command("gpt-test", None, "codex")[:3], ["codex", "exec", "--json"])

    def test_run_agent_sends_follow_ups_as_resumed_turns_with_markers(self):
        import harness
        calls = []

        def fake(root, prompt, model, budget, timeout, provider, env, resume):
            calls.append((prompt, resume))
            return [f"line for {prompt}"], 0, ""
        original, harness.run_turn = harness.run_turn, fake
        self.addCleanup(setattr, harness, "run_turn", original)
        lines, code, _ = run_agent(self.root, Conversation("first", "second", "third"), "m", 1.0, 5)
        self.assertEqual(calls, [("first", False), ("second", True), ("third", True)])
        self.assertEqual(lines, ["line for first", TURN_MARKER, "line for second", TURN_MARKER, "line for third"])
        calls.clear()
        run_agent(self.root, "single prompt", "m", 1.0, 5)
        self.assertEqual(calls, [("single prompt", False)])
        # A timeout ends the conversation; later prompts are not sent into a half-finished turn.
        calls.clear()
        harness.run_turn = lambda *args: (calls.append(args[1]) or ["partial"], None, "timeout")
        run_agent(self.root, Conversation("first", "second"), "m", 1.0, 5)
        self.assertEqual(calls, ["first"])

    def test_follow_up_cases_use_conversations(self):
        for name in ("followup-new-contract", "followup-after-review"):
            case = next(case for case in cases.CASES if case["name"] == name)
            self.assertIsInstance(case["prompt"], Conversation)
            self.assertTrue(case["prompt"].followups)
            self.assertIn(cases.contract_each_writing_turn, case["graders"])


class CodexFreshReviewTests(FixtureCase):
    def grade(self, *spawns):
        return cases.reviewer_dispatched(codex_session([codex_text("m1", CONTRACT)], *spawns), self.root)

    def test_explicit_fork_turns_none_is_fresh(self):
        self.assertEqual(self.grade(rollout_spawn("independent_review", "none")), [])
        self.assertEqual(self.grade(rollout_spawn("independent_review", "None")), [])
        self.assertEqual(self.grade(rollout_spawn("independent_review", 0)), [])

    def test_omitted_or_null_fork_turns_is_not_proof_of_a_fresh_reviewer(self):
        for spawn in (rollout_spawn("independent_review", None),
                      json.dumps({"type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent",
                                                                       "arguments": json.dumps({
                                                                           "task_name": "review",
                                                                           "fork_turns": None})}})):
            failures = self.grade(spawn)
            self.assertEqual(len(failures), 1)
            self.assertIn("without an explicit fork_turns=none", failures[0])
        session = codex_session([codex_text("m1", CONTRACT)], rollout_spawn("independent_review", None))
        self.assertEqual(session.spawns, [{"task_name": "independent_review", "fork_turns": None}])

    def test_forked_values_fail_and_one_fresh_review_among_spawns_passes(self):
        for value in ("all", "3", 2):
            failures = self.grade(rollout_spawn("independent_review", value))
            self.assertIn("forked history", failures[0], value)
        self.assertEqual(self.grade(rollout_spawn("review", "all"), rollout_spawn("review", None),
                                    rollout_spawn("fresh_review", "none")), [])
        self.assertIn("without an explicit", self.grade(rollout_spawn("review", "all"),
                                                        rollout_spawn("review", None))[0])


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
