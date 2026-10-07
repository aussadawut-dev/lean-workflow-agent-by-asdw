"""Exercise actual local Git submodules and application/workflow boundaries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SubmoduleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean submodule ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "lean workspace"
        self.root.mkdir()
        self.env = {**os.environ, "GIT_ALLOW_PROTOCOL": "file", "GIT_TERMINAL_PROMPT": "0",
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
        for name in (".lean/scripts/submodule.py", ".lean/scripts/workflow.py", ".lean/scripts/model_catalog.py",
                     ".lean/templates/tracker.md", ".lean/templates/queue-item.json",
                     ".lean/scripts/gate_evidence.py", ".lean/scripts/quality-gate.sh", ".claude/hooks/quality-gate.sh", ".claude/hooks/session-start.sh", ".gitignore", "AGENTS.md"):
            dst = self.root / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, dst)
        (self.root / ".lean/PROJECT.md").write_text("# Lean\n<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n")
        (self.root / ".lean/config.json").write_text(json.dumps({"mode": "standard", "configured": True, "execution": "direct"}))
        self.git(self.root, "init", "-q")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Lean fixture")
        self.remote = self.make_remote("application")
        self.script = self.root / ".lean/scripts/submodule.py"

    def command(self, *args, **kwargs):
        return subprocess.run([str(a) for a in args], env=self.env, text=True, capture_output=True, **kwargs)

    def git(self, root, *args):
        result = self.command("git", "-C", root, *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def make_remote(self, name):
        source = self.base / (name + " source")
        source.mkdir()
        self.git(source, "init", "-q", "--initial-branch=main")
        (source / "app.txt").write_text("application\n")
        self.git(source, "add", ".")
        self.git(source, "commit", "-qm", "Application fixture")
        remote = self.base / (name + ".git")
        self.git(source, "clone", "-q", "--bare", str(source), str(remote))
        return remote.as_uri()

    def cli(self, *args, success=True):
        result = self.command("python3", self.script, *args)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def install(self, remote=None):
        return json.loads(self.cli("use", remote or self.remote, "--apply").stdout)

    def workflow(self, *args, success=True):
        result = self.command("python3", self.root / ".lean/scripts/workflow.py", *args)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def gate_file(self, context, command):
        Path(context["project_file"]).write_text("# Application\n<!-- gate:start -->\n```sh\n" + command + "\n```\n<!-- gate:end -->\n")

    def hook(self, seed=False):
        result = subprocess.run(["bash", str(self.root / ".claude/hooks/quality-gate.sh"), *(["--seed"] if seed else [])],
                                input="{}", env={**self.env, "CLAUDE_PROJECT_DIR": str(self.root)},
                                text=True, capture_output=True)
        return result

    def test_preview_has_no_filesystem_or_index_effects(self):
        before = self.git(self.root, "status", "--porcelain")
        proposal = json.loads(self.cli("use", self.remote).stdout)
        self.assertEqual(proposal["target"], "targets/application")
        self.assertFalse((self.root / "targets").exists())
        self.assertFalse((self.root / ".agent-runtime").exists())
        self.assertEqual(before, self.git(self.root, "status", "--porcelain"))

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
        report = self.command("python3", self.root / ".lean/scripts/model_catalog.py", "check")
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertFalse(json.loads(report.stdout)["present"])
        self.assertFalse((self.root / ".lean/scripts/__pycache__").exists())
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

    def test_application_gate_uses_target_directory_and_propagates_failure(self):
        context = self.install()
        self.cli("gate", success=False)  # Empty target checks must not count as a pass.
        self.gate_file(context, "test -f app.txt && test ! -d .lean")
        self.cli("gate")
        self.gate_file(context, "false")
        self.assertIn("Target Quality Gate failed", self.cli("gate", success=False).stderr)

    def test_direct_shared_gate_checks_target_even_when_claude_cache_would_skip(self):
        context = self.install()
        self.gate_file(context, "test ! -f blocked.txt")
        self.assertEqual(self.hook(seed=True).returncode, 0)
        gate = self.root / ".lean/scripts/quality-gate.sh"
        result = self.command("bash", gate, "--root", self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        (Path(context["project_root"]) / "blocked.txt").write_text("must gate")
        result = self.command("bash", gate, "--root", self.root)
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
        (Path(context["project_root"]) / "blocked.txt").unlink()
        self.assertEqual(self.hook().returncode, 0)

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
        result = self.command("python3", clone / ".lean/scripts/submodule.py", "use", self.remote, "--apply")
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
        result = self.command("python3", clone / ".lean/scripts/submodule.py", "use", self.remote, "--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        target = Path(json.loads(result.stdout)["project_root"])
        self.assertEqual(self.git(target, "rev-parse", "HEAD"), pinned)
        self.assertTrue(self.git(target, "symbolic-ref", "--short", "HEAD"))
        self.assertEqual(self.git(clone, "status", "--porcelain"), "")

    def test_lean_gate_checks_lean_config_and_catalog_while_target_is_selected(self):
        context = self.install()
        self.gate_file(context, "true")
        commands = [line for line in (ROOT / ".lean/PROJECT.md").read_text().splitlines()
                    if line.startswith(("python3 .lean/scripts/workflow.py", "python3 .lean/scripts/model_catalog.py"))]
        (self.root / ".lean/PROJECT.md").write_text("# Lean\n<!-- gate:start -->\n```sh\n" + "\n".join(commands) + "\n```\n<!-- gate:end -->\n")
        config = self.root / ".lean/config.json"
        original = config.read_bytes()
        config.write_text('{}')
        self.assertEqual(self.hook().returncode, 2)
        config.write_bytes(original)
        (self.root / ".lean/model-catalog.json").write_text('{}')
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
