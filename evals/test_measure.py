import contextlib
import io
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

import measure

RESULTS = Path(__file__).resolve().parent / "measurements"


def art(arm="a", kind="template", run=1, outcome="correct", tokens=100, cost=None, seconds=10.0, **meta):
    base = {"provider": "claude", "model": "m", "runtime": "r1", "revision": "v1"}
    base.update(meta)
    return {"schema": measure.SCHEMA, "synthetic": True, "case": "c", "run": run,
            "arm": {"name": arm, "kind": kind}, "meta": base, "outcome": outcome, "tokens": tokens,
            "cost_usd": cost, "seconds": seconds, "tool_turns": 4, "user_exchanges": 1}


def cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = measure.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class AggregateTests(unittest.TestCase):
    def rows(self, items, group_by=()):
        return measure.aggregate([measure.validate(item) for item in items], group_by)

    def test_counts_and_means(self):
        rows = self.rows([art(run=1, tokens=100, seconds=10.0), art(run=2, outcome="false_success", tokens=300, seconds=20.0),
                          art(run=3, outcome="blocked", tokens=None, seconds=0.0)])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["runs"], row["correct"], row["false_success"], row["blocked"]), (3, 1, 1, 1))
        self.assertEqual(row["tokens"], {"runs_reporting": 2, "total": 400, "mean": 200.0})
        self.assertEqual(row["seconds"]["mean"], 10.0)
        self.assertAlmostEqual(row["correct_rate"], 0.3333, places=4)

    def test_missing_cost_is_null_not_zero(self):
        row = self.rows([art(cost=None), art(run=2, cost=None)])[0]
        self.assertIsNone(row["cost_usd"]["total"])
        self.assertEqual(row["cost_usd"]["runs_reporting"], 0)
        partial = self.rows([art(cost=0.5), art(run=2, cost=None)])[0]
        self.assertEqual(partial["cost_usd"], {"runs_reporting": 1, "total": 0.5, "mean": 0.5})
        self.assertIn("(1/2 runs)", measure.render_table([partial]))
        self.assertIn("n/a", measure.render_table([row]))

    def test_template_and_local_arms_stay_separate(self):
        rows = self.rows([art(arm="x", kind="template"), art(arm="x", kind="local-settings")])
        self.assertEqual([(r["arm"], r["arm_kind"], r["runs"]) for r in rows],
                         [("x", "local-settings", 1), ("x", "template", 1)])

    def test_metadata_mismatch_refused_unless_grouped(self):
        items = [art(revision="v1"), art(run=2, revision="v2")]
        with self.assertRaises(measure.MeasureError) as caught:
            self.rows(items)
        self.assertIn("revision", str(caught.exception))
        rows = self.rows(items, ("revision",))
        self.assertEqual([r["revision"] for r in rows], ["v1", "v2"])
        with self.assertRaises(measure.MeasureError):
            self.rows(items, ("bogus",))

    def test_report_is_deterministic(self):
        first = cli("report", str(RESULTS), "--json")
        self.assertEqual(first, cli("report", str(RESULTS), "--json"))
        self.assertEqual(first[0], 0)


class SampleTests(unittest.TestCase):
    def test_sample_artifacts_report(self):
        code, out, _ = cli("report", str(RESULTS))
        self.assertEqual(code, 0)
        self.assertIn("[SYNTHETIC]", out)
        self.assertIn("local-settings", out)

    def test_cli_refuses_mixed_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            for index, rev in enumerate(("v1", "v2")):
                (Path(directory) / f"{index}.json").write_text(json.dumps(art(run=index, revision=rev)))
            code, _, err = cli("report", directory)
            self.assertEqual(code, 2)
            self.assertIn("--group-by", err)
            self.assertEqual(cli("report", directory, "--group-by", "revision")[0], 0)


class ValidationTests(unittest.TestCase):
    def test_rejects_paths_and_free_text(self):
        for bad in ("/Users/me/x", "has space", "../up", ""):
            with self.assertRaises(measure.MeasureError):
                measure.validate(art(arm=bad))
        with self.assertRaises(measure.MeasureError):
            measure.validate(art(model="a/b"))

    def test_rejects_bad_kind_outcome_numbers(self):
        with self.assertRaises(measure.MeasureError):
            measure.validate(art(kind="other"))
        with self.assertRaises(measure.MeasureError):
            measure.validate(art(outcome="great"))
        with self.assertRaises(measure.MeasureError):
            measure.validate(art(tokens=-1))

    def test_unknown_fields_dropped(self):
        item = art()
        item["prompt"] = "secret prompt"
        self.assertNotIn("prompt", measure.validate(item))


SECRET = "sk-ant-SECRET-TOKEN /Users/alice/private prompt text"


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.report = {
            "provider": "claude", "model": "m", "requested_runs": 3, "partial": False,
            "runs": [
                {"case": "c1", "run": 1, "passed": True, "failures": [], "exit_code": 0, "cost_usd": 0.5,
                 "tokens": None, "seconds": 12.5, "changed_files": ["/Users/alice/private/calc.py"],
                 "fixture": "/tmp/lean eval c1 xyz"},
                {"case": "c1", "run": 2, "passed": False, "failures": [f"wrong: {SECRET}"], "exit_code": 0,
                 "cost_usd": None, "tokens": None, "seconds": 20.0, "changed_files": [], "fixture": None},
                {"case": "c1", "run": 3, "passed": False, "failures": ["HARNESS: session output contains 'x'"],
                 "exit_code": None, "cost_usd": None, "tokens": None, "seconds": 900.0, "changed_files": [],
                 "fixture": None},
            ]}
        (self.root / "report.json").write_text(json.dumps(self.report))
        events = [
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": SECRET},
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": f"cat {SECRET}"}},
                {"type": "tool_use", "id": "t2", "name": "AskUserQuestion", "input": {"question": SECRET}}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "All done, tests pass."}]}},
            {"type": "result", "result": "All done, tests pass.", "total_cost_usd": 9.0,
             "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100}},
        ]
        (self.root / "c1#2.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
        self.out = self.root / "out"

    def extract(self):
        return cli("extract", str(self.root / "report.json"), "--out", str(self.out), "--arm", "tpl-a",
                   "--arm-kind", "template", "--runtime", "claude-9.9", "--revision", "abc1234")

    def test_extract_sanitizes_and_classifies(self):
        code, _, err = self.extract()
        self.assertEqual(code, 0, err)
        files = sorted(self.out.glob("*.json"))
        self.assertEqual(len(files), 3)
        text = "".join(path.read_text() for path in files)
        for leaked in ("SECRET", "/Users", "alice", "/tmp", "private", "sk-ant", "calc.py", "prompt"):
            self.assertNotIn(leaked, text)
        by_run = {json.loads(p.read_text())["run"]: json.loads(p.read_text()) for p in files}
        self.assertEqual(by_run[1]["outcome"], "correct")
        self.assertEqual(by_run[1]["cost_usd"], 0.5)
        self.assertIsNone(by_run[1]["tool_turns"])  # no raw session saved for run 1
        self.assertEqual(by_run[2]["outcome"], "false_success")  # failed graders, claimed completion
        self.assertEqual((by_run[2]["tool_turns"], by_run[2]["user_exchanges"]), (2, 2))
        self.assertEqual(by_run[2]["tokens"], 115)
        self.assertEqual(by_run[2]["cost_usd"], 9.0)
        self.assertEqual(by_run[3]["outcome"], "blocked")
        self.assertEqual(cli("report", str(self.out))[0], 0)

    def test_extract_without_session_marks_failure_incorrect(self):
        (self.root / "c1#2.jsonl").unlink()
        self.extract()
        data = json.loads((self.out / "tpl-a--c1--2.json").read_text())
        self.assertEqual(data["outcome"], "incorrect")
        self.assertIsNone(data["tokens"])


if __name__ == "__main__":
    unittest.main()
