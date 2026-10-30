"""Read-only public receipt readiness and final HIGH-floor regressions."""
import json
from pathlib import Path
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from target_support import TargetFixture  # noqa: E402

HIGH = "Contract: risk=HIGH quality=HIGH acceptance=preflight fixture passes"
LOW = "Contract: risk=LOW quality=STANDARD acceptance=preflight fixture passes"
VERY_HIGH = "Contract: risk=LOW quality=VERY_HIGH acceptance=preflight fixture passes"


class GatePreflightTests(TargetFixture):
    def preflight(self, *args):
        return self.command(sys.executable, self.lean, "gate", "preflight", *args)

    def project(self, risk=False):
        path = self.root / ".lean/PROJECT.md"
        path.write_text("# Fixture\n<!-- gate:start -->\n"
                        "printf 'run\\n' >> .agent-runtime/check-runs\n<!-- gate:end -->\n"
                        + ("\n## High-risk areas\n- `risky.txt`\n" if risk else ""))
        self.git(self.root, "add", ".lean/PROJECT.md")
        self.git(self.root, "commit", "-qm", "Fixture policy")
        return path

    def snapshot(self):
        """Include paths, bytes and metadata: even creating/touching a lock violates read-only."""
        runtime = self.root / ".agent-runtime"
        return {str(p.relative_to(runtime)): (p.stat().st_mode, p.stat().st_mtime_ns,
                                              p.read_bytes() if p.is_file() else None)
                for p in ([runtime] + list(runtime.rglob("*"))) if p.exists()} if runtime.exists() else {}

    def ready(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("receipt ready", result.stdout.lower())
        self.assertIn("validation NOT_RUN", result.stdout)
        self.assertIn("final gate", result.stdout.lower())
        self.assertNotIn("Quality Gate: PASS", result.stdout + result.stderr)

    def refused(self, result, text):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(text.lower(), (result.stdout + result.stderr).lower())
        self.assertIn("validation NOT_RUN", result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_public_preflight_missing_high_receipt(self):
        self.refused(self.preflight("--contract", HIGH), "review")

    def test_not_required_without_runtime_or_unknown_session_is_read_only(self):
        shutil.rmtree(self.root / ".agent-runtime", ignore_errors=True)
        for args in ((), ("--contract", LOW), ("--session", "unknown")):
            with self.subTest(args=args):
                result = self.preflight(*args)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("not required", result.stdout)
                self.assertIn("validation NOT_RUN", result.stdout)
                self.assertNotIn("PASS", result.stdout + result.stderr)
                self.assertFalse((self.root / ".agent-runtime").exists())

    def test_ready_runs_no_checks_and_preserves_all_runtime_state(self):
        self.project()
        self.reviewed(HIGH)
        runtime = self.root / ".agent-runtime"
        for name in ("gate-cache", "gate-failed", "gate-baseline", "gate-refusal", "quality-gate.lock",
                     "activity.jsonl", "gate-controls.json", "review-pending.json"):
            (runtime / name).write_text("preserve existing " + name)
        before = self.snapshot()
        self.ready(self.preflight("--require-review", "--contract", HIGH))
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((runtime / "check-runs").exists())

    def test_exact_contract_punctuation_and_very_high_floor(self):
        self.reviewed(HIGH)
        self.refused(self.preflight("--contract", HIGH + "."), "exact contract")
        self.reviewed(VERY_HIGH)
        self.ready(self.preflight("--contract", VERY_HIGH))
        (self.root / ".agent-runtime/review.json").unlink()
        self.refused(self.preflight("--contract", VERY_HIGH), "review")

    def test_stale_and_partially_staged_receipts_refuse(self):
        path = self.root / "code.txt"
        path.write_text("reviewed contents\n")
        self.reviewed(HIGH)
        path.write_text("later contents\n")
        self.refused(self.preflight("--contract", HIGH), "shipping state")
        self.git(self.root, "add", "code.txt")
        path.write_text("reviewed contents\n")
        self.refused(self.preflight("--contract", HIGH), "shipping")
        self.git(self.root, "add", "code.txt")
        self.ready(self.preflight("--contract", HIGH))

    def test_malformed_contract_and_required_review_without_contract(self):
        for contract in ("", "Contract: risk=HIGH quality=HIGH acceptance=",
                         HIGH + "\nextra", "risk=HIGH quality=HIGH acceptance=fixture"):
            with self.subTest(contract=contract):
                self.refused(self.preflight("--contract", contract), "contract")
        self.refused(self.preflight("--require-review"), "contract")
        for session in ("", " ", "bad\nsession", "bad\rsession"):
            with self.subTest(session=session):
                self.refused(self.preflight("--session", session), "session")

    def test_canonical_trivial_contract_needs_no_review_but_cannot_request_one(self):
        trivial = "Contract: trivial (prints risk=HIGH quality=VERY_HIGH)"
        result = self.preflight("--contract", trivial)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("not required", result.stdout)
        self.refused(self.preflight("--require-review", "--contract", trivial), "contract")

    def test_malformed_receipt_refuses_cleanly_without_runtime_mutations(self):
        runtime = self.root / ".agent-runtime"
        runtime.mkdir(exist_ok=True)
        path = runtime / "review.json"
        for receipt in ("not JSON", "[]", "null", "{}", json.dumps({"schema": 1, "verdict": "REWORK"})):
            with self.subTest(receipt=receipt):
                path.write_text(receipt)
                before = self.snapshot()
                self.refused(self.preflight("--contract", HIGH), "review")
                self.assertEqual(self.snapshot(), before)

    def test_bound_session_contract_and_committed_risk_are_used_read_only(self):
        self.project(risk=True)
        self.evidence("seed-session", "--session", "committed")
        self.bind("committed", LOW)
        (self.root / "risky.txt").write_text("committed risky content")
        self.git(self.root, "add", "risky.txt")
        self.git(self.root, "commit", "-qm", "Session risk")
        before = self.snapshot()
        self.refused(self.preflight("--session", "committed"), "risky.txt")
        self.assertEqual(self.snapshot(), before)
        self.reviewed(HIGH)
        before = self.snapshot()
        self.ready(self.preflight("--session", "committed"))
        self.assertEqual(self.snapshot(), before)
        self.bind("bound-high", HIGH)
        self.ready(self.preflight("--session", "bound-high"))
        (self.root / ".agent-runtime/review.json").unlink()
        self.refused(self.preflight("--session", "bound-high"), "review")

    def test_malformed_bound_session_fails_closed(self):
        runtime = self.root / ".agent-runtime"
        runtime.mkdir(exist_ok=True)
        path = runtime / "contract-sessions.json"
        for record in (["bad record"], {"contract": "invalid contract"}, {"contract": 123},
                       {"contract": False}, {"contract": []}):
            with self.subTest(record=record):
                path.write_text(json.dumps({"schema": 1, "sessions": {"bad": record}}))
                before = self.snapshot()
                self.refused(self.preflight("--session", "bad"), "contract")
                self.assertEqual(self.snapshot(), before)

    def test_exact_high_receipt_requires_valid_pass_fields_in_both_entries(self):
        self.project()
        self.reviewed(HIGH)
        path = self.root / ".agent-runtime/review.json"
        valid = json.loads(path.read_text())
        for field, value in (("schema", 2), ("schema", True), ("reviewer", ""), ("reviewer", {"id": "bad"}),
                             ("evidence", ""), ("evidence", ["bad"]),
                             ("verdict", "REWORK"), ("contract", LOW)):
            with self.subTest(field=field):
                path.write_text(json.dumps({**valid, field: value}))
                self.refused(self.preflight("--contract", HIGH), "review")
                result = self.gate_entry("shared", "--contract", HIGH)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        path.write_text(json.dumps(valid))
        self.ready(self.preflight("--contract", HIGH))
        self.assertEqual(self.gate_entry("shared", "--contract", HIGH).returncode, 0)

    def test_duplicate_receipt_keys_are_malformed(self):
        self.reviewed(HIGH)
        path = self.root / ".agent-runtime/review.json"
        path.write_text(path.read_text().rstrip()[:-1] + ', "verdict": "PASS"}')
        before = self.snapshot()
        self.refused(self.preflight("--contract", HIGH), "duplicate JSON key")
        self.assertEqual(self.snapshot(), before)

    def test_require_review_checks_exact_low_contract_when_requested(self):
        self.reviewed(LOW)
        self.ready(self.preflight("--require-review", "--contract", LOW))
        self.reviewed(HIGH)  # 5.7: a later receipt for another contract no longer replaces this one.
        self.ready(self.preflight("--require-review", "--contract", LOW))
        self.refused(self.preflight("--require-review", "--contract", LOW + " other"), "exact contract")

    def test_workspace_risk_rejects_exact_matching_low_receipt(self):
        self.project(risk=True)
        (self.root / "risky.txt").write_text("risk requires independent depth")
        self.reviewed(LOW)
        self.refused(self.preflight("--contract", LOW), "HIGH")
        self.reviewed(HIGH)
        self.ready(self.preflight("--contract", LOW))

    def test_final_gate_rejects_exact_matching_low_risk_receipt_after_checks(self):
        self.project(risk=True)
        (self.root / "risky.txt").write_text("risk requires independent depth")
        self.reviewed(LOW)
        result = self.gate_entry("shared", "--contract", LOW)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("HIGH", result.stderr)
        self.assertEqual((self.root / ".agent-runtime/check-runs").read_text().splitlines(), ["run"])
        self.reviewed(HIGH)
        self.assertEqual(self.gate_entry("shared", "--contract", LOW).returncode, 0)

    def test_direct_final_gate_uses_bound_high_contract(self):
        self.bind("direct-high", HIGH)
        result = self.gate_entry("shared", session="direct-high")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("review", result.stderr.lower())
        self.reviewed(HIGH)
        self.assertEqual(self.gate_entry("shared", session="direct-high").returncode, 0)

    def test_final_gate_rechecks_drift_after_readiness(self):
        self.project()
        (self.root / "code.txt").write_text("reviewed")
        self.reviewed(HIGH)
        self.ready(self.preflight("--contract", HIGH))
        self.assertFalse((self.root / ".agent-runtime/check-runs").exists())
        (self.root / "code.txt").write_text("drift after preflight")
        result = self.gate_entry("shared", "--require-review", "--contract", HIGH, "--cache-tree")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertTrue((self.root / ".agent-runtime/check-runs").exists())
        self.assertFalse((self.root / ".agent-runtime/gate-cache").exists())

    def test_preflight_never_accepts_changed_gate_controls(self):
        self.project()
        self.assertEqual(self.gate_entry("shared").returncode, 0)
        (self.root / ".lean/lean/hooks.py").write_text("# changed gate control\n")
        self.reviewed(HIGH)
        before = self.snapshot()
        self.ready(self.preflight("--contract", HIGH))
        self.assertEqual(self.snapshot(), before)
        result = self.gate_entry("shared", "--contract", HIGH)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("control", result.stderr.lower())

    def test_target_active_and_retained_high_floor_without_check_execution(self):
        context = self.install()
        self.gate_file(context, "touch target-check-ran")
        policy = Path(context["project_file"])
        policy.write_text(policy.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Target risk policy")
        (Path(context["project_root"]) / "app.txt").write_text("target risky edit")
        self.reviewed(LOW)
        before = self.snapshot()
        self.refused(self.preflight("--contract", LOW), "targets/application/app.txt")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((Path(context["project_root"]) / "target-check-ran").exists())
        self.cli("clear")
        self.refused(self.preflight("--contract", LOW), "targets/application/app.txt")
        self.reviewed(HIGH)
        self.ready(self.preflight("--contract", LOW))

    def test_invalid_active_target_fails_closed(self):
        runtime = self.root / ".agent-runtime"
        runtime.mkdir(exist_ok=True)
        active = runtime / "active-target.json"
        for data in ("[]", "{", '{"schema": 1, "name": "missing"}'):
            with self.subTest(data=data):
                active.write_text(data)
                before = self.snapshot()
                self.refused(self.preflight(), "target")
                self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
