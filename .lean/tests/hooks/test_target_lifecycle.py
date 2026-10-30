"""Target install, selection, records, gate propagation and clone behavior."""
from pathlib import Path
import json
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from target_support import TargetFixture  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, install  # noqa: E402


class TargetLifecycleTests(TargetFixture):
    def test_preview_has_no_filesystem_or_index_effects(self):
        before = self.git(self.root, "status", "--porcelain")
        proposal = json.loads(self.cli("use", self.remote).stdout)
        self.assertEqual(proposal["target"], "targets/application")
        self.assertFalse((self.root / "targets").exists())
        self.assertFalse((self.root / ".agent-runtime").exists())
        self.assertEqual(before, self.git(self.root, "status", "--porcelain"))

    def test_skill_intensity_uses_selected_records_and_invalid_context_blocks(self):
        context = self.install()
        skills = self.root / '.lean/skills/lean-scope'
        skills.mkdir(parents=True)
        (skills / 'SKILL.md').write_text('scope procedure')
        result = self.command(sys.executable, self.lean, 'effort', 'ultra', 'lean-scope')
        self.assertEqual(result.returncode, 0, result.stderr)
        target_settings = Path(context['record_root']) / '.lean/skill-effort.json'
        self.assertEqual(json.loads(target_settings.read_text())['skills'], {'lean-scope': 'ultra'})
        self.assertFalse((Path(context['project_root']) / '.lean').exists())
        self.assertFalse((self.root / '.lean/skill-effort.json').exists())
        result = self.command(sys.executable, self.lean, '--root', self.root, 'effort', 'high')
        self.assertEqual(result.returncode, 0, result.stderr)
        lean_settings = self.root / '.lean/skill-effort.json'
        before = lean_settings.read_bytes()
        (self.root / '.agent-runtime/active-target.json').write_text('{"schema":1,"name":"missing"}')
        result = self.command(sys.executable, self.lean, 'effort', 'standard')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(lean_settings.read_bytes(), before)
        self.assertEqual(json.loads(target_settings.read_text())['skills'], {'lean-scope': 'ultra'})

    def test_unignored_selection_and_active_lean_work_block_initial_install(self):
        ignore = self.root / ".gitignore"
        original = ignore.read_text()
        ignore.write_text(original.replace('.agent-runtime/', ''))
        self.cli("use", self.remote, "--apply", success=False)
        self.assertFalse((self.root / ".agent-runtime").exists())
        ignore.write_text(original)
        self.workflow("--root", self.root, "configure", "tracker")
        self.workflow("--root", self.root, "tracker", "new", "--id", "TCK001", "--title", "Lean work")
        self.workflow("--root", self.root, "tracker", "status", "--id", "TCK001", "--status", "IN_PROGRESS")
        self.cli("use", self.remote, "--apply", success=False)
        self.assertFalse((self.root / "targets").exists())

    def test_install_repeat_and_pending_work_preservation(self):
        staged = self.root / "existing.txt"
        staged.write_text("pending Lean work")
        self.git(self.root, "add", "existing.txt")
        before_head = self.git(self.root, "rev-parse", "HEAD")
        context = self.install()
        target = Path(context["project_root"])
        self.assertEqual(context["branch"], "main")
        self.assertEqual(self.git(target, "status", "--porcelain"), "")
        self.assertEqual(self.git(target, "ls-files"), "app.txt")
        self.assertFalse((target / ".lean").exists())
        (target / "untracked.txt").write_text("keep")
        index = self.git(self.root, "ls-files", "--stage")
        before_project = Path(context["project_file"]).read_bytes()
        again = self.install()
        self.assertEqual(again["stages"], [])
        self.assertEqual(index, self.git(self.root, "ls-files", "--stage"))
        self.assertEqual(before_project, Path(context["project_file"]).read_bytes())
        self.assertEqual(before_head, self.git(self.root, "rev-parse", "HEAD"))
        self.assertEqual((target / "untracked.txt").read_text(), "keep")

    def test_records_and_model_catalog_resolve_outside_target(self):
        context = self.install()
        host = (self.root / ".lean/config.json").read_bytes()
        self.workflow("configure", "tracker", "--execution", "delegated")
        self.workflow("tracker", "new", "--id", "TCK001", "--title", "Target work")
        records = Path(context["record_root"])
        self.assertTrue((records / "docs/tracking/TCK001.md").is_file())
        self.assertEqual(host, (self.root / ".lean/config.json").read_bytes())
        self.assertEqual(self.git(Path(context["project_root"]), "status", "--porcelain"), "")
        report = self.command(sys.executable, self.lean, "models", "check")
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("model list ok", report.stdout)
        self.assertFalse((self.root / ".lean/lean/__pycache__").exists())
        self.assertTrue(json.loads(self.workflow("--root", self.root, "show").stdout)["configured"])
        self.workflow("--root", records, "--workflow-root", self.root, "tracker", "new", "--id", "TCK002", "--title", "Explicit records")

    def test_full_records_and_claims_stay_in_lean(self):
        context = self.install()
        self.workflow("configure", "full")
        self.workflow("tracker", "new", "--id", "TCK001", "--title", "Claim")
        records = Path(context["record_root"])
        item = json.loads((ROOT / ".lean/templates/queue-item.json").read_text())
        (records / ".agents/queue/items/Q0001.json").write_text(json.dumps(item))
        claim = json.loads(self.workflow("queue", "claim", "--id", "Q0001", "--agent", "worker", "--request-id", "submodule-test-claim").stdout)
        self.assertTrue((records / ".agent-runtime/claims/Q0001.json").is_file())
        self.cli("clear", success=False)
        self.workflow("queue", "release", "--id", "Q0001", "--token", claim["token"])
        self.cli("clear")
        self.assertEqual(self.git(Path(context["project_root"]), "status", "--porcelain"), "")

    def test_status_and_mode_context_identify_their_roots(self):
        context = self.install()
        self.workflow("configure", "full")
        self.command(sys.executable, self.lean, "progress", "set", "test", "--task", "workspace progress")
        report = json.loads(self.command(sys.executable, self.lean, "status", "--json").stdout)
        self.assertEqual(report["mode"], "standard")
        self.assertEqual(report["roots"], {k: context[k] for k in ("workflow_root", "project_root", "record_root")})
        self.assertEqual(report["target_mode"]["mode"], "full")
        resumed = json.loads(self.workflow("context").stdout)
        self.assertEqual(resumed["progress"]["task"], "workspace progress")
        self.assertEqual(resumed["evidence_root"], str(self.root.resolve()))
        explicit = json.loads(self.workflow("--root", context["record_root"], "context").stdout)
        self.assertEqual(explicit["progress"]["task"], "workspace progress")
        scoped = json.loads(self.command(sys.executable, self.lean, "--root", context["record_root"],
                                         "status", "--json").stdout)
        self.assertEqual(scoped["mode"], "full")
        self.assertIsNone(scoped["progress"])
        self.assertEqual(scoped["scope_root"], context["record_root"])

    def closure_fixture(self, high=False):
        context = self.install()
        self.workflow("configure", "tracker")
        self.workflow("tracker", "new", "--id", "TCK001", "--title", "Closure")
        tracker = Path(context["record_root"]) / "docs/tracking/TCK001.md"
        tracker.write_text(tracker.read_text().replace("- [ ]", "- [x]"))
        self.workflow("tracker", "new", "--id", "TCK002", "--title", "Second batch task")
        second = tracker.with_name("TCK002.md")
        second.write_text(second.read_text().replace("- [ ]", "- [x]"))
        self.gate_file(context, "true")
        self.evidence("accept-controls", "--reason", "fixture gate approved")
        contract = f"Contract: risk={'HIGH' if high else 'LOW'} quality=HIGH acceptance=fixture closure works"
        if high:
            self.evidence("record-review", "--contract", contract, "--reviewer", "fixture-reviewer",
                          "--state", self.evidence("state"), "--verdict", "PASS", "--evidence", "fixture review")
        result = self.command(sys.executable, self.lean, "gate", "run", "--contract", contract)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return context, tracker, contract

    def test_target_closure_uses_workspace_pass_and_allows_bookkeeping(self):
        context, tracker, contract = self.closure_fixture()
        self.workflow("tracker", "status", "--id", "TCK001", "--status", "DONE",
                      "--contract", contract, "--evidence", "covering gate passed")
        self.assertIn("Status: DONE", tracker.read_text())
        self.assertEqual(tracker.stat().st_mode & 0o777, 0o644)
        # A second workset in the same validated batch may close against the same pass.
        self.workflow("tracker", "status", "--id", "TCK002", "--status", "DONE",
                      "--contract", contract, "--evidence", "closure bookkeeping")
        self.assertIn("Status: DONE", tracker.with_name("TCK002.md").read_text())
        report = json.loads(self.workflow("context").stdout)
        self.assertEqual(report["evidence_root"], context["workflow_root"])
        self.assertEqual(report["gate"]["status"], "STALE")

    def test_target_closure_rejects_changed_requirements_and_code(self):
        context, tracker, contract = self.closure_fixture()
        original = tracker.read_text()
        tracker.write_text(original.replace("Observable result.", "A different requirement."))
        rejected = self.workflow("tracker", "status", "--id", "TCK001", "--status", "DONE",
                                 "--contract", contract, "--evidence", "invalid closure", success=False)
        self.assertIn("stale", rejected.stderr)
        tracker.write_text(original)
        (Path(context["project_root"]) / "app.txt").write_text("changed after validation")
        rejected = self.workflow("tracker", "status", "--id", "TCK001", "--status", "DONE",
                                 "--contract", contract, "--evidence", "invalid closure", success=False)
        self.assertIn("stale", rejected.stderr)
        self.assertNotIn("Status: DONE", tracker.read_text())

    def test_target_closure_rechecks_exact_contract_and_review(self):
        context, tracker, contract = self.closure_fixture(high=True)
        rejected = self.workflow("tracker", "status", "--id", "TCK001", "--status", "DONE",
                                 "--contract", contract + " changed", "--evidence", "invalid", success=False)
        self.assertIn("exact Task Contract", rejected.stderr)
        self.evidence("record-review", "--contract", contract, "--reviewer", "fixture-reviewer",
                      "--state", self.evidence("state"), "--verdict", "REWORK", "--evidence", "new finding")
        rejected = self.workflow("tracker", "status", "--id", "TCK001", "--status", "DONE",
                                 "--contract", contract, "--evidence", "invalid", success=False)
        self.assertIn("not PASS", rejected.stderr)
        self.assertNotIn("Status: DONE", tracker.read_text())

    def test_target_closure_rejects_staged_shipping_difference(self):
        context, tracker, contract = self.closure_fixture()
        app = Path(context["project_root"]) / "app.txt"
        original = app.read_text()
        app.write_text("staged but not validated")
        self.git(Path(context["project_root"]), "add", "app.txt")
        app.write_text(original)
        rejected = self.workflow("tracker", "status", "--id", "TCK001", "--status", "DONE",
                                 "--contract", contract, "--evidence", "invalid", success=False)
        self.assertIn("stale", rejected.stderr)
        self.assertNotIn("Status: DONE", tracker.read_text())

    def test_shared_pass_rejects_target_checks_that_change_shipping_inputs(self):
        context = self.install()
        self.gate_file(context, "printf changed > app.txt")
        self.evidence("accept-controls", "--reason", "fixture control approved")
        result = self.command(sys.executable, self.lean, "gate", "run")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("shipping inputs changed during validation", result.stderr)

    def test_application_gate_uses_target_directory_and_propagates_failure(self):
        context = self.install()
        self.cli("gate", success=False)  # Empty target checks must not count as a pass.
        self.gate_file(context, "test -f app.txt && test ! -d .lean")
        result = self.cli("gate")
        self.assertIn("Target Quality Gate: check 1 started", result.stderr)
        self.assertIn("Target Quality Gate: check 1 passed", result.stderr)
        self.assertNotIn("Target Quality Gate: check", self.cli("gate", "--quiet").stderr)
        self.gate_file(context, "false")
        self.evidence("accept-controls", "--reason", "fixture author approved failing target command")
        self.assertIn("Target Quality Gate failed", self.cli("gate", success=False).stderr)

    def test_direct_shared_gate_checks_target_even_when_claude_cache_would_skip(self):
        context = self.install()
        self.gate_file(context, "test ! -f blocked.txt")
        self.assertEqual(self.hook(seed=True).returncode, 0)
        gate = ["gate", "run"]
        result = self.command(sys.executable, self.lean, "--root", self.root, *gate)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Target Quality Gate: check 1 passed", result.stderr)
        quiet = self.command(sys.executable, self.lean, "--root", self.root, *gate, "--quiet")
        self.assertEqual(quiet.returncode, 0, quiet.stderr)
        self.assertNotIn("Quality Gate: check", quiet.stderr)
        (Path(context["project_root"]) / "blocked.txt").write_text("must gate")
        result = self.command(sys.executable, self.lean, "--root", self.root, *gate)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Target Quality Gate failed", result.stderr)

    def test_hook_gates_untracked_target_work_even_after_lean_cache_is_seeded(self):
        context = self.install()
        self.gate_file(context, "test ! -f blocked.txt")
        self.assertEqual(self.hook(seed=True).returncode, 0)
        self.assertEqual(self.hook().returncode, 0)
        (Path(context["project_root"]) / "blocked.txt").write_text("must gate")
        result = self.hook()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Target Quality Gate failed", result.stderr)
        self.assertNotIn("Quality Gate: check", result.stdout + result.stderr)  # A Stop runs the target quietly.
        (Path(context["project_root"]) / "blocked.txt").unlink()
        self.assertEqual(self.hook().returncode, 0)

    def test_target_output_never_corrupts_the_stop_decision_and_is_in_the_reason(self):
        context = self.install()
        self.gate_file(context, "echo app-out-on-stdout; echo app-err-on-stderr >&2; test ! -f blocked.txt")
        self.assertEqual(self.hook(seed=True).returncode, 0)
        (Path(context["project_root"]) / "blocked.txt").write_text("must gate")
        self.bind("s", "Contract: risk=LOW quality=STANDARD acceptance=target checks pass")
        for provider in ("claude", "codex"):
            with self.subTest(provider=provider):
                raw = subprocess.run([sys.executable, str(self.lean), "hook", provider, "stop"], cwd=self.root,
                                     input=json.dumps({"session_id": "s", "stop_hook_active": False}), text=True,
                                     capture_output=True, env={**self.env, "CLAUDE_PROJECT_DIR": str(self.root)})
                self.assertEqual(raw.returncode, 0, raw.stderr)
                decision = json.loads(raw.stdout)  # A single JSON object, nothing else on stdout.
                self.assertEqual(decision["decision"], "block")
                self.assertIn("Target Quality Gate failed", decision["reason"])
                self.assertIn("app-out-on-stdout", decision["reason"])
                self.assertIn("app-err-on-stderr", decision["reason"])

    def test_spawn_run_refuses_while_a_target_is_selected(self):
        self.install()
        tasks = self.root / ".agent-runtime/tasks.json"
        tasks.write_text(json.dumps({"tasks": [{"id": "a", "files": ["app.txt"], "size": "S"}]}))
        result = self.command(sys.executable, self.lean, "spawn", "run", "--tasks", tasks)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("target", result.stderr)
        planned = self.command(sys.executable, self.lean, "spawn", "plan", "--tasks", tasks)
        self.assertEqual(planned.returncode, 0, planned.stderr)  # Planning for in-session subagents still works.

    def test_invalid_active_context_blocks_tools_instead_of_falling_back(self):
        context = self.install()
        manifest = Path(context["record_root"]) / "context.json"
        manifest.write_text('{}')
        self.cli("context", success=False)
        self.workflow("show", success=False)
        self.assertEqual(self.hook().returncode, 2)

    def test_symlink_and_existing_path_are_never_overwritten(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.root / "targets").symlink_to(outside, target_is_directory=True)
        self.cli("use", self.remote, "--apply", success=False)
        self.assertEqual(list(outside.iterdir()), [])
        (self.root / "targets").unlink()
        (self.root / "targets/application").mkdir(parents=True)
        self.cli("use", self.remote, "--apply", success=False)
        self.assertFalse((self.root / ".gitmodules").exists())

    def test_collision_and_pending_gitmodules_are_preserved(self):
        self.install()
        other = self.base / "another"
        other.mkdir()
        same_name_remote = (other / "application.git").as_uri()
        self.cli("use", same_name_remote, "--apply", success=False)
        modules = self.root / ".gitmodules"
        before = modules.read_bytes()
        different = self.make_remote("second")
        self.cli("use", different, "--apply", success=False)  # Existing staged modules are not restaged.
        self.assertEqual(modules.read_bytes(), before)
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "First target")
        modules.write_bytes(before + b"\n# pending\n")
        self.cli("use", different, "--apply", success=False)
        self.assertEqual(modules.read_bytes(), before + b"\n# pending\n")

    def test_detached_checkout_reuses_default_branch_without_losing_changes(self):
        context = self.install()
        target = Path(context["project_root"])
        self.git(target, "checkout", "--detach")
        (target / "app.txt").write_text("pending")
        self.cli("use", self.remote, "--apply", success=False)
        self.assertEqual((target / "app.txt").read_text(), "pending")
        self.git(target, "restore", "app.txt")
        self.assertEqual(self.install()["branch"], "main")

    def test_clone_can_initialize_and_select_registered_target(self):
        self.install()
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Target registration")
        clone = self.base / "another Lean checkout"
        self.git(self.root, "clone", "-q", str(self.root), str(clone))
        result = self.command(sys.executable, clone / ".lean/bin/lean", "target", "use", self.remote, "--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        context = json.loads(result.stdout)
        self.assertEqual(context["branch"], "main")
        self.assertEqual(self.git(Path(context["project_root"]), "status", "--porcelain"), "")

    def test_clone_keeps_pinned_commit_when_remote_default_advances(self):
        first = self.install()
        pinned = self.git(Path(first["project_root"]), "rev-parse", "HEAD")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Pin application")
        advanced = self.base / "advanced application"
        self.git(self.root, "clone", "-q", self.remote, str(advanced))
        (advanced / "app.txt").write_text("advanced remote\n")
        self.git(advanced, "add", ".")
        self.git(advanced, "commit", "-qm", "Advance default")
        self.git(advanced, "push", "-q", "origin", "main")
        clone = self.base / "pinned Lean clone"
        self.git(self.root, "clone", "-q", str(self.root), str(clone))
        result = self.command(sys.executable, clone / ".lean/bin/lean", "target", "use", self.remote, "--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        target = Path(json.loads(result.stdout)["project_root"])
        self.assertEqual(self.git(target, "rev-parse", "HEAD"), pinned)
        self.assertTrue(self.git(target, "symbolic-ref", "--short", "HEAD"))
        self.assertEqual(self.git(clone, "status", "--porcelain"), "")

    def test_lean_gate_checks_lean_config_and_catalog_while_target_is_selected(self):
        context = self.install()
        self.gate_file(context, "true")
        commands = [line for line in (ROOT / ".lean/PROJECT.md").read_text().splitlines()
                    if line.startswith(("python3 .lean/bin/lean --root . mode", "python3 .lean/bin/lean --root . models"))]
        self.assertEqual(len(commands), 2, commands)
        (self.root / ".lean/PROJECT.md").write_text("# Lean\n<!-- gate:start -->\n```sh\n" + "\n".join(commands) + "\n```\n<!-- gate:end -->\n")
        config = self.root / ".lean/config.json"
        original = config.read_bytes()
        config.write_text('{}')
        self.assertEqual(self.hook().returncode, 2)
        config.write_bytes(original)
        (self.root / ".lean/models.json").write_text('{}')
        self.assertEqual(self.hook().returncode, 2)

    def test_clear_keeps_checkout_and_records(self):
        context = self.install()
        self.cli("clear")
        self.assertTrue(Path(context["project_root"]).is_dir())
        self.assertTrue(Path(context["project_file"]).is_file())
        self.assertIsNone(json.loads(self.cli("context").stdout)["target"])
        self.cli("gate", "--optional")

    def test_switch_preserves_each_target_configuration_and_blocks_active_tracker(self):
        first = self.install()
        self.workflow("configure", "tracker", "--execution", "delegated")
        self.workflow("tracker", "new", "--id", "TCK001", "--title", "First target")
        self.workflow("tracker", "status", "--id", "TCK001", "--status", "IN_PROGRESS")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "First target")
        second_remote = self.make_remote("second")
        self.cli("use", second_remote, "--apply", success=False)
        self.assertFalse((self.root / "targets/second").exists())
        self.workflow("tracker", "status", "--id", "TCK001", "--status", "BLOCKED")
        second = self.install(second_remote)
        self.assertNotEqual(first["record_root"], second["record_root"])
        self.assertFalse(json.loads(self.workflow("show").stdout)["configured"])
        self.install()
        self.assertEqual(json.loads(self.workflow("show").stdout)["execution"], "delegated")

    def test_missing_target_can_be_deselected_without_losing_records(self):
        context = self.install()
        self.git(self.root, "submodule", "deinit", "-f", "--", "targets/application")
        self.cli("context", success=False)
        self.cli("clear")
        self.assertTrue(Path(context["project_file"]).is_file())
        self.assertIsNone(json.loads(self.cli("context").stdout)["target"])

    def test_invalid_remote_cannot_create_state_or_run_shell_commands(self):
        for remote in ("--help", "https://token@example.org/app.git", "https://host/app.git?token=x", "$(touch injected)", "file:///tmp/../.git"):
            self.cli("use", "--apply", "--", remote, success=False)
        self.assertFalse((self.root / ".agent-runtime").exists())
        self.assertFalse((self.root / "injected").exists())


if __name__ == "__main__":
    unittest.main()
