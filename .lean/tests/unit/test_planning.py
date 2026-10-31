"""Validation plans explain the real selection without executing or changing state."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, commit, git  # noqa: E402
from lean import evidence, gate, planning, testsel  # noqa: E402
from lean.util import LeanError  # noqa: E402

LOW = "Contract: risk=LOW quality=STANDARD acceptance=focused checks pass"


class PlanningTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in ("unit/test_a.py", "hooks/test_h.py", "e2e/test_e.py"):
            path = self.root / ".lean/tests" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fixture\n")
        (self.root / ".lean/tests/impact.json").write_text(json.dumps({
            "scope": ["src/*", ".lean/*", "docs/*"], "lint_only": ["docs/*"],
            "rules": [{"paths": ["src/a.py"], "tests": ["unit/test_a.py"]}]}))
        (self.root / ".lean/PROJECT.md").write_text(
            "# Project\n<!-- gate:start -->\n```sh\nprintf MUST_NOT_EXECUTE > ran\n```\n<!-- gate:end -->\n"
            "## High-risk areas\n- `src/security/`: protected behavior\n")
        (self.root / ".gitignore").write_text(".agent-runtime/\n")
        (self.root / "src").mkdir()
        (self.root / "src/a.py").write_text("original\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        commit(self.root)
        self.base = git(self.root, "rev-parse", "HEAD")

    def plan(self, **kwargs):
        return planning.plan(self.root, base=self.base, **kwargs)

    def test_selection_matches_real_selector_for_changed_staged_and_untracked_paths(self):
        (self.root / "src/a.py").write_text("changed\n")
        git(self.root, "add", "src/a.py")
        (self.root / "docs").mkdir()
        (self.root / "docs/guide.md").write_text("notes\n")
        result = self.plan(contract=LOW)
        paths = testsel.changed(self.root, self.base)
        self.assertEqual(result["changed_paths"], paths)
        self.assertEqual((result["tests"]["files"], result["tests"]["reason"]), testsel.select(self.root, paths))
        self.assertEqual(result["tests"]["files"], ["unit/test_a.py"])

    def test_unknown_impact_runs_all_tests_instead_of_omitting_checks(self):
        (self.root / "src/new.py").write_text("new behavior\n")
        result = self.plan()
        self.assertEqual(result["tests"]["files"], sorted(testsel.all_files(self.root)))
        self.assertIn("src/new.py", result["tests"]["reason"])

    def test_shipped_map_selection_parity(self):
        paths = [".lean/lean/guard.py", "docs/workflow.md", ".lean/tests/unit/test_testsel.py"]
        with patch.object(testsel, "changed", return_value=paths), patch.object(evidence, "high_risk_changes", return_value=[]):
            value = planning.plan(ROOT, contract=LOW)
        self.assertEqual((value["tests"]["files"], value["tests"]["reason"]), testsel.select(ROOT, paths))

    def test_review_depth_uses_quality_and_changed_high_risk_floor(self):
        for quality, depth in (("STANDARD", "LOW"), ("HIGH", "MEDIUM"), ("VERY_HIGH", "HIGH")):
            value = self.plan(contract=LOW.replace("STANDARD", quality))
            self.assertEqual(value["review"]["depth"], depth)
        (self.root / "src/security").mkdir()
        (self.root / "src/security/key.py").write_text("sensitive\n")
        value = self.plan(contract=LOW)
        self.assertEqual(value["review"]["depth"], "HIGH")
        self.assertTrue(value["review"]["independent"])
        self.assertEqual(value["review"]["high_risk_paths"], ["src/security/key.py"])
        commit(self.root, "risky unpushed commit")
        self.assertEqual(self.plan(contract=LOW)["review"]["depth"], "HIGH")

    def test_missing_stop_tier_is_not_runnable_and_explains_automatic_fallback(self):
        value = self.plan(tier="stop")
        self.assertFalse(value["gate"]["runnable"])
        self.assertEqual(value["gate"]["tier"], "stop")
        self.assertEqual(value["gate"]["commands"], [])
        self.assertEqual(value["gate"]["automatic_stop_tier"], "full")
        self.assertIn("automatic Stop uses the full tier", planning.explain(value))

    def test_defined_stop_tier_uses_only_its_commands(self):
        project = self.root / ".lean/PROJECT.md"
        project.write_text(project.read_text() + "\n<!-- gate:stop:start -->\nprintf fast\n<!-- gate:stop:end -->\n")
        value = self.plan(tier="stop")
        self.assertEqual(value["gate"]["commands"], ["printf fast"])
        self.assertTrue(value["gate"]["runnable"])

    def test_plan_never_executes_commands_or_creates_runtime_locks_or_caches(self):
        def snapshot():
            return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                    for p in self.root.rglob("*") if p.is_file()}
        before = snapshot()
        original = subprocess.run
        def read_only(command, *args, **kwargs):
            self.assertEqual(command[0], "git")
            return original(command, *args, **kwargs)
        with patch.object(subprocess, "run", side_effect=read_only), patch.object(gate, "run", side_effect=AssertionError("gate execution")):
            value = self.plan(contract=LOW, session="preview")
        self.assertEqual(snapshot(), before)
        self.assertFalse((self.root / "ran").exists())
        self.assertFalse((self.root / ".agent-runtime").exists())
        self.assertEqual(value["validation"], "NOT_RUN")
        self.assertIsNone(value["evidence"]["reuse"]["eligible"])

    def test_recorded_pass_does_not_claim_reuse_and_runtime_records_are_unchanged(self):
        runtime = self.root / ".agent-runtime"
        runtime.mkdir()
        result = {"schema": 1, "status": "PASS", "workflow_root": str(self.root),
                  "record_root": str(self.root), "contract": LOW, "require_review": False,
                  "high_risk_review": False, "state": None, "review_state": None, "base": None}
        record = runtime / "gate-result.json"
        record.write_text(json.dumps(result))
        (runtime / "gate-cache").write_text("old cache")
        before = {p.name: p.read_bytes() for p in runtime.iterdir()}
        value = self.plan(contract=LOW)
        self.assertEqual(value["evidence"]["gate"]["recorded_status"], "PASS")
        self.assertEqual(value["evidence"]["reuse"]["status"], "not_assessed")
        self.assertIsNone(value["evidence"]["reuse"]["eligible"])
        self.assertEqual({p.name: p.read_bytes() for p in runtime.iterdir()}, before)

    def test_low_review_depth_does_not_invent_independent_receipt_requirement(self):
        value = self.plan(contract=LOW)
        self.assertEqual(value["review"]["depth"], "LOW")
        self.assertEqual(value["evidence"]["review"]["status"], "not_required")

    def test_existing_high_receipt_is_checked_and_detects_changed_shipping_bytes(self):
        contract = LOW.replace("risk=LOW", "risk=HIGH")
        runtime = self.root / ".agent-runtime"
        runtime.mkdir()
        receipt = {"schema": 1, "contract": contract, "reviewer": "separate reviewer", "verdict": "PASS",
                   "evidence": "fixture review", "state": evidence.review_state(self.root),
                   "base": evidence.head_tree(self.root)}
        record = runtime / "review.json"
        record.write_text(json.dumps(receipt))
        before = record.read_bytes()
        self.assertEqual(self.plan(contract=contract)["evidence"]["review"]["status"], "covered")
        (self.root / "src/a.py").write_text("changed since review\n")
        value = self.plan(contract=contract)
        self.assertEqual(value["evidence"]["review"]["status"], "not_covered")
        self.assertIn("shipping state changed", value["evidence"]["review"]["reason"])
        self.assertEqual(record.read_bytes(), before)

    def test_bound_contract_is_read_without_updating_session_or_creating_lock(self):
        runtime = self.root / ".agent-runtime"
        runtime.mkdir()
        record = runtime / "contract-sessions.json"
        record.write_text(json.dumps({"schema": 1, "sessions": {"preview": {"contract": LOW}}}))
        before = record.read_bytes()
        value = self.plan(session="preview")
        self.assertEqual(value["contract"], LOW)
        self.assertEqual(value["review"]["depth"], "LOW")
        self.assertEqual(record.read_bytes(), before)
        self.assertFalse((runtime / "contract-sessions.lock").exists())

    def test_active_target_is_separate_and_workspace_base_never_crosses_repositories(self):
        app = self.root / "targets/app"
        app.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(app)], check=True)
        (app / "main.py").write_text("application\n")
        records = self.root / ".lean/targets/app"
        (records / ".lean").mkdir(parents=True)
        project = records / ".lean/PROJECT.md"
        project.write_text("<!-- gate:start -->\napp-test\n<!-- gate:end -->\n")
        context = {"workflow_root": str(self.root), "project_root": str(app), "record_root": str(records),
                   "project_file": str(project), "target": "app"}
        original = testsel.changed
        calls = []
        def changed(root, base=None):
            calls.append((root, base))
            return original(root, base)
        with patch.object(planning.target, "context", return_value=context), patch.object(evidence, "high_risk_changes", return_value=[]), patch.object(testsel, "changed", side_effect=changed):
            value = self.plan()
        self.assertEqual(calls, [(self.root, self.base), (app, None)])
        self.assertEqual(value["target"]["gate"]["commands"], ["app-test"])
        self.assertEqual(value["target"]["gate"]["cwd"], str(app))
        self.assertEqual(value["gate"]["cwd"], str(self.root))
        self.assertEqual(value["target"]["tests"]["status"], "not_assessed")
        self.assertEqual(value["target"]["changed_paths"], ["main.py"])

    def test_invalid_target_or_contract_refuses_instead_of_silently_lowering_scope(self):
        with self.assertRaises(LeanError):
            self.plan(contract="Contract: invalid")
        runtime = self.root / ".agent-runtime"
        runtime.mkdir()
        (runtime / "active-target.json").write_text('{"schema": 1, "name": "missing"}')
        with self.assertRaises(ValueError):
            self.plan()


if __name__ == "__main__":
    unittest.main()
