"""`lean update`: preview writes nothing, apply migrates a 4.x installation, rollback restores it."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, commit, git, install_release, lean  # noqa: E402
from lean import __version__ as VERSION  # noqa: E402

LEGACY_GATE = """<!-- gate:start -->
```sh
shellcheck .claude/hooks/*.sh .lean/scripts/*.sh .lean/tests/*.sh
.lean/scripts/check-structure.sh
python3 .lean/scripts/workflow.py --root . check
python3 .lean/scripts/model_catalog.py --root . check
make test
python3 -m unittest discover -s .lean/tests -p 'test_skill_pack.py'
python3 tools/check_commit_attribution.py --root .
python3 .lean/tests/run_tests.py --shards 6 test-hooks.sh test_gate_integrity.py
```
<!-- gate:end -->
"""
OLD_FILES = {
    ".lean/scripts/workflow.py": "print('4.x')\n",
    ".lean/scripts/quality-gate.sh": "#!/usr/bin/env bash\n",
    ".claude/hooks/quality-gate.sh": "#!/usr/bin/env bash\n",
    ".codex/hooks/quality_gate.py": "print('4.x')\n",
    ".lean/skills/lean-prune/SKILL.md": "---\nname: lean-prune\ndescription: old\n---\n",
    ".lean/skills/lean-task/SKILL.md": "---\nname: lean-task\ndescription: old\n---\n",
    ".lean/policy/QUALITY.md": "# Quality (4.x)\n",
    ".lean/README.md": "# Agent policy router\n\nLean Workflow Baseline 4.17.0.\n",
}


def write(root, name, text):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def snapshot(root):
    """Every path outside .git with its bytes, mode or link target."""
    found = {}
    for path in sorted(Path(root).rglob("*")):
        relative = str(path.relative_to(root))
        if relative == ".git" or relative.startswith(".git/"):
            continue
        if path.is_symlink():
            found[relative] = "link:" + os.readlink(path)
        elif path.is_file():
            found[relative] = (path.read_bytes(), os.access(path, os.X_OK))
    return found


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="lean-update-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.source = self.base / "upstream"
        install_release(self.source)
        commit(self.source, f"release {VERSION}")
        git(self.source, "tag", f"v{VERSION}")
        self.target = self.base / "project"
        self.legacy_install()
        self.cli = [sys.executable, str(self.source / ".lean/bin/lean")]

    def legacy_install(self):
        """A 4.17-shaped installation with project data that must survive."""
        target = self.target
        for name, text in OLD_FILES.items():
            write(target, name, text)
        (target / ".claude/hooks/quality-gate.sh").chmod(0o755)
        write(target, "AGENTS.md", "# Agent Instructions\n\nLean Workflow Baseline 4.17.0.\n\n## Project additions\n\n"
                                   "- Use pnpm, never npm.\n")
        write(target, "CLAUDE.md", "# Claude Instructions\n\n@AGENTS.md\n\n## Project additions\n\n- Claude note.\n")
        write(target, ".claude/settings.json", json.dumps({
            "permissions": {"allow": ["Bash(pnpm test:*)"]},
            "statusLine": {"type": "command", "command": "~/bin/my-status"},
            "hooks": {"Stop": [{"hooks": [{"type": "command", "command": ".claude/hooks/quality-gate.sh"}]}],
                      "PostToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "pnpm prettier"}]}],
                      "PreToolUse": [{"hooks": [{"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR\"/"
                                                 ".lean/scripts/contract_guard.py pre-tool || exit 2"}]},
                                     {"matcher": "Bash", "hooks": [{"type": "command", "command": "./audit.sh"}]}]}}))
        write(target, ".lean/PROJECT.md", "# Project Context\n\n## Purpose\n\nA shop.\n\n" + LEGACY_GATE)
        write(target, ".codex/quality-gate.json", '{"auto": false}\n')
        write(target, ".lean/config.json", '{"mode": "tracker", "configured": true, "execution": "direct"}\n')
        write(target, "docs/tracking/TCK001.md", "# TCK001 — Work\n\nStatus: IN_PROGRESS\n\n## Evidence\n")
        write(target, "docs/tracking/README.md", "# Tracking\n")
        write(target, "docs/tracking/TEMPLATE.md", (ROOT / ".lean/templates/tracker.md").read_text())
        write(target, ".gitignore", ".env\n")
        write(target, "src/app.py", "print('app')\n")
        links = {}
        for skill in ("lean-prune", "lean-task"):
            for tree in (".claude/skills", ".agents/skills"):
                (target / tree).mkdir(parents=True, exist_ok=True)
                os.symlink(f"../../.lean/skills/{skill}", target / tree / skill)
                links[f"{tree}/{skill}"] = f"../../.lean/skills/{skill}"
        # An optional 4.x skill enabled by skill_pack: linked, but not declared in the registry's links.
        write(target, ".lean/skills/lean-takeover/SKILL.md", "---\nname: lean-takeover\ndescription: old\n---\n")
        os.symlink("../../.lean/skills/lean-takeover", target / ".claude/skills/lean-takeover")
        # A project's own skill beside the Lean links must survive.
        write(target, ".claude/skills/deploy/SKILL.md", "---\nname: deploy\ndescription: Ship.\n---\n")
        write(target, ".codex/hooks.json", json.dumps({"hooks": {
            "Stop": [{"hooks": [{"type": "command",
                                 "command": "python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/quality_gate.py\" stop"}]}],
            "PostToolUse": [{"hooks": [{"type": "command", "command": "./codex-format.sh"}]}]}}))
        files = sorted(OLD_FILES) + [".lean/skills/lean-takeover/SKILL.md", "AGENTS.md", "CLAUDE.md",
                                     ".claude/settings.json", ".codex/hooks.json", ".lean/assets.json"]
        write(target, ".lean/assets.json", json.dumps({"schema": 2, "files": files, "links": links}))
        subprocess.run(["git", "init", "-q", str(target)], check=True)
        commit(target, "4.17 install")

    def lean(self, *args, root=None):
        return subprocess.run([*self.cli, "--root", str(root or self.target), *args], text=True, capture_output=True)

    def preview(self, workspace="ws"):
        result = self.lean("update", "preview", "--target", str(self.target), "--source", str(self.source),
                           "--workspace", str(self.base / workspace))
        self.assertEqual(result.returncode, 0, result.stderr)
        return result, json.loads((self.base / workspace / "plan.json").read_text())

    def test_preview_writes_nothing_and_lists_the_migration(self):
        before = snapshot(self.target)
        result, plan = self.preview()
        self.assertEqual(snapshot(self.target), before)
        self.assertEqual((plan["installed_version"], plan["incoming_version"]), ("4.17.0", VERSION))
        self.assertEqual(plan["ref"], f"refs/tags/v{VERSION}")
        provenance = [op for op in plan["operations"] if op["path"] == ".lean/upstream.json"][0]
        self.assertEqual(json.loads(provenance["content"])["ref"], f"refs/tags/v{VERSION}")
        actions = {op["path"]: op["action"] for op in plan["operations"]}
        for retired in (".lean/scripts/workflow.py", ".claude/hooks/quality-gate.sh", ".codex/hooks/quality_gate.py",
                        ".lean/skills/lean-prune/SKILL.md", ".claude/skills/lean-prune", ".codex/quality-gate.json",
                        ".claude/skills/lean-takeover", ".lean/skills/lean-takeover/SKILL.md"):
            self.assertEqual(actions.get(retired), "delete", retired)
        for written in (".lean/bin/lean", ".lean/lean/gate.py", ".lean/policy/QUALITY.md", ".lean/gate.json",
                        "AGENTS.md", ".lean/PROJECT.md", ".lean/upstream.json", ".lean/models.json", ".gitignore"):
            self.assertEqual(actions.get(written), "write", written)
        self.assertEqual(actions.get(".claude/skills/lean-update"), "link")
        self.assertIn(f"Lean update 4.17.0 -> {VERSION}", result.stdout)
        # Every overwrite of an existing file is listed, not only counted.
        self.assertIn("  replace  .lean/policy/QUALITY.md — major-version migration", result.stdout)
        self.assertIn("  merge    .claude/settings.json", result.stdout)
        self.assertIn("kept your status line", result.stdout)
        self.assertNotIn("src/app.py", actions)
        self.assertNotIn("docs/tracking/TCK001.md", actions)
        self.assertNotIn(".lean/config.json", actions)

    def test_preview_names_what_lint_will_reject_after_the_update(self):
        # Found upgrading a real 4.16 project: its own test in .lean/tests and a routed README naming 4.x paths.
        project = self.target / ".lean/PROJECT.md"
        project.write_text(project.read_text() + "\n## Documentation routes\n\n- Setup: `README.md`\n"
                           "- Outside: `../outside.md`\n- Absolute: `/etc/outside.md`\n- Binary: `docs/blob.md`\n"
                           "- Ignored: `docs/ignored.md`\n- Linked: `docs/linked.md`\n- Escaping: `docs/escape.md`\n")
        write(self.target, "docs/real.md", "`.lean/scripts/gate_mode.py`\n")
        os.symlink("real.md", self.target / "docs/linked.md")
        os.symlink(str(self.base / "outside.md"), self.target / "docs/escape.md")
        (self.base / "outside.md").write_text("`.lean/scripts/workflow.py`\n")
        (self.target / "docs").mkdir(exist_ok=True)
        (self.target / "docs/blob.md").write_bytes(b"\xff\xfe .lean/scripts/workflow.py")
        write(self.target, "docs/ignored.md", "`.lean/scripts/takeover.py`\n")
        (self.target / ".gitignore").write_text((self.target / ".gitignore").read_text() + "docs/ignored.md\n")
        write(self.target, "README.md", "Run `python3 .lean/scripts/submodule.py context`.\n")
        write(self.target, ".lean/tests/test_local_gate.py", "# the project's own test\n")
        commit(self.target, "project files")
        result, plan = self.preview()
        self.assertIn("README.md still names the 4.x path .lean/scripts/submodule.py", result.stdout)
        self.assertIn(".lean/tests/test_local_gate.py is not part of Lean but sits in a workflow-owned folder",
                      result.stdout)
        self.assertIn("docs/linked.md still names the 4.x path .lean/scripts/gate_mode.py", result.stdout)
        self.assertIn("docs/blob.md is not UTF-8 text; lean lint reports it as unreadable", result.stdout)
        for unseen in ("outside.md", "/etc/outside.md", "docs/blob.md", "docs/ignored.md", "docs/escape.md"):
            self.assertNotIn(f"{unseen} still names", result.stdout)
        actions = {op["path"]: op["action"] for op in plan["operations"]}
        self.assertNotIn(".lean/tests/test_local_gate.py", actions, "a project's file is never deleted")
        self.assertNotIn("README.md", actions)

    def test_apply_migrates_preserves_project_data_and_passes_lint(self):
        _, plan = self.preview()
        tracker = (self.target / "docs/tracking/TCK001.md").read_bytes()
        applied = self.lean("update", "apply", "--workspace", str(self.base / "ws"))
        self.assertEqual(applied.returncode, 0, applied.stderr)
        target = self.target
        self.assertFalse((target / ".lean/scripts").exists())
        self.assertFalse((target / ".claude/hooks").exists())
        self.assertFalse((target / ".claude/skills/lean-prune").is_symlink())
        self.assertFalse((target / ".claude/skills/lean-takeover").is_symlink())
        self.assertTrue((target / ".claude/skills/deploy/SKILL.md").is_file())
        self.assertEqual(os.readlink(target / ".agents/skills/lean-update"), "../../.lean/skills/lean-update")
        self.assertTrue(os.access(target / ".lean/bin/lean", os.X_OK))
        agents = (target / "AGENTS.md").read_text()
        self.assertIn(f"Lean Workflow Baseline {VERSION}", agents)
        self.assertTrue(agents.rstrip().endswith("- Use pnpm, never npm."))
        self.assertIn("- Claude note.", (target / "CLAUDE.md").read_text())
        settings = json.loads((target / ".claude/settings.json").read_text())
        self.assertEqual(settings["permissions"], {"allow": ["Bash(pnpm test:*)"]})
        self.assertIn("lean hook claude stop", settings["hooks"]["Stop"][0]["hooks"][0]["command"])
        # The project's own hooks and status line survive; only Lean's entries are replaced.
        self.assertEqual(settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"], "pnpm prettier")
        pre = [hook["command"] for group in settings["hooks"]["PreToolUse"] for hook in group["hooks"]]
        self.assertIn("./audit.sh", pre)
        self.assertFalse(any("contract_guard.py" in command for command in pre))
        self.assertTrue(any("lean hook claude pre-tool" in command for command in pre))
        self.assertEqual(settings["statusLine"]["command"], "~/bin/my-status")
        codex = json.loads((target / ".codex/hooks.json").read_text())["hooks"]
        self.assertEqual(codex["PostToolUse"][0]["hooks"][0]["command"], "./codex-format.sh")
        stops = [hook["command"] for group in codex["Stop"] for hook in group["hooks"]]
        self.assertTrue(any("lean\" hook codex stop" in command for command in stops), stops)
        self.assertFalse(any("quality_gate.py" in command for command in stops))
        project = (target / ".lean/PROJECT.md").read_text()
        gate = project.split("<!-- gate:start -->")[1].split("<!-- gate:end -->")[0]
        self.assertEqual([line for line in gate.splitlines() if line and not line.startswith("```")],
                         ["python3 .lean/bin/lean lint", "python3 .lean/bin/lean --root . mode check",
                          "python3 .lean/bin/lean --root . models check", "make test",
                          "python3 .lean/bin/lean test --changed", "python3 .lean/bin/lean attribution"])
        self.assertIn("A shop.", project)
        self.assertEqual(json.loads((target / ".lean/gate.json").read_text()), {"auto": False})
        self.assertFalse((target / ".codex/quality-gate.json").exists())
        self.assertEqual(json.loads((target / ".lean/upstream.json").read_text())["commit"], plan["commit"])
        self.assertEqual((target / "docs/tracking/TCK001.md").read_bytes(), tracker)
        self.assertEqual(json.loads((target / ".lean/config.json").read_text())["mode"], "tracker")
        self.assertIn(".agent-runtime/", (target / ".gitignore").read_text())
        for args in (("lint",), ("mode", "check"), ("models", "check")):
            result = subprocess.run([sys.executable, str(target / ".lean/bin/lean"), *args], text=True,
                                    capture_output=True, cwd=target)
            self.assertEqual(result.returncode, 0, (args, result.stdout + result.stderr))
        again = self.lean("update", "apply", "--workspace", str(self.base / "ws"))
        self.assertNotEqual(again.returncode, 0)  # A plan applies once.

    def test_rollback_restores_the_exact_installation(self):
        before = snapshot(self.target)
        self.preview()
        self.assertEqual(self.lean("update", "apply", "--workspace", str(self.base / "ws")).returncode, 0)
        self.assertNotEqual(snapshot(self.target), before)
        restored = self.lean("update", "rollback", "--workspace", str(self.base / "ws"))
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(snapshot(self.target), before)

    def test_rollback_refuses_after_later_edits(self):
        self.preview()
        self.lean("update", "apply", "--workspace", str(self.base / "ws"))
        (self.target / ".lean/policy/QUALITY.md").write_text("edited after the update\n")
        refused = self.lean("update", "rollback", "--workspace", str(self.base / "ws"))
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("changed after the update", refused.stderr)

    def test_apply_refuses_a_target_that_changed_since_preview(self):
        self.preview()
        (self.target / ".lean/scripts/workflow.py").write_text("print('edited')\n")
        before = snapshot(self.target)
        refused = self.lean("update", "apply", "--workspace", str(self.base / "ws"))
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("changed since preview", refused.stderr)
        self.assertEqual(snapshot(self.target), before)

    def test_local_files_the_old_registry_did_not_own_are_conflicts_until_taken(self):
        write(self.target, ".lean/policy/MODELS.md", "# Local model notes\n")
        _, plan = self.preview()
        conflict = [op for op in plan["operations"] if op["path"] == ".lean/policy/MODELS.md"][0]
        self.assertEqual(conflict["action"], "conflict")
        self.lean("update", "apply", "--workspace", str(self.base / "ws"))
        self.assertEqual((self.target / ".lean/policy/MODELS.md").read_text(), "# Local model notes\n")
        write(self.target, ".lean/policy/MODELS.md", "# Local model notes\n")
        self.lean("update", "rollback", "--workspace", str(self.base / "ws"))
        _, plan = self.preview("ws2")
        bad = self.lean("update", "apply", "--workspace", str(self.base / "ws2"), "--take", "src/app.py")
        self.assertNotEqual(bad.returncode, 0)
        taken = self.lean("update", "apply", "--workspace", str(self.base / "ws2"), "--take", ".lean/policy/MODELS.md")
        self.assertEqual(taken.returncode, 0, taken.stderr)
        self.assertEqual((self.target / ".lean/policy/MODELS.md").read_text(),
                         (ROOT / ".lean/policy/MODELS.md").read_text())

    def test_plan_paths_never_leave_the_target(self):
        _, plan = self.preview()
        path = self.base / "ws/plan.json"
        for bad in ("../escaped.txt", "/tmp/lean-escape.txt", "docs/../../escaped.txt"):
            with self.subTest(path=bad):
                tampered = json.loads(path.read_text())
                tampered["operations"].append({"path": bad, "action": "write", "content": "x", "link": None,
                                               "mode": None, "reason": "tampered", "before": None})
                path.write_text(json.dumps(tampered))
                refused = self.lean("update", "apply", "--workspace", str(self.base / "ws"))
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn("outside the target", refused.stderr)
                path.write_text(json.dumps(plan))
        self.assertFalse((self.base / "escaped.txt").exists())
        self.assertFalse(Path("/tmp/lean-escape.txt").exists())
        outside = self.base / "outside"
        outside.mkdir()
        (self.target / "docs/linked").symlink_to(outside)
        tampered = json.loads(path.read_text())
        tampered["operations"].append({"path": "docs/linked/x.txt", "action": "write", "content": "x", "link": None,
                                       "mode": None, "reason": "tampered", "before": None})
        path.write_text(json.dumps(tampered))
        refused = self.lean("update", "apply", "--workspace", str(self.base / "ws"))
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_a_release_registry_with_escaping_paths_is_refused(self):
        registry = self.source / ".lean/assets.json"
        data = json.loads(registry.read_text())
        data["files"].append("../evil.txt")
        registry.write_text(json.dumps(data))
        commit(self.source, "bad registry")
        git(self.source, "tag", "-f", f"v{VERSION}")
        result = self.lean("update", "preview", "--target", str(self.target), "--source", str(self.source),
                           "--workspace", str(self.base / "ws-bad"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside the target", result.stderr)

    def test_older_releases_and_workspaces_inside_a_checkout_are_refused(self):
        inside = self.lean("update", "preview", "--target", str(self.target), "--source", str(self.source),
                           "--workspace", str(self.target / "ws"))
        self.assertNotEqual(inside.returncode, 0)
        self.assertIn("outside every Git checkout", inside.stderr)
        newer = self.base / "newer"
        install_release(newer)
        for name in ("AGENTS.md", ".lean/README.md"):
            path = newer / name
            path.write_text(path.read_text().replace(f"Baseline {VERSION}", "Baseline 6.0.0"))
        commit(newer, "6.0.0")
        older = self.lean("update", "preview", "--target", str(newer), "--source", str(self.source),
                          "--workspace", str(self.base / "ws3"))
        self.assertNotEqual(older.returncode, 0)
        self.assertIn("older than installed", older.stderr)


if __name__ == "__main__":
    unittest.main()
