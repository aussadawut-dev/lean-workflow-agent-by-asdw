"""Port of the 4.x bash hook suite (test-hooks.sh): gate runs, session hook, contract and risk cases.

Skipped 4.x intent with no v5 counterpart: shellcheck of the hook .sh files and their executability
(the hooks are now the `lean` CLI)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import commit, git, install, lean, stop_refusal  # noqa: E402

PROJECT_HEAD = "# Project Context\n\n## Purpose\n\nNot defined yet.\n\n"
LOW = "Contract: risk=LOW quality=STANDARD acceptance=tests pass"
HUMAN = {"type": "user", "message": {"content": "please change file"}}
SAID = {"type": "assistant", "message": {"content": [{"type": "text", "text": LOW}]}}
EDIT = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Edit", "input": {}}]}}
DECLARE = "python3 .lean/bin/lean contract declare --contract '{}'"


def text_entry(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def environment(root):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    env.pop("LEAN_GATE_FORCE", None)
    env.pop("LEAN_GATE_LOCK_FD", None)
    return env


class HookCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean hook cases ")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.count = 0

    def scratch(self, name="dir"):
        self.count += 1
        path = self.work / f"{name}{self.count}"
        path.mkdir()
        return path

    def fixture(self, *gate_lines):
        """New installed repo whose PROJECT.md gate block holds the given lines."""
        root = self.scratch("repo")
        install(root)
        block = "<!-- gate:start -->\n```sh\n" + "".join(line + "\n" for line in gate_lines) + "```\n<!-- gate:end -->\n"
        (root / ".lean/PROJECT.md").write_text(PROJECT_HEAD + block)
        git(root, "init", "-q")
        commit(root, "init")
        return root

    def risky_fixture(self):
        root = self.fixture("true")
        project = root / ".lean/PROJECT.md"
        project.write_text(project.read_text() + "\n## High-risk areas\n\n- `secure/`: auth boundary.\n"
                           "- `deploy/*.yml`: production config.\n\n## Other\n\n- `not/listed/`\n")
        commit(root, "areas")
        return root

    def stop(self, root, payload, cache=True):
        args = ["hook", "claude", "stop"] + (["--cache-tree"] if cache else [])
        return stop_refusal(lean(root, *args, input=payload if isinstance(payload, str) else json.dumps(payload),
                                 env=environment(root)))

    def run_gate(self, root, payload):
        """Fixture setup accepts the edited controls, then runs the Claude Stop adapter."""
        accepted = lean(root, "evidence", "accept-controls", "--reason", "Fixture intentionally selected these controls")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        return self.stop(root, payload)

    def run_raw(self, root, payload):
        return self.stop(root, payload, cache=False)

    def seed(self, root):
        return lean(root, "hook", "claude", "session-start", input="{}", env=environment(root))

    def session(self, root):
        return lean(root, "hook", "claude", "session-start", input="", env=environment(root))

    def evidence(self, root, *args):
        return lean(root, "evidence", *args)

    def runs(self, counter):
        return len(counter.read_text().splitlines())

    def write(self, root, name, text):
        (root / name).write_text(text)

    def replace_in_project(self, root, old, new):
        project = root / ".lean/PROJECT.md"
        project.write_text(project.read_text().replace(old, new))

    def transcript(self, *entries):
        self.count += 1
        path = self.work / f"transcript{self.count}.jsonl"
        path.write_text("\n".join(e if isinstance(e, str) else json.dumps(e) for e in entries) + "\n")
        return str(path)

    def payload(self, path, active=False):
        return {"stop_hook_active": active, "transcript_path": path}


class GateBasics(HookCase):
    def test_no_project_md_is_undefined(self):
        root = self.scratch("empty")
        install(root)
        git(root, "init", "-q")
        self.assertEqual(self.run_gate(root, "{}").returncode, 2)

    def test_empty_block_is_undefined(self):
        root = self.fixture()
        self.write(root, "file.txt", "change\n")
        self.assertEqual(self.run_gate(root, "{}").returncode, 2)

    def test_refusal_is_json_decision_block_on_exit_0(self):
        root = self.fixture("false")
        self.write(root, "file.txt", "change\n")
        accepted = lean(root, "evidence", "accept-controls", "--reason", "Fixture intentionally selected these controls")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        raw = lean(root, "hook", "claude", "stop", "--cache-tree", input="{}", env=environment(root))
        self.assertEqual(raw.returncode, 0, raw.stderr)
        data = json.loads(raw.stdout)
        self.assertEqual(data["decision"], "block")
        self.assertIn("Quality Gate failed", data["reason"])

    def test_failing_command_blocks_and_names_it(self):
        root = self.fixture("false")
        self.write(root, "file.txt", "change\n")
        result = self.run_gate(root, {"stop_hook_active": False})
        self.assertEqual(result.returncode, 2)
        self.assertIn("Quality Gate failed: false", result.stderr)

    def test_unchanged_continued_refusal_is_released_unverified(self):
        root = self.fixture("false")
        self.write(root, "file.txt", "change\n")
        self.run_gate(root, {"stop_hook_active": False})
        first = self.run_gate(root, {"stop_hook_active": True, "session_id": "s"})
        self.assertEqual(first.returncode, 2, "a refusal first shown to this session blocks")
        released = self.run_gate(root, {"stop_hook_active": True, "session_id": "s"})
        self.assertEqual(released.returncode, 0, "an unchanged continued refusal is released at once")
        self.assertIn("UNVERIFIED", json.loads(released.stdout)["systemMessage"])
        self.assertTrue((root / ".agent-runtime/gate-failed").is_file())
        self.assertFalse((root / ".agent-runtime/gate-cache").exists(), "a release caches nothing")
        warn = self.run_gate(root, {"stop_hook_active": False, "session_id": "s"})
        self.assertEqual(warn.returncode, 0, "a fresh Stop with nothing changed only warns")
        self.write(root, "file.txt", "again\n")
        again = self.run_gate(root, {"stop_hook_active": False, "session_id": "s"})
        self.assertEqual(again.returncode, 2, "a fresh Stop after a change is gated again")
        self.assertEqual((root / ".agent-runtime/gate-failed").read_text().strip(), "1",
                         "a fresh refusal restarts the count")

    def test_committed_work_is_still_gated(self):
        root = self.fixture("false")
        self.write(root, "code.txt", "change\n")
        commit(root, "work")
        self.assertEqual(self.run_gate(root, "{}").returncode, 2)

    def test_seed_is_not_proof_a_failing_gate_passes(self):
        root = self.fixture("false")
        self.seed(root)
        self.assertEqual(self.run_gate(root, "{}").returncode, 2)
        self.write(root, "code.txt", "change\n")
        self.assertEqual(self.run_gate(root, "{}").returncode, 2, "seeded then changed runs")

    def test_seed_records_baseline_without_validating(self):
        counter = self.work / "seeded"
        counter.write_text("")
        root = self.fixture(f"echo run >> '{counter}'")
        self.seed(root)
        self.assertGreater((root / ".agent-runtime/gate-baseline").stat().st_size, 0)
        self.assertEqual(counter.read_text(), "")
        self.assertFalse((root / ".agent-runtime/gate-cache").exists())

    def test_ignores_comments_and_blank_lines(self):
        root = self.fixture("# comment", "", "true")
        self.write(root, "file.txt", "change\n")
        self.assertEqual(self.run_gate(root, "{}").returncode, 0)

    def test_pass_is_cached_and_change_reruns(self):
        counter = self.work / "count"
        counter.write_text("")
        root = self.fixture(f"echo run >> '{counter}'")
        self.write(root, "file.txt", "change\n")
        self.assertEqual(self.run_gate(root, "{}").returncode, 0, "passing command exits 0")
        self.run_gate(root, "{}")
        self.assertEqual(self.runs(counter), 1, "cache skips unchanged tree")
        self.write(root, "file.txt", "other\n")
        self.run_gate(root, "{}")
        self.assertEqual(self.runs(counter), 2, "change re-runs")


class GateState(HookCase):
    def test_stops_at_first_failure(self):
        counter = self.work / "count"
        counter.write_text("")
        root = self.fixture("false", f"echo run >> '{counter}'")
        self.write(root, "file.txt", "change\n")
        result = self.run_gate(root, "{}")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.runs(counter), 0)

    def test_session_suggests_lean_init_when_empty(self):
        root = self.fixture()
        self.assertIn("/lean-init", self.session(root).stdout)

    def test_session_silent_when_filled(self):
        root = self.fixture("true")
        self.replace_in_project(root, "Not defined yet.", "A real project.")
        self.write(root, ".lean/config.json", '{"mode":"standard","configured":true}\n')
        out = self.session(root).stdout
        self.assertEqual(out.strip(), "", out)

    def test_session_mode_prompt(self):
        prompt = "choose standard, tracker, or full"
        root = self.fixture()
        self.write(root, ".lean/config.json", '{"mode":"standard","configured":false}\n')
        self.assertIn(prompt, self.session(root).stdout, "prompts for mode before initial setup")
        self.write(root, ".lean/config.json", '{"mode":"tracker","configured":true}\n')
        self.assertNotIn(prompt, self.session(root).stdout, "no mode prompt after setup")
        missing = self.fixture()
        (missing / ".lean/config.json").unlink(missing_ok=True)
        self.assertIn(prompt, self.session(missing).stdout, "prompts when config is missing")

    def test_session_records_the_change_baseline(self):
        root = self.fixture("false")
        (root / ".agent-runtime/gate-cache").unlink(missing_ok=True)
        self.session(root)
        self.assertGreater((root / ".agent-runtime/gate-baseline").stat().st_size, 0)

    def test_every_commit_is_gated(self):
        counter = self.work / "count"
        counter.write_text("")
        root = self.fixture(f"echo run >> '{counter}'")
        self.seed(root)
        for n in (1, 2):
            self.write(root, "code.txt", f"change {n}\n")
            commit(root, f"work {n}")
            self.run_gate(root, "{}")
        self.assertEqual(self.runs(counter), 2)

    def test_a_further_edit_to_a_tracked_file_reruns(self):
        counter = self.work / "count"
        counter.write_text("")
        root = self.fixture(f"echo run >> '{counter}'")
        self.write(root, "t.txt", "first\n")
        commit(root, "add-t")
        self.write(root, "t.txt", "second\n")
        self.run_gate(root, "{}")
        self.write(root, "t.txt", "third\n")
        self.run_gate(root, "{}")
        self.assertEqual(self.runs(counter), 2)

    def test_editing_the_gate_commands_reruns(self):
        counter = self.work / "count"
        counter.write_text("")
        root = self.fixture(f"echo run >> '{counter}'")
        self.write(root, "code.txt", "change\n")
        self.run_gate(root, "{}")
        self.replace_in_project(root, "echo run >> ", "echo edited >> ")
        self.run_gate(root, "{}")
        self.assertEqual(self.runs(counter), 2)

    def test_a_seed_does_not_bless_a_refused_state(self):
        root = self.fixture("false")
        self.write(root, "code.txt", "broken\n")
        self.assertEqual(self.run_gate(root, "{}").returncode, 2, "refuses broken work")
        self.seed(root)
        self.assertEqual(self.run_gate(root, "{}").returncode, 2)

    def test_a_seed_does_not_bless_refused_committed_work(self):
        root = self.fixture("false")
        self.write(root, "code.txt", "broken\n")
        commit(root, "broken")
        self.assertEqual(self.run_gate(root, "{}").returncode, 2, "refuses committed broken work")
        self.seed(root)
        self.assertEqual(self.run_gate(root, "{}").returncode, 2)

    def test_a_refusal_is_recorded_and_a_pass_clears_it(self):
        flag = self.work / "flag"
        root = self.fixture(f"test -f '{flag}'")
        self.write(root, "code.txt", "change\n")
        self.assertEqual(self.run_gate(root, "{}").returncode, 2)
        self.assertTrue((root / ".agent-runtime/gate-failed").is_file())
        flag.write_text("")
        self.assertEqual(self.run_gate(root, "{}").returncode, 0)
        self.assertFalse((root / ".agent-runtime/gate-failed").exists())

    def test_a_new_empty_untracked_file_reruns(self):
        counter = self.work / "count"
        counter.write_text("")
        root = self.fixture(f"echo run >> '{counter}'")
        self.write(root, "code.txt", "change\n")
        self.run_gate(root, "{}")
        self.write(root, "appeared.txt", "")
        self.run_gate(root, "{}")
        self.assertEqual(self.runs(counter), 2)

    def test_the_gate_commands_are_part_of_the_state(self):
        # With PROJECT.md ignored by git, only the commands themselves can reveal an edit to it.
        counter = self.work / "count"
        counter.write_text("")
        root = self.fixture(f"echo run >> '{counter}'")
        with open(root / ".gitignore", "a") as handle:
            handle.write(".lean/PROJECT.md*\n")
        git(root, "rm", "-q", "--cached", ".lean/PROJECT.md")
        commit(root, "ignore PROJECT.md")
        self.write(root, "code.txt", "change\n")
        self.run_gate(root, "{}")
        self.replace_in_project(root, "echo run >> ", "echo edited >> ")
        self.run_gate(root, "{}")
        self.assertEqual(self.runs(counter), 2)


class GateFailures(HookCase):
    def test_seed_writes_no_cache_while_a_refusal_stands_and_cache_does_not_override(self):
        root = self.fixture("false")
        self.write(root, "code.txt", "broken\n")
        self.run_gate(root, "{}")
        self.seed(root)
        self.assertFalse((root / ".agent-runtime/gate-cache").exists())
        ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", ".agent-runtime/gate-failed"])
        self.assertEqual(ignored.returncode, 0, "the refusal marker is invisible to the state")
        (root / ".agent-runtime/gate-failed").unlink()
        self.seed(root)
        (root / ".agent-runtime/gate-failed").write_text("")
        self.assertEqual(self.run_gate(root, "{}").returncode, 2, "a matching cache does not override a refusal")

    def test_a_missing_program_says_the_gate_could_not_run(self):
        root = self.fixture("lean-no-such-tool --check")
        self.seed(root)
        self.write(root, "code.txt", "change\n")
        result = self.run_gate(root, "{}")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Quality Gate could not run: lean-no-such-tool --check", result.stderr)
        self.assertIn("not a failure your change caused", result.stderr)
        self.assertNotIn("If your change caused this", result.stderr)
        self.assertTrue((root / ".agent-runtime/gate-failed").is_file())
        self.assertFalse((root / ".agent-runtime/gate-cache").exists())

    def test_a_real_failure_keeps_the_failure_message(self):
        root = self.fixture(f"test -f '{self.work}/never-created'")
        self.write(root, "code.txt", "change\n")
        result = self.run_gate(root, "{}")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Quality Gate failed: test -f", result.stderr)
        self.assertIn("If your change caused this", result.stderr)
        self.assertNotIn("could not run", result.stderr)

    def test_a_missing_script_is_a_failure_not_an_environment_problem(self):
        root = self.fixture("./scripts/gone.sh")
        self.write(root, "code.txt", "change\n")
        result = self.run_gate(root, "{}")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Quality Gate failed: ./scripts/gone.sh", result.stderr)

    def test_a_present_wrapper_is_a_failure_not_a_missing_tool(self):
        root = self.fixture("bash scripts/lint.sh")
        (root / "scripts").mkdir()
        self.write(root, "scripts/lint.sh", "#!/usr/bin/env bash\n./tools/lint-tool --check\n")
        self.write(root, "code.txt", "change\n")
        result = self.run_gate(root, "{}")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Quality Gate failed: bash scripts/lint.sh", result.stderr)

    def test_an_assignment_does_not_hide_a_missing_program(self):
        root = self.fixture("LEAN_TEST=1 lean-no-such-tool --check")
        self.write(root, "code.txt", "change\n")
        result = self.run_gate(root, "{}")
        self.assertEqual(result.returncode, 2)
        self.assertIn("'lean-no-such-tool' is not available", result.stderr)

    def test_a_quoted_assignment_fragment_is_not_called_a_missing_tool(self):
        root = self.fixture('LEAN_OPTS="-a b" bash scripts/lint.sh')
        (root / "scripts").mkdir()
        self.write(root, "scripts/lint.sh", "#!/usr/bin/env bash\n./tools/lint-tool --check\n")
        self.write(root, "code.txt", "change\n")
        result = self.run_gate(root, "{}")
        self.assertEqual(result.returncode, 2)
        self.assertIn('Quality Gate failed: LEAN_OPTS="-a b" bash scripts/lint.sh', result.stderr)
        self.assertNotIn("could not run", result.stderr)

    def test_a_status_other_than_127_is_a_failure_whatever_the_first_word_is(self):
        root = self.fixture("lean-no-such-tool ; false")
        self.write(root, "code.txt", "change\n")
        result = self.run_gate(root, "{}")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Quality Gate failed: lean-no-such-tool ; false", result.stderr)

    def test_an_option_is_not_reported_as_a_missing_tool(self):
        root = self.fixture("  -x code.txt")
        self.write(root, "code.txt", "change\n")
        result = self.run_gate(root, "{}")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Quality Gate failed:   -x code.txt", result.stderr)

    def test_distinct_untracked_file_boundaries_invalidate_a_passing_cache(self):
        root = self.fixture('test "$(cat a)" = A')
        self.write(root, "a", "A")
        self.write(root, "b", "BC")
        self.assertEqual(self.run_gate(root, "{}").returncode, 0, "initial untracked boundary fixture passes")
        self.write(root, "a", "AB")
        self.write(root, "b", "C")
        self.assertEqual(self.run_gate(root, "{}").returncode, 2, "redistributed untracked bytes rerun and fail")


class ContractCases(HookCase):
    def contract_case(self, want, *entries):
        root = self.fixture("true")
        self.write(root, "file.txt", "change\n")
        result = self.run_gate(root, self.payload(self.transcript(*entries)))
        self.assertEqual(result.returncode, want, result.stderr)
        return result

    def test_contract_line_forms(self):
        cases = (
            ("real assistant Contract line passes", 0, text_entry(LOW + "\nDone")),
            ("trivial form passes", 0, text_entry("Contract: trivial (typo)")),
            ("missing line blocks", 2, text_entry("Done.")),
            ("template placeholders do not count", 2, text_entry(
                "Contract: risk=<LOW|MEDIUM|HIGH> quality=<STANDARD|HIGH|VERY_HIGH> acceptance=<observable check>"
                " / Contract: trivial (<reason>)")),
            ("a line in a user entry does not count", 2, {"type": "user", "message": {"content": LOW}}),
            ("a line inside tool_use input does not count", 2, {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Edit", "input": {"new_string": LOW}}]}}),
            ("a contract after prose is not a first line", 2, text_entry(
                'say "hi"\nContract: risk=LOW quality=STANDARD acceptance=x ok')),
        )
        for label, want, entry in cases:
            with self.subTest(label):
                self.contract_case(want, entry)

    def test_unreadable_transcript_blocks_with_a_diagnostic(self):
        root = self.fixture("true")
        self.write(root, "file.txt", "change\n")
        result = self.run_gate(root, self.payload("/nonexistent/t.jsonl"))
        self.assertEqual(result.returncode, 2)

    def test_block_message_is_specific(self):
        result = self.contract_case(2, {"type": "assistant", "message": {"content": "x"}})
        self.assertIn("No Task Contract first line", result.stderr)

    def test_a_contract_refusal_is_not_inherited_by_a_chat_only_session(self):
        root = self.fixture("true")
        path = self.transcript(text_entry("hi"))
        self.write(root, "file.txt", "change\n")
        self.assertEqual(self.run_gate(root, self.payload(path)).returncode, 2, "first refusal")
        self.assertEqual((root / ".agent-runtime/gate-failed").read_text().strip(), "c1",
                         "marker is a contract marker")
        self.assertEqual(self.run_gate(root, self.payload(path, True)).returncode, 2, "continued refusal (2nd)")
        self.assertEqual(self.run_gate(root, self.payload(path, True)).returncode, 2, "continued refusal (3rd)")
        released = self.run_gate(root, self.payload(path, True))
        self.assertEqual(released.returncode, 0, "released after three refusals")
        self.assertTrue((root / ".agent-runtime/gate-failed").read_text().startswith("c"),
                        "a released refusal stays a contract refusal")
        commit(root, "change")
        lean(root, "hook", "claude", "session-start", input="", env=environment(root))
        self.assertFalse((root / ".agent-runtime/gate-failed").exists(), "seed clears a contract marker")
        self.assertEqual(self.run_gate(root, self.payload(path)).returncode, 0,
                         "chat-only follow-up session is not blocked")

    def test_missing_transcript_path_is_not_checked(self):
        root = self.fixture("true")
        self.write(root, "file.txt", "change\n")
        self.assertEqual(self.run_gate(root, {"stop_hook_active": False}).returncode, 0)

    def test_runtime_injected_user_entries_are_not_human_turns(self):
        meta = lambda text: {"type": "user", "isMeta": True, "message": {"content": [{"type": "text", "text": text}]}}
        cases = (
            ("a loaded skill body does not end the turn", 0,
             (HUMAN, SAID, meta("Base directory for this skill: x"), EDIT)),
            ("Stop hook feedback cannot excuse an earlier write", 2,
             (HUMAN, EDIT, meta("Stop hook feedback: no contract"), SAID)),
            ("a task notification does not end the turn", 0,
             (HUMAN, SAID, {"type": "user", "message": {"content": "<task-notification> <task-id>a1</task-id> </task-notification>"}}, EDIT)),
            ("a compaction summary does not end the turn", 0,
             (HUMAN, SAID, {"type": "user", "isCompactSummary": True, "message": {"content": "This session is being continued"}}, EDIT)),
            ("a new human prompt still needs a new contract", 2,
             (HUMAN, SAID, {"type": "user", "message": {"content": "now change it again"}}, EDIT)),
        )
        for label, want, entries in cases:
            with self.subTest(label):
                self.contract_case(want, *entries)


class RiskCases(HookCase):
    def test_low_contract_in_a_high_risk_area_needs_a_high_depth_review_receipt(self):
        path = self.transcript(SAID)
        root = self.risky_fixture()
        (root / "secure").mkdir()
        self.write(root, "secure/auth.py", "x\n")
        result = self.run_gate(root, self.payload(path))
        self.assertEqual(result.returncode, 2, "a LOW contract in a high-risk area needs a review receipt")
        self.assertRegex(result.stderr, r"High-risk areas changed[\s\S]*secure/auth\.py")
        state = self.evidence(root, "state")
        recorded = self.evidence(root, "record-review", "--contract", LOW, "--reviewer", "independent",
                                 "--evidence", "round 1, no findings", "--verdict", "PASS",
                                 "--state", state.stdout.strip())
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(self.run_gate(root, self.payload(path)).returncode, 2,
                         "a matching LOW receipt cannot satisfy the independent HIGH-depth floor")
        high = "Contract: risk=HIGH quality=HIGH acceptance=tests pass"
        state = self.evidence(root, "state")
        recorded = self.evidence(root, "record-review", "--contract", high, "--reviewer", "independent",
                                 "--evidence", "HIGH-depth review, no findings", "--verdict", "PASS",
                                 "--state", state.stdout.strip())
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(self.run_gate(root, self.payload(path)).returncode, 0,
                         "a current HIGH-depth receipt satisfies the floor under a LOW task contract")

    def test_paths_outside_high_risk_areas_keep_the_contract_depth(self):
        path = self.transcript(SAID)
        root = self.risky_fixture()
        self.write(root, "elsewhere.txt", "x\n")
        (root / "not/listed").mkdir(parents=True)
        self.write(root, "not/listed/f", "x\n")
        self.assertEqual(self.run_gate(root, self.payload(path)).returncode, 0)

    def test_glob_areas_match(self):
        path = self.transcript(SAID)
        root = self.risky_fixture()
        (root / "deploy").mkdir()
        self.write(root, "deploy/prod.yml", "x\n")
        self.assertEqual(self.run_gate(root, self.payload(path)).returncode, 2)

    def test_work_committed_during_the_session_still_counts(self):
        path = self.transcript(SAID)
        root = self.risky_fixture()
        self.seed(root)
        (root / "secure").mkdir()
        self.write(root, "secure/auth.py", "x\n")
        commit(root, "risky")
        self.assertEqual(self.run_gate(root, self.payload(path)).returncode, 2)

    def test_a_high_risk_change_without_any_contract_is_refused(self):
        root = self.risky_fixture()
        (root / "secure").mkdir()
        self.write(root, "secure/auth.py", "x\n")
        self.assertEqual(self.run_gate(root, {"stop_hook_active": False}).returncode, 2)

    def test_a_chat_only_turn_over_an_inherited_high_risk_change_is_not_refused(self):
        root = self.risky_fixture()
        (root / "secure").mkdir()
        self.write(root, "secure/auth.py", "x\n")
        self.seed(root)
        path = self.transcript(text_entry("hi"))
        self.assertEqual(self.run_gate(root, self.payload(path)).returncode, 0)

    def test_a_nested_lean_root_still_sees_tracked_high_risk_edits(self):
        outer = self.scratch("outer")
        git(outer, "init", "-q")
        root = outer / "app"
        (root / "secure").mkdir(parents=True)
        install(root)
        source = self.risky_fixture()
        self.write(root, ".lean/PROJECT.md", (source / ".lean/PROJECT.md").read_text())
        self.write(root, "secure/auth.py", "old\n")
        commit(outer, "init")
        self.write(root, "secure/auth.py", "new\n")
        path = self.transcript(SAID)
        self.assertEqual(self.run_gate(root, self.payload(path)).returncode, 2)

    def test_changed_controls_refuse_and_an_unchanged_refusal_is_released_at_once(self):
        root = self.fixture("true")
        self.assertEqual(self.run_raw(root, {"stop_hook_active": False}).returncode, 0, "first use records controls")
        self.replace_in_project(root, "\ntrue\n", "\ntest -d .\n")
        self.assertEqual(self.run_raw(root, {"stop_hook_active": False, "session_id": "s"}).returncode, 2,
                         "changed controls refuse")
        released = self.run_raw(root, {"stop_hook_active": True, "session_id": "s"})
        self.assertEqual(released.returncode, 0)
        self.assertIn("UNVERIFIED", released.stdout)

    def test_reviewed_changed_controls_are_accepted(self):
        root = self.fixture("true")
        self.assertEqual(self.run_raw(root, {"stop_hook_active": False}).returncode, 0)
        self.replace_in_project(root, "\ntrue\n", "\ntest -d .\n")
        high = "Contract: risk=HIGH quality=HIGH acceptance=fixture"
        bound = lean(root, "hook", "claude", "pre-tool", input=json.dumps({
            "session_id": "s2", "tool_name": "Bash", "tool_input": {"command": DECLARE.format(high)}}))
        self.assertEqual(bound.returncode, 0, bound.stderr)
        state = self.evidence(root, "state").stdout.strip()
        recorded = self.evidence(root, "record-review", "--contract", high, "--reviewer", "r",
                                 "--evidence", "e", "--verdict", "PASS", "--state", state)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        result = self.run_raw(root, {"stop_hook_active": False, "session_id": "s2"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS review", result.stderr)

    def test_an_undefined_gate_refuses_and_is_released_at_once_when_unchanged(self):
        root = self.fixture("true")
        (root / ".lean/PROJECT.md").unlink()
        self.assertEqual(self.run_raw(root, {"stop_hook_active": False, "session_id": "s"}).returncode, 2)
        self.assertEqual(self.run_raw(root, {"stop_hook_active": True, "session_id": "s"}).returncode, 0)

    def test_seed_never_records_a_refusal(self):
        root = self.fixture("true")
        (root / ".lean/PROJECT.md").unlink()
        lean(root, "hook", "claude", "session-start", input="", env=environment(root))
        self.assertFalse((root / ".agent-runtime/gate-failed").exists())


if __name__ == "__main__":
    unittest.main()
