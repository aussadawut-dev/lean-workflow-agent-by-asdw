"""Single-source discovery and provider-neutral gate behavior."""
import os
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SharedAssetsTests(unittest.TestCase):
    def test_discovery_uses_one_source_and_resources(self):
        names = sorted(p.name for p in (ROOT / ".lean/skills").iterdir())
        self.assertEqual(len(names), 15)
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
