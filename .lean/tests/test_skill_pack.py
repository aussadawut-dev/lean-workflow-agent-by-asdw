"""Optional discovery is explicit, reversible and preserves local extensions."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
EXTRAS = {"lean-clean-queue", "lean-clean-repo", "lean-compress", "lean-model-update",
          "lean-takeover-workflow", "lean-use-submodule", "lean-update-workflow"}


class SkillPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean skill pack ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in (".lean/skills", ".lean/scripts"):
            shutil.copytree(ROOT / name, self.root / name)
        for tree in (".agents/skills", ".claude/skills"):
            (self.root / tree).mkdir(parents=True)

    def run_pack(self, action):
        return subprocess.run(["python3", str(self.root / ".lean/scripts/skill_pack.py"), action],
                              text=True, capture_output=True)

    def test_default_release_discovers_core_only(self):
        registry = json.loads((ROOT / ".lean/assets.json").read_text())
        self.assertFalse({Path(name).name for name in registry["links"]} & EXTRAS)

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
        self.assertTrue((self.root / ".lean/skills/lean-clean-repo/SKILL.md").is_file())

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
