"""Exercise actual local Git submodules and application/workflow boundaries."""
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, install, stop_refusal  # noqa: E402

DECLARE = "python3 .lean/bin/lean contract declare --contract '{}'"


MODE_ACTIONS = ("configure", "downgrade", "show", "check", "context")


def workflow_args(args):
    """4.x workflow.py arguments in v5 form: mode actions moved under `lean mode`."""
    args = [str(arg) for arg in args]
    prefix = []
    while args[:1] in (["--root"], ["--workflow-root"]):
        prefix, args = prefix + args[:2], args[2:]
    return prefix + (["mode", *args] if args and args[0] in MODE_ACTIONS else args)


class TargetTests(unittest.TestCase):
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
        install(self.root, extra=(".lean/templates/tracker.md", ".lean/templates/queue-item.json", "AGENTS.md",
                                  ".lean/models.json"))
        self.env.pop("LEAN_GATE_FORCE", None)
        self.env.pop("LEAN_GATE_LOCK_FD", None)
        (self.root / ".lean/PROJECT.md").write_text("# Lean\n<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n")
        (self.root / ".lean/config.json").write_text(json.dumps({"mode": "standard", "configured": True, "execution": "direct"}))
        self.git(self.root, "init", "-q")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Lean fixture")
        self.remote = self.make_remote("application")
        self.lean = self.root / ".lean/bin/lean"

    def command(self, *args, **kwargs):
        kwargs.setdefault("cwd", self.root)
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
        result = self.command(sys.executable, self.lean, "target", *args)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def install(self, remote=None):
        return json.loads(self.cli("use", remote or self.remote, "--apply").stdout)

    def workflow(self, *args, success=True):
        result = self.command(sys.executable, self.lean, *workflow_args(args))
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def gate_file(self, context, command):
        Path(context["project_file"]).write_text("# Application\n<!-- gate:start -->\n```sh\n" + command + "\n```\n<!-- gate:end -->\n")

    def hook(self, seed=False, session=""):
        result = subprocess.run([sys.executable, str(self.lean), "hook", "claude", "session-start" if seed else "stop"],
                                input=json.dumps({"session_id": session}), env={**self.env, "CLAUDE_PROJECT_DIR": str(self.root)},
                                text=True, capture_output=True, cwd=self.root)
        return stop_refusal(result)

    def evidence(self, *args):
        result = self.command(sys.executable, self.lean, "--root", self.root, "evidence", *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def gate_entry(self, entry, *args, session=""):
        if session:
            args = (*args, "--session", session)
        if entry == "standalone":
            return self.command(sys.executable, self.lean, "target", "gate", *args)
        if entry == "claude":
            return self.hook(session=session)
        if entry == "codex":
            return stop_refusal(self.command(sys.executable, self.lean, "hook", "codex", "stop",
                                             input=json.dumps({"session_id": session})))
        return self.command(sys.executable, self.lean, "--root", self.root, "gate", "run", *args)

    def reviewed(self, contract="Contract: risk=HIGH quality=HIGH acceptance=target fixture reviewed"):
        self.evidence("record-review", "--contract", contract, "--reviewer", "independent-fixture",
                      "--verdict", "PASS", "--evidence", "target contents and controls",
                      "--state", self.evidence("state"))

    def bind(self, session, contract):
        result = self.command(sys.executable, self.lean, "--root", self.root, "hook", "claude", "pre-tool",
                              input=json.dumps({"session_id": session, "tool_name": "Bash",
                                                "tool_input": {"command": DECLARE.format(contract)}}))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_target_high_risk_floor_applies_to_all_gate_entries_and_stale_reviews(self):
        context = self.install()
        marker = self.root / ".agent-runtime/target-check-ran"
        self.gate_file(context, "test -f app.txt && touch " + shlex.quote(str(marker)))
        project = Path(context["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt` and `secret/`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Registered target policy")
        self.assertEqual(self.gate_entry("shared", "--cache-tree").returncode, 0)
        self.bind("target-low", "Contract: risk=LOW quality=STANDARD acceptance=target fixture")
        target = Path(context["project_root"])
        (target / "app.txt").write_text("unreviewed target edit")
        for entry in ("shared", "standalone", "claude", "codex"):
            with self.subTest(entry=entry):
                marker.unlink(missing_ok=True)
                result = self.gate_entry(entry, session="target-low")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("targets/application/app.txt", result.stderr)
                self.assertTrue(marker.is_file(), "approved deterministic checks must precede review enforcement")
        self.reviewed()
        for entry in ("shared", "standalone", "claude", "codex"):
            result = self.gate_entry(entry, session="target-low")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (target / "secret").mkdir()
        (target / "secret/new.txt").write_text("untracked risk invalidates review")
        for entry in ("shared", "standalone"):
            result = self.gate_entry(entry, *(["--cache-tree"] if entry == "shared" else []))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("targets/application/secret/new.txt", result.stderr)

    def test_target_session_commit_and_pointer_update_keep_high_risk_floor(self):
        context = self.install()
        self.gate_file(context, "true")
        project = Path(context["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Registered target policy")
        self.evidence("seed-session", "--session", "target-session")
        target = Path(context["project_root"])
        (target / "app.txt").write_text("committed risk")
        self.git(target, "add", ".")
        self.git(target, "commit", "-qm", "Target edit")
        self.git(self.root, "add", "targets/application")
        self.git(self.root, "commit", "-qm", "Advance target pointer")
        self.evidence("seed-session", "--session", "target-session")  # Resume preserves initial pin.
        for entry in ("shared", "standalone"):
            result = self.gate_entry(entry, "--session", "target-session")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("targets/application/app.txt", result.stderr)
        self.reviewed()
        for entry in ("shared", "standalone"):
            result = self.gate_entry(entry, "--session", "target-session")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_target_added_after_session_start_reviews_all_new_high_risk_content(self):
        self.evidence("seed-session", "--session", "new-target")
        context = self.install()
        self.gate_file(context, "true")
        project = Path(context["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "New target is part of this session")
        for entry in ("shared", "standalone"):
            result = self.gate_entry(entry, session="new-target")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("targets/application/app.txt", result.stderr)
        self.reviewed()
        self.assertEqual(self.gate_entry("standalone", session="new-target").returncode, 0)

    def test_inactive_target_risk_survives_clear_switch_and_session_commits(self):
        first = self.install()
        self.gate_file(first, "true")
        project = Path(first["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "First target policy")
        second_remote = self.make_remote("second")
        second = self.install(second_remote)
        self.gate_file(second, "true")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Second target policy")
        self.install()
        self.evidence("seed-session", "--session", "inactive-risk")
        self.bind("inactive-risk", "Contract: risk=LOW quality=STANDARD acceptance=inactive target")
        target = Path(first["project_root"])
        (target / "app.txt").write_text("unreviewed inactive target")
        for selection in ("clear", "switch"):
            self.cli("clear") if selection == "clear" else self.install(second_remote)
            for entry in ("shared", "claude", "codex"):
                with self.subTest(selection=selection, entry=entry):
                    result = self.gate_entry(entry, session="inactive-risk")
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("targets/application/app.txt", result.stderr)
            # Once another application is selected, its standalone gate enforces the root receipt too.
            if selection == "switch":
                result = self.gate_entry("standalone", session="inactive-risk")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("targets/application/app.txt", result.stderr)
        self.git(target, "add", ".")
        self.git(target, "commit", "-qm", "Commit inactive target risk")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Commit inactive target pin")
        self.cli("clear")
        result = self.gate_entry("shared", session="inactive-risk")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("targets/application/app.txt", result.stderr)
        self.reviewed()
        for entry in ("shared", "claude", "codex"):
            result = self.gate_entry(entry, session="inactive-risk")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (target / "app.txt").write_text("later inactive target edit")
        result = self.gate_entry("shared", session="inactive-risk")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("targets/application/app.txt", result.stderr)

    def test_unborn_parent_target_uses_index_and_session_new_content_boundaries(self):
        self.git(self.root, "checkout", "--orphan", "unborn")
        self.evidence("seed-session", "--session", "unborn-target")
        self.bind("unborn-target", "Contract: risk=LOW quality=STANDARD acceptance=new target")
        context = self.install()
        self.gate_file(context, "true")
        for entry in ("shared", "standalone", "claude", "codex"):
            result = self.gate_entry(entry)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        project = Path(context["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        # Direct validation uses the staged pin in an unborn parent.
        self.assertEqual(self.gate_entry("shared").returncode, 0)
        # A session begun before any parent commit owns all newly registered app content.
        for committed in (False, True):
            if committed:
                self.git(self.root, "add", ".")
                self.git(self.root, "commit", "-qm", "First parent commit with new target")
            for entry in ("shared", "standalone", "claude", "codex"):
                with self.subTest(committed=committed, entry=entry):
                    result = self.gate_entry(entry, session="unborn-target")
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("targets/application/app.txt", result.stderr)

    def test_unchanged_deinitialized_retained_target_does_not_block_root_gate(self):
        context = self.install()
        self.gate_file(context, "true")
        project = Path(context["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Retained target policy")
        self.cli("clear")
        self.git(self.root, "submodule", "deinit", "-f", "--", "targets/application")
        result = self.gate_entry("shared")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_changed_deinitialized_target_and_explicit_missing_baseline_fail_closed(self):
        context = self.install()
        self.gate_file(context, "true")
        project = Path(context["project_file"])
        project.write_text(project.read_text() + "\n## High-risk areas\n- `app.txt`\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Target policy baseline")
        self.evidence("seed-session", "--session", "deinitialized-risk")
        target = Path(context["project_root"])
        (target / "app.txt").write_text("changed target pin")
        self.git(target, "add", ".")
        self.git(target, "commit", "-qm", "New target content")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Advance target pin")
        self.cli("clear")
        self.git(self.root, "submodule", "deinit", "-f", "--", "targets/application")
        result = self.gate_entry("shared", session="deinitialized-risk")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Changed target submodule is not initialized", result.stderr)
        # Only an optional HEAD can fall back to the index; a recorded unavailable tree cannot.
        (self.root / ".agent-runtime/gate-baseline-head").write_text("1" * 40)
        result = self.command(sys.executable, self.lean, "--root", self.root, "evidence", "high-risk")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("ls-tree", result.stderr)

    def test_target_control_drift_never_executes_before_guard_in_any_entry(self):
        context = self.install()
        self.gate_file(context, "true")
        self.assertEqual(self.gate_entry("shared").returncode, 0)
        self.gate_file(context, "false")
        self.evidence("accept-controls", "--reason", "fixture author approved failing target command")
        result = self.gate_entry("shared")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Target Quality Gate failed", result.stderr)
        baseline = (self.root / ".agent-runtime/gate-controls.json").read_bytes()
        self.gate_file(context, ":; touch escaped-control")
        for entry in ("standalone", "shared", "claude", "codex"):
            with self.subTest(entry=entry):
                result = self.gate_entry(entry)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("Protected gate controls changed", result.stderr)
                self.assertFalse((Path(context["project_root"]) / "escaped-control").exists())
                self.assertEqual((self.root / ".agent-runtime/gate-controls.json").read_bytes(), baseline)

    def test_switching_target_does_not_approve_inactive_gate_drift(self):
        first = self.install()
        self.gate_file(first, "true")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "First registered target")
        second = self.install(self.make_remote("second"))
        self.gate_file(second, "true")
        self.assertEqual(self.gate_entry("shared").returncode, 0)
        self.gate_file(first, "touch inactive-control")
        result = self.gate_entry("shared")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Protected gate controls changed", result.stderr)
        self.install()
        self.assertEqual(self.gate_entry("standalone").returncode, 2)
        self.assertFalse((Path(first["project_root"]) / "inactive-control").exists())

    def test_target_control_review_uses_root_session_trust_for_all_entries(self):
        context = self.install()
        self.gate_file(context, "true")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Baseline target checks")
        self.assertEqual(self.gate_entry("standalone").returncode, 0)
        contract = "Contract: risk=HIGH quality=HIGH acceptance=review target controls"
        self.bind("target-controls", contract)
        for entry in ("standalone", "shared", "claude", "codex"):
            with self.subTest(entry=entry):
                self.gate_file(context, "true # reviewed " + entry)
                rejected = self.gate_entry(entry, session="target-controls")
                self.assertEqual(rejected.returncode, 2, rejected.stdout + rejected.stderr)
                self.assertIn("Protected gate controls changed", rejected.stderr)
                self.reviewed(contract)
                # A receipt alone cannot accept drift without the session's declared contract.
                unbound = self.gate_entry("standalone")
                self.assertEqual(unbound.returncode, 2, unbound.stderr)
                accepted = self.gate_entry(entry, session="target-controls")
                self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
                history = json.loads((self.root / ".agent-runtime/gate-controls.json").read_text())["history"]
                self.assertIn("independent HIGH-depth", history[-1]["reason"])
                self.git(self.root, "add", ".")
                self.git(self.root, "commit", "-qm", "Accept reviewed target checks " + entry)

    def test_target_controls_match_trusted_root_ref_and_reject_retained_symlinks(self):
        context = self.install()
        self.gate_file(context, "true")
        project = self.root / ".lean/PROJECT.md"
        project.write_text(project.read_text() + "\n<!-- trusted-control-refs: refs/remotes/origin/main -->\n")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Baseline targets and trusted ref")
        self.git(self.root, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.assertEqual(self.gate_entry("standalone").returncode, 0)
        self.gate_file(context, "true # trusted target gate")
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Upstream reviewed target gate")
        self.git(self.root, "update-ref", "refs/remotes/origin/main", "HEAD")
        result = self.gate_entry("standalone")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("match refs/remotes/origin/main", result.stderr)
        # Retained records are checked even with no selected target.
        self.cli("clear")
        target_project = Path(context["project_file"])
        external = self.base / "external PROJECT.md"
        external.write_bytes(target_project.read_bytes())
        target_project.unlink()
        target_project.symlink_to(external)
        result = self.gate_entry("shared")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("symlink boundary", result.stderr)

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
