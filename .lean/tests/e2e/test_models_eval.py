"""`lean models eval|apply|bank` with fake provider CLIs: scoring, budget, tokens, timeouts, resume, proposal."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, install, lean  # noqa: E402
from lean import evals, models  # noqa: E402
from lean.util import LeanError  # noqa: E402

FAKE = r'''#!{python}
"""Fake provider CLI. FAKE_<MODEL> picks the behaviour: solve | nothing | sleep | deny | silent."""
import json, os, shutil, sys, time
from pathlib import Path
name = Path(sys.argv[0]).name
model = sys.argv[sys.argv.index("--model" if "--model" in sys.argv else "-m") + 1]
mode = os.environ.get("FAKE_" + model.upper().replace("-", "_").replace(".", "_"), "nothing")
if mode == "sleep":
    time.sleep(30)
if mode in ("solve", "slow", "solvedeny"):
    if mode == "slow":
        time.sleep(1)
    bank = Path(os.environ["FAKE_BANK"])
    for size in os.listdir(bank):
        reference = bank / size / "reference"
        if reference.is_dir() and all((Path.cwd() / p.relative_to(reference)).exists()
                                      for p in reference.rglob("*.py")):
            shutil.copytree(reference, Path.cwd(), dirs_exist_ok=True)
            break
def size_here():
    """The task size of this repository: the size whose task files all exist here (the largest such set)."""
    bank, best = Path(os.environ["FAKE_BANK"]), (0, None)
    for size in os.listdir(bank):
        task = bank / size / "task"
        files = [p.relative_to(task) for p in task.rglob("*.py")] if task.is_dir() else []
        if files and all((Path.cwd() / f).exists() for f in files) and len(files) > best[0]:
            best = (len(files), size)
    return best[1]


count = int(os.environ.get("FAKE_TOKENS_" + str(size_here()), "1234"))
if mode == "silent":
    print("done")
elif name == "codex":
    print(f"did it\ntokens used\n{count:,}")
elif name == "claude":
    print(json.dumps({"result": "ok", "usage": {"input_tokens": 10, "cache_creation_input_tokens": 90,
                                                 "cache_read_input_tokens": 5000, "output_tokens": 100}}))
else:
    denied = [{"action": "command", "display_name": "RunCommand"}] if mode in ("deny", "solvedeny") else []
    print(json.dumps({"status": "SUCCESS", "usage": {"total_tokens": 700, "cache_read_tokens": 200},
                      "denied_actions": denied}))
'''


class EvalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        install(self.root)
        shutil.copytree(ROOT / ".lean/evals", self.root / ".lean/evals")
        shutil.copy2(ROOT / ".lean/models.json", self.root / ".lean/models.json")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for name in ("codex", "claude", "agy"):
            path = self.bin / name
            path.write_text(FAKE.replace("{python}", sys.executable))
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        self.env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}", FAKE_BANK=str(ROOT / ".lean/evals"),
                        ANTHROPIC_API_KEY="must-not-leak")

    def plan(self, candidates, tasks):
        path = self.base / f"plan-{len(list(self.base.glob('plan-*')))}.json"
        path.write_text(json.dumps({"candidates": candidates, "tasks": tasks}))
        return path

    def run_eval(self, candidates, tasks, budget=10**6, out="out", modes=None, **options):
        env = dict(self.env, **(modes or {}))
        options.setdefault("work_root", self.base / "work")
        return evals.evaluate(self.root, self.plan(candidates, tasks), budget, self.base / out, environment=env, **options)

    def test_scores_tokens_and_proposal(self):
        rows, skipped = self.run_eval([{"provider": "codex", "model": "good", "effort": "low"},
                                       {"provider": "claude", "model": "lazy", "effort": "low"}], ["3S", "M"],
                                      modes={"FAKE_GOOD": "solve"})
        by = {(row["model"], row["size"]): row for row in rows}
        self.assertEqual(skipped, [])
        self.assertEqual(by[("good", "3S")]["passed"], by[("good", "3S")]["units"])
        self.assertEqual(by[("good", "M")]["passed"], 30)
        self.assertEqual(by[("lazy", "3S")]["passed"], evals.index()["3S"]["baseline"])
        self.assertEqual(by[("lazy", "M")]["passed"], 0)
        self.assertEqual(by[("good", "3S")]["tokens"], 1234)
        self.assertEqual((by[("lazy", "M")]["tokens"], by[("lazy", "M")]["cache_read"]), (200, 5000))
        self.assertEqual(evals.propose(rows), {"codex": {"3S": {"model": "good", "effort": "low"},
                                                         "M": {"model": "good", "effort": "low"}}})

    def test_token_formats(self):
        self.assertEqual(evals.tokens("codex", "x\ntokens used\n12,345\n"), (12345, None))
        self.assertEqual(evals.tokens("claude", '{"usage": {"input_tokens": 1, "cache_creation_input_tokens": 2, '
                                                '"output_tokens": 3, "cache_read_input_tokens": 9}}'), (6, 9))
        self.assertEqual(evals.tokens("agy", '{"usage": {"total_tokens": 50, "cache_read_tokens": 20}}'), (30, 20))
        for provider in ("codex", "claude", "agy"):
            with self.subTest(provider=provider):
                self.assertEqual(evals.tokens(provider, "no usage here"), (None, None))

    def test_budget_stops_new_runs_and_unknown_counts_are_charged(self):
        rows, skipped = self.run_eval([{"provider": "codex", "model": "good", "effort": "low"}], ["3S", "2S", "S"],
                                      budget=1000, modes={"FAKE_GOOD": "solve"}, jobs=1, estimate=1000)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(skipped), 2)
        self.assertGreaterEqual(sum(row["charged"] for row in rows), 1000)
        rows, _ = self.run_eval([{"provider": "codex", "model": "good", "effort": "low"},
                                 {"provider": "codex", "model": "mute", "effort": "low"}], ["3S"], out="unknown",
                                modes={"FAKE_GOOD": "solve", "FAKE_MUTE": "silent"}, jobs=1)
        mute = [row for row in rows if row["model"] == "mute"][0]
        self.assertTrue(mute["tokens_estimated"])
        self.assertEqual(mute["charged"], evals.ESTIMATE, "an unknown count is charged at least the estimate")

    def test_timeout_denial_and_resume(self):
        candidates = [{"provider": "codex", "model": "stuck", "effort": "low"},
                      {"provider": "agy", "model": "blocked", "effort": None}]
        rows, _ = self.run_eval(candidates, ["3S"], modes={"FAKE_STUCK": "sleep", "FAKE_BLOCKED": "deny"}, timeout=1)
        by = {row["model"]: row for row in rows}
        self.assertEqual(by["stuck"]["exit"], "timeout")
        self.assertTrue(by["blocked"]["denied"])
        self.assertEqual(evals.propose(rows), {})
        self.assertIn("permissions.allow", evals.summary(rows, [], 10))
        again, _ = self.run_eval(candidates, ["3S"], modes={"FAKE_STUCK": "sleep", "FAKE_BLOCKED": "deny"}, timeout=1)
        self.assertEqual(len(again), 2, "finished runs are not repeated")

    def test_an_unknown_first_count_is_charged_the_estimate(self):
        rows, skipped = self.run_eval([{"provider": "codex", "model": "mute", "effort": "low"}], ["3S", "2S"],
                                      budget=1500, modes={"FAKE_MUTE": "silent"}, jobs=1, estimate=1000)
        self.assertEqual([row["charged"] for row in rows], [1000])
        self.assertEqual(len(skipped), 1, "a parser that never finds a count must still exhaust the budget")

    def test_reservations_keep_concurrent_runs_inside_the_budget(self):
        rows, skipped = self.run_eval([{"provider": "codex", "model": "a", "effort": "low"},
                                       {"provider": "codex", "model": "b", "effort": "low"},
                                       {"provider": "claude", "model": "c", "effort": "low"}], ["3S"],
                                      budget=1500, modes={"FAKE_A": "slow", "FAKE_B": "slow", "FAKE_C": "slow"},
                                      jobs=4, estimate=1000)
        self.assertEqual((len(rows), len(skipped)), (1, 2))

    def test_a_cheap_first_count_never_shrinks_later_reservations(self):
        # Found in review: 3S runs report 1,000 and 3XL runs 90,000; reserving the largest count seen let the
        # 3XL runs spend 182,000 of a 100,000 budget.
        rows, skipped = self.run_eval([{"provider": "codex", "model": "a", "effort": "low"},
                                       {"provider": "codex", "model": "b", "effort": "low"}], ["3S", "3XL"],
                                      budget=100_000, estimate=50_000, jobs=4,
                                      modes={"FAKE_TOKENS_3S": "1000", "FAKE_TOKENS_3XL": "90000"})
        self.assertLessEqual(sum(row["charged"] for row in rows), 100_000)
        self.assertEqual(len(skipped), 1)

    def test_a_run_waits_for_reservations_instead_of_being_skipped(self):
        rows, skipped = self.run_eval([{"provider": "codex", "model": "a", "effort": "low"},
                                       {"provider": "codex", "model": "b", "effort": "low"}], ["3S"],
                                      budget=100_000, estimate=95_000, jobs=4,
                                      modes={"FAKE_A": "slow", "FAKE_B": "slow", "FAKE_TOKENS_3S": "1000"})
        self.assertEqual((len(rows), skipped), (2, []))

    def test_a_cli_that_never_started_costs_nothing_and_runs_again(self):
        (self.bin / "agy").unlink()
        modes = {"PATH": f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin"}
        rows, _ = self.run_eval([{"provider": "agy", "model": "x", "effort": None}], ["3S"], modes=modes)
        self.assertEqual((rows[0]["exit"], rows[0]["charged"]), ("not-run", 0))
        again, _ = self.run_eval([{"provider": "agy", "model": "x", "effort": None}], ["3S"], modes=modes)
        self.assertEqual(len(again), 1, "the not-run row is retried, not kept as finished")
        self.assertFalse(any((self.base / "work").rglob("shop")), "run copies are removed after grading")

    def test_a_run_that_raises_releases_its_reservation(self):
        # Found in review: an exception between reserve and release left a waiting run blocked for ever.
        real, calls = evals.prepare, []

        def flaky(size, destination, overlay=None):
            calls.append(destination)
            if len(calls) == 1:
                raise OSError("disk full")
            return real(size, destination, overlay)

        outcome = {}

        def run():
            with mock.patch.object(evals, "prepare", flaky):
                outcome["result"] = self.run_eval([{"provider": "codex", "model": "a", "effort": "low"},
                                                   {"provider": "codex", "model": "b", "effort": "low"}], ["3S"],
                                                  budget=100, estimate=60, jobs=2,
                                                  modes={"FAKE_A": "slow", "FAKE_B": "slow", "FAKE_TOKENS_3S": "10"})

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(60)
        self.assertFalse(thread.is_alive(), "the eval hung after a failing run")
        rows, skipped = outcome["result"]
        failed = [row for row in rows if row["exit"] == "not-run"]
        self.assertEqual((len(rows), skipped, len(failed)), (2, [], 1))
        self.assertIn("disk full", failed[0]["grade_error"])
        self.assertEqual(failed[0]["charged"], 0)

    def test_a_waiter_is_woken_even_when_recording_fails(self):
        # Found in review: notify_all came after record(), so an exception there (a closed pipe on print)
        # left the other run waiting for ever.
        real, calls = evals.denied, []

        def flaky(output):
            calls.append(1)
            if len(calls) == 1:
                raise BrokenPipeError
            return real(output)

        outcome = {}

        def run():
            with mock.patch.object(evals, "denied", flaky):
                try:
                    outcome["result"] = self.run_eval([{"provider": "codex", "model": "a", "effort": "low"},
                                                       {"provider": "codex", "model": "b", "effort": "low"}], ["3S"],
                                                      budget=100, estimate=60, jobs=2,
                                                      modes={"FAKE_A": "slow", "FAKE_B": "slow", "FAKE_TOKENS_3S": "10"})
                except BrokenPipeError:
                    outcome["raised"] = True

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(60)
        self.assertFalse(thread.is_alive(), "a waiting run hung after recording failed")

    def test_output_that_is_not_text_still_counts_as_a_started_run(self):
        spy = self.bin / "codex"
        spy.write_text(f"#!{sys.executable}\nimport sys\nsys.stdout.buffer.write(b'\\xff\\n')\n"
                       "print('tokens used\\n5,000')\n")
        rows, _ = self.run_eval([{"provider": "codex", "model": "x", "effort": "low"}], ["3S"])
        self.assertEqual((rows[0]["exit"], rows[0]["tokens"], rows[0]["charged"]), (0, 5000, 5000))
        self.assertTrue((self.base / "out/solutions").is_dir(), "each run's files are kept for review")

    def test_resume_survives_a_truncated_results_line(self):
        self.run_eval([{"provider": "codex", "model": "good", "effort": "low"}], ["3S"], modes={"FAKE_GOOD": "solve"})
        log = self.base / "out/results.jsonl"
        log.write_text(log.read_text() + '{"id": "cut')
        rows, _ = self.run_eval([{"provider": "codex", "model": "good", "effort": "low"}], ["3S"],
                                modes={"FAKE_GOOD": "solve"})
        self.assertEqual(len(rows), 1, "the finished run is not repeated")

    def test_after_stop_no_waiting_run_starts(self):
        # Found in review: runs already waiting for the provider gate or for budget still started after Ctrl-C.
        stop, real, calls = threading.Event(), evals.run_cli, []

        def first_call_stops(*args):
            calls.append(args[0])
            stop.set()  # As if the user pressed Ctrl-C while this run was in flight.
            return real(*args)

        with mock.patch.object(evals, "run_cli", first_call_stops):
            rows, _ = self.run_eval([{"provider": "codex", "model": f"m{i}", "effort": "low"} for i in range(4)], ["3S"],
                                    jobs=4, stop=stop, modes={f"FAKE_M{i}": "slow" for i in range(4)})
        self.assertIn(len(calls), (1, 2), "only runs already past the gate may run")
        self.assertEqual(len(rows), len(calls))

    def test_grading_does_not_see_the_callers_secrets(self):
        spy = self.bin / "codex"
        spy.write_text(f"#!{sys.executable}\nfrom pathlib import Path\n"
                       "Path('shop/__init__.py').write_text(\"import os\\nopen('leak.txt', 'w').write("
                       "os.environ.get('ANTHROPIC_API_KEY', ''))\\n\")\nprint('tokens used\\n1')\n")
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "secret-in-the-callers-environment"}):
            self.run_eval([{"provider": "codex", "model": "x", "effort": "low"}], ["3S"])
        leak = next((self.base / "out/solutions").rglob("leak.txt"))
        self.assertEqual(leak.read_text(), "", "the grader ran the solution with the caller's API key")

    def test_grading_never_raises_on_what_a_candidate_left(self):
        work = self.base / "grading"
        cases = {
            "non-object output": lambda repo: (repo / "shop/pricing.py").write_text(
                "import os\nprint(42, flush=True)\nos._exit(0)\n"),
            "a file where the hidden tests go": lambda repo: (repo / ".lean-eval-hidden").write_text("x"),
        }
        for name, damage in cases.items():
            with self.subTest(case=name):
                repo = evals.prepare("3S", work / name.replace(" ", "-"))
                damage(repo)
                passed, failed, error = evals.grade(repo, "3S")
                if name == "non-object output":
                    self.assertEqual((passed, failed), (0, 0))
                    self.assertTrue(error)
                else:
                    self.assertEqual(passed, evals.index()["3S"]["baseline"])

    def test_an_unknown_count_is_charged_exactly_its_reservation(self):
        rows, _ = self.run_eval([{"provider": "codex", "model": "big", "effort": "low"},
                                 {"provider": "codex", "model": "mute", "effort": "low"}], ["3S"],
                                budget=10**6, estimate=50_000, jobs=2,
                                modes={"FAKE_BIG": "slow", "FAKE_MUTE": "silent", "FAKE_TOKENS_3S": "80000"})
        mute = [row for row in rows if row["model"] == "mute"][0]
        self.assertIn(mute["charged"], (50_000, 80_000))  # Its own reservation: before or after big reported.
        self.assertTrue(mute["tokens_estimated"])

    def test_runs_happen_outside_the_repository_with_eval_flags(self):
        spy = self.bin / "claude"
        spy.write_text(f"#!{sys.executable}\nimport os, sys\nprint('CWD=' + os.getcwd())\nprint('ARGS=' + repr(sys.argv))\n")
        self.run_eval([{"provider": "claude", "model": "x", "effort": "low"}], ["3S"])
        log = next((self.base / "out/logs").glob("*.log")).read_text()
        cwd = Path(log.split("CWD=")[1].splitlines()[0]).resolve()
        self.assertNotIn(self.root.resolve(), [cwd, *cwd.parents])
        self.assertIn("'--allowedTools', 'Bash(python3 -m unittest:*)'", log)

    def test_a_denied_tool_does_not_disqualify_a_full_score(self):
        rows, _ = self.run_eval([{"provider": "agy", "model": "noted", "effort": None}], ["3S"],
                                modes={"FAKE_NOTED": "solvedeny"})
        self.assertTrue(rows[0]["denied"])
        self.assertEqual(evals.propose(rows), {"agy": {"3S": {"model": "noted", "effort": None}}})

    def test_proposal_prefers_the_fastest_full_score(self):
        rows, _ = self.run_eval([{"provider": "codex", "model": "slow", "effort": "high"},
                                 {"provider": "codex", "model": "quick", "effort": "low"}], ["3S"],
                                modes={"FAKE_SLOW": "slow", "FAKE_QUICK": "solve"})
        self.assertEqual(evals.propose(rows)["codex"]["3S"], {"model": "quick", "effort": "low"})

    def test_api_keys_never_reach_the_provider(self):
        spy = self.bin / "codex"
        spy.write_text(f"#!{sys.executable}\nimport os\nprint('KEY=' + os.environ.get('ANTHROPIC_API_KEY', ''))\n"
                       "print('tokens used\\n1')\n")
        self.run_eval([{"provider": "codex", "model": "x", "effort": "low"}], ["3S"])
        log = next((self.base / "out/logs").glob("*.log")).read_text()
        self.assertIn("KEY=\n", log)

    def test_apply_needs_the_approved_digest(self):
        proposal = self.base / "proposal.json"
        proposal.write_text(json.dumps({"codex": {"3S": {"model": "gpt-new", "effort": "low"}}}))
        with self.assertRaises(LeanError):
            evals.apply(self.root, proposal, "0" * 64)
        changes = evals.apply(self.root, proposal, evals.digest(proposal))
        self.assertEqual(len(changes), 1)
        before = (self.root / ".lean/models.json").read_text()
        self.assertEqual(evals.apply(self.root, proposal, evals.digest(proposal)), [])
        self.assertEqual((self.root / ".lean/models.json").read_text(), before, "no change, no rewrite")
        self.assertIn("codex.3S:", changes[0])
        data = models.load(self.root)
        self.assertEqual(data["providers"]["codex"]["tiers"]["3S"], {"model": "gpt-new", "effort": "low"})
        self.assertEqual(models.validate(data), [])
        for bad in ({"gemini": {"S": {"model": "x"}}}, {"codex": {"4XL": {"model": "x"}}}, {"codex": {"S": {"model": ""}}}):
            with self.subTest(bad=bad):
                proposal.write_text(json.dumps(bad))
                with self.assertRaises(LeanError):
                    evals.apply(self.root, proposal, evals.digest(proposal))

    def test_cli_requires_a_budget_and_reports_the_proposal_digest(self):
        plan = self.plan([{"provider": "codex", "model": "good", "effort": "low"}], ["3S"])
        missing = lean(self.root, "models", "eval", "--plan", str(plan), env=self.env)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("--budget", missing.stderr)
        zero = lean(self.root, "models", "eval", "--plan", str(plan), "--budget", "0", env=self.env)
        self.assertEqual(zero.returncode, 2)
        no_estimate = lean(self.root, "models", "eval", "--plan", str(plan), "--budget", "100", "--estimate", "0",
                           env=self.env)
        self.assertEqual(no_estimate.returncode, 2)
        self.assertIn("--estimate", no_estimate.stderr)
        ran = lean(self.root, "models", "eval", "--plan", str(plan), "--budget", "5000", "--out", str(self.base / "cli"),
                   env=dict(self.env, FAKE_GOOD="solve"))
        self.assertEqual(ran.returncode, 0, ran.stderr)
        digest = evals.digest(self.base / "cli/proposal.json")
        self.assertIn(f"sha256 {digest}", ran.stdout)
        self.assertTrue((self.base / "cli/summary.md").is_file())

    def test_invalid_plans_are_refused(self):
        for plan in ({"candidates": []}, {"candidates": [{"provider": "gemini", "model": "x"}]},
                     {"candidates": [{"provider": "codex", "model": "x", "effort": "low"}], "tasks": ["4XL"]}):
            with self.subTest(plan=plan):
                path = self.base / "bad.json"
                path.write_text(json.dumps(plan))
                with self.assertRaises(LeanError):
                    evals.evaluate(self.root, path, 100, self.base / "bad", environment=self.env)


class BankTests(unittest.TestCase):
    def test_every_reference_scores_full_marks_and_every_stub_less(self):
        with tempfile.TemporaryDirectory() as work:
            report = evals.check_bank(Path(work))
        self.assertEqual(list(report), list(models.TIERS))
        for size, (reference, stub, units) in report.items():
            with self.subTest(size=size):
                self.assertEqual(reference, units)
                self.assertLess(stub, units)
                self.assertEqual(stub, evals.index()[size]["baseline"])


if __name__ == "__main__":
    unittest.main()
