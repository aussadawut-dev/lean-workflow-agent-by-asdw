"""Optional discovery is explicit, reversible and preserves local extensions."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
EXTRAS = {"lean-prune", "lean-compress", "lean-catalog",
          "lean-takeover", "lean-target", "lean-update",
          "lean-pattern", "lean-audit", "lean-playbook"}


class SkillPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean skill pack ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in (".lean/skills", ".lean/scripts", ".lean/templates"):
            shutil.copytree(ROOT / name, self.root / name)
        for tree in (".agents/skills", ".claude/skills"):
            (self.root / tree).mkdir(parents=True)

    def run_pack(self, action):
        return subprocess.run(["python3", str(self.root / ".lean/scripts/skill_pack.py"), action],
                              text=True, capture_output=True)

    def test_default_release_discovers_core_only(self):
        registry = json.loads((ROOT / ".lean/assets.json").read_text())
        self.assertFalse({Path(name).name for name in registry["links"]} & EXTRAS)
        self.assertEqual(len(registry["links"]), 18)  # Nine per provider.

    def test_pattern_and_audit_ship_with_resources_without_activating_automation(self):
        registry = json.loads((ROOT / ".lean/assets.json").read_text())
        for name in ("lean-pattern", "lean-audit"):
            self.assertIn(f".lean/skills/{name}/SKILL.md", registry["files"])
        for name in ("project-standard.md", "audit-finding.md"):
            self.assertIn(f".lean/templates/{name}", registry["files"])
        self.assertEqual(self.run_pack("enable").returncode, 0)
        self.assertFalse((self.root / ".agent-runtime").exists())
        self.assertFalse((self.root / "docs").exists())
        self.assertFalse((self.root / ".lean/config.json").exists())
        self.assertFalse((self.root / ".claude/settings.json").exists())

    def test_pack_preserves_project_gate_and_procedure_settings(self):
        records = {".lean/PROJECT.md": "<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n",
                   ".claude/settings.json": '{"hooks":{"Stop":[]}}',
                   ".lean/skill-effort.json": '{"default":"high","skills":{}}',
                   ".lean/config.json": '{"mode":"standard","configured":true,"execution":"direct"}',
                   "docs/operations/playbook.md": "project staging plan",
                   "docs/operations/releases/existing.md": "existing deployment evidence"}
        for name, value in records.items():
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_text(value)
        for action in ("enable", "disable"):
            self.assertEqual(self.run_pack(action).returncode, 0)
            for name, value in records.items():
                self.assertEqual((self.root / name).read_text(), value)
        self.assertFalse((self.root / ".agent-runtime").exists())

    def test_new_optional_skills_accept_named_intensity_without_discovery(self):
        for name in ("lean-pattern", "lean-audit", "lean-playbook"):
            result = subprocess.run(["python3", str(self.root / ".lean/scripts/skill_effort.py"),
                                     "--root", str(self.root), "high", name], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads((self.root / ".lean/skill-effort.json").read_text())
        self.assertEqual(settings, {"default": "standard", "skills": {
            "lean-pattern": "high", "lean-audit": "high", "lean-playbook": "high"}})
        for tree in (".agents/skills", ".claude/skills"):
            self.assertEqual(list((self.root / tree).iterdir()), [])

    def test_new_skill_conflict_prevents_partial_enable(self):
        custom = self.root / ".agents/skills/lean-playbook"
        custom.mkdir()
        (custom / "SKILL.md").write_text("project deployment plan")
        self.assertNotEqual(self.run_pack("enable").returncode, 0)
        self.assertEqual(list((self.root / ".claude/skills").iterdir()), [])
        self.assertEqual((custom / "SKILL.md").read_text(), "project deployment plan")

    def test_existing_eight_skill_pack_adds_playbook_for_both_providers(self):
        registry = json.loads((ROOT / ".lean/assets.json").read_text())
        resources = (".lean/skills/lean-playbook/SKILL.md",
                     ".lean/templates/deployment-playbook.md", ".lean/templates/deployment-release.md")
        for name in resources:
            self.assertIn(name, registry["files"])
            self.assertEqual((self.root / name).read_bytes(), (ROOT / name).read_bytes())
        for tree in (".agents/skills", ".claude/skills"):
            for name in EXTRAS - {"lean-playbook"}:
                (self.root / tree / name).symlink_to(f"../../.lean/skills/{name}")
        before = json.loads(self.run_pack("status").stdout)
        self.assertTrue(before["partial"])
        self.assertFalse(before["enabled"])
        result = self.run_pack("enable")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(json.loads(result.stdout)["changed"]), {
            ".agents/skills/lean-playbook", ".claude/skills/lean-playbook"})
        for tree in (".agents/skills", ".claude/skills"):
            self.assertTrue((self.root / tree / "lean-playbook/SKILL.md").samefile(
                self.root / ".lean/skills/lean-playbook/SKILL.md"))
        self.assertEqual(self.run_pack("disable").returncode, 0)
        self.assertTrue((self.root / ".lean/skills/lean-playbook/SKILL.md").is_file())
        self.assertFalse((self.root / "docs/operations").exists())
        self.assertFalse((self.root / ".agent-runtime").exists())

    def test_previous_pattern_pack_can_be_completed_or_disabled(self):
        for tree in (".agents/skills", ".claude/skills"):
            for name in EXTRAS - {"lean-pattern", "lean-audit", "lean-playbook"}:
                (self.root / tree / name).symlink_to(f"../../.lean/skills/{name}")
        self.assertTrue(json.loads(self.run_pack("status").stdout)["partial"])
        self.assertEqual(self.run_pack("enable").returncode, 0)
        self.assertTrue(json.loads(self.run_pack("status").stdout)["enabled"])
        self.assertEqual(self.run_pack("disable").returncode, 0)
        for tree in (".agents/skills", ".claude/skills"):
            self.assertEqual(list((self.root / tree).iterdir()), [])

    def test_enable_disable_and_status_preserve_canonical_resources(self):
        result = self.run_pack("enable")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_pack("enable").returncode, 0)
        for tree in (".agents/skills", ".claude/skills"):
            for name in EXTRAS:
                self.assertEqual((self.root / tree / name).resolve(), self.root / ".lean/skills" / name)
        result = self.run_pack("status")
        self.assertEqual(json.loads(result.stdout)["enabled"], True)
        self.assertEqual(self.run_pack("disable").returncode, 0)
        self.assertEqual(self.run_pack("disable").returncode, 0)
        self.assertFalse(json.loads(self.run_pack("status").stdout)["enabled"])
        self.assertTrue((self.root / ".lean/skills/lean-prune/SKILL.md").is_file())
        for name in ("lean-pattern", "lean-audit"):
            self.assertEqual((self.root / ".lean/skills" / name / "SKILL.md").read_bytes(),
                             (ROOT / ".lean/skills" / name / "SKILL.md").read_bytes())

    def test_conflicts_block_the_entire_batch_and_never_delete_custom_skills(self):
        custom = self.root / ".claude/skills/lean-compress"
        custom.mkdir()
        (custom / "SKILL.md").write_text("local customization")
        result = self.run_pack("enable")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any((self.root / ".agents/skills").iterdir()))
        self.assertNotEqual(self.run_pack("disable").returncode, 0)
        self.assertEqual((custom / "SKILL.md").read_text(), "local customization")

    def test_symlinked_provider_parent_blocks_writes(self):
        path = self.root / ".agents/skills"
        path.rmdir()
        outside = self.root / "outside"
        outside.mkdir()
        path.symlink_to(outside)
        self.assertNotEqual(self.run_pack("enable").returncode, 0)
        self.assertFalse(any(outside.iterdir()))


if __name__ == "__main__":
    unittest.main()
