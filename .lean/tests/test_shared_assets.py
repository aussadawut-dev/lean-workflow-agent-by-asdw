"""Single-source discovery and provider-neutral gate behavior."""
import os
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.lean/scripts'))
from shared_assets import declared_links


class SharedAssetsTests(unittest.TestCase):
    def test_previous_core_and_full_registries_remain_readable(self):
        registry = json.loads((ROOT / '.lean/assets.json').read_text())
        old_files = [name for name in registry['files'] if 'skill-effort' not in name and 'skill_effort' not in name]
        old_core = {path: target for path, target in registry['links'].items() if not path.endswith('/lean-skill-effort')}
        self.assertEqual(declared_links({'schema': 2, 'files': old_files, 'links': old_core}), old_core)
        extras = ('lean-clean-queue', 'lean-clean-repo', 'lean-compress', 'lean-model-update',
                  'lean-takeover-workflow', 'lean-use-submodule', 'lean-update-workflow')
        old_full = dict(old_core)
        for tree in ('.agents/skills', '.claude/skills'):
            old_full.update({f'{tree}/{name}': f'../../.lean/skills/{name}' for name in extras})
        self.assertEqual(declared_links({'schema': 2, 'files': old_files, 'links': old_full}), old_full)
        with self.assertRaises(ValueError):
            declared_links({'schema': 2, 'files': old_files, 'links': registry['links']})

    def test_intensity_is_shared_but_project_settings_never_ship(self):
        registry = json.loads((ROOT / '.lean/assets.json').read_text())
        self.assertNotIn('.lean/skill-effort.json', registry['files'])
        for path in (ROOT / '.lean/skills').glob('*/SKILL.md'):
            content = path.read_text()
            self.assertIn('.lean/policy/SKILL-EFFORT.md', content, path)
            self.assertIn('user-invocable: true', content, path)
            self.assertIn('argument-hint:', content, path)

    def test_discovery_uses_one_source_and_resources(self):
        names = sorted(p.name for p in (ROOT / ".lean/skills").iterdir())
        self.assertEqual(len(names), 16)
        self.assertTrue(all(name.startswith("lean-") for name in names), names)
        self.assertIn("lean-clean-queue", names)
        for tree in (".claude/skills", ".agents/skills"):
            old = ROOT / tree / "clean-queue"
            self.assertFalse(old.exists() or old.is_symlink(), old)
        declared = json.loads((ROOT / ".lean/assets.json").read_text())["links"]
        for name in names:
            canonical = ROOT / ".lean/skills" / name
            for tree in (".claude/skills", ".agents/skills"):
                link = ROOT / tree / name
                if str(link.relative_to(ROOT)) not in declared and not link.exists() and not link.is_symlink():
                    continue
                self.assertTrue(link.is_symlink(), link)
                self.assertEqual(link.resolve(), canonical.resolve())
                self.assertTrue((link / "SKILL.md").samefile(canonical / "SKILL.md"))
                for resource in canonical.rglob("*"):
                    if resource.is_file():
                        self.assertTrue((link / resource.relative_to(canonical)).samefile(resource))

    def test_direct_gate_always_runs_without_claude_state_or_stdin(self):
        with tempfile.TemporaryDirectory(prefix="shared gate ") as directory:
            root = Path(directory)
            (root / ".lean").mkdir()
            (root / ".lean/PROJECT.md").write_text(
                "<!-- gate:start -->\n```sh\necho run >> count\n```\n<!-- gate:end -->\n")
            gate = ROOT / ".lean/scripts/quality-gate.sh"
            for _ in range(2):
                result = subprocess.run(["bash", str(gate), "--root", str(root)],
                                        input='{"stop_hook_active":true}', text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "count").read_text(), "run\nrun\n")
            self.assertFalse((root / ".claude").exists())
            (root / ".lean/PROJECT.md").write_text(
                "<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n")
            accepted = subprocess.run(["python3", str(ROOT / ".lean/scripts/gate_evidence.py"),
                                       "--root", str(root), "accept-controls", "--reason",
                                       "Fixture intentionally installs a failing command"],
                                      text=True, capture_output=True)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            result = subprocess.run(["bash", str(gate), "--root", str(root)],
                                    stdin=subprocess.DEVNULL, text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Quality Gate failed: false", result.stderr)


if __name__ == "__main__":
    unittest.main()
