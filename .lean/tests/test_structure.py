"""Regression checks for shared authority and native skill adapters."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class StructureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lean structure ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in (".lean", ".claude", ".agents"):
            shutil.copytree(ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__", ".gate-cache", ".gate-failed", "settings.local.json"))
        for name in ("AGENTS.md", "CLAUDE.md", ".gitignore"):
            shutil.copy2(ROOT / name, self.root / name)
        # Simulate a downstream project that chose AGENTS as canonical authority.
        contract = (ROOT / "AGENTS.md").read_text().split("## Project additions", 1)[0]
        if "## Core rules" not in contract:
            contract = (ROOT / "CLAUDE.md").read_text().split("## Project additions", 1)[0]
        (self.root / "AGENTS.md").write_text(contract)
        (self.root / "CLAUDE.md").write_text("# Claude\n\n@AGENTS.md\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def check(self, success=True):
        result = subprocess.run(["bash", str(self.root / ".lean/scripts/check-structure.sh")],
                                text=True, capture_output=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result.stdout + result.stderr

    def test_valid_template_and_space_paths_pass(self):
        self.check()

    def test_missing_canonical_import_is_rejected(self):
        with (self.root / "AGENTS.md").open("a") as output:
            output.write("\n@missing-contract.md\n")
        self.assertIn("missing import", self.check(False))

    def test_canonical_reviewer_model_rule_is_required(self):
        path = self.root / "AGENTS.md"
        path.write_text(path.read_text().replace("MODELS.md", "MISSING_MODELS"))
        self.assertIn("model", self.check(False).lower())

    def test_canonical_reviewer_routing_cannot_be_deleted(self):
        path = self.root / "AGENTS.md"
        lines = [line for line in path.read_text().splitlines() if "reviewer" not in line.lower() and "independent" not in line.lower()]
        path.write_text("\n".join(lines) + "\n")
        self.check(False)

    def test_adapter_frontmatter_name_is_validated(self):
        path = self.root / ".agents/skills/lean-task/SKILL.md"
        path.write_text(path.read_text().replace("name: lean-task", "name: wrong"))
        self.assertIn("name", self.check(False).lower())

    def test_adapter_target_is_validated(self):
        path = self.root / ".agents/skills/lean-task/SKILL.md"
        path.write_text(path.read_text().replace("../../../.claude/skills/lean-task/SKILL.md", "../../../missing-procedure.md"))
        self.assertIn("adapter", self.check(False).lower())

    def test_adapter_parity_is_required(self):
        shutil.rmtree(self.root / ".agents/skills/lean-gate")
        self.assertIn("adapter", self.check(False).lower())

    def test_clean_queue_adapter_is_required(self):
        shutil.rmtree(self.root / ".agents/skills/clean-queue")
        self.assertIn("adapter", self.check(False))

    def test_model_update_adapter_is_required(self):
        shutil.rmtree(self.root / ".agents/skills/lean-model-update")
        self.assertIn("adapter", self.check(False))

    def test_model_update_adapter_must_link_shared_procedure(self):
        path = self.root / ".agents/skills/lean-model-update/SKILL.md"
        path.write_text(path.read_text().replace("../../../.claude/skills/lean-model-update/SKILL.md", "../../../.claude/skills/lean-task/SKILL.md"))
        self.assertIn("adapter", self.check(False))

    def test_compress_adapter_is_required(self):
        shutil.rmtree(self.root / ".agents/skills/lean-compress")
        self.assertIn("adapter", self.check(False))

    def test_compress_adapter_must_link_canonical_procedure(self):
        path = self.root / ".agents/skills/lean-compress/SKILL.md"
        path.write_text(path.read_text().replace("../../../.claude/skills/lean-compress/SKILL.md", "../../../.claude/skills/lean-task/SKILL.md"))
        self.assertIn("adapter", self.check(False))

    def test_takeover_adapter_is_required_and_must_link_canonical_procedure(self):
        path = self.root / ".agents/skills/lean-takeover-workflow/SKILL.md"
        original = path.read_text()
        path.write_text(original.replace("../../../.claude/skills/lean-takeover-workflow/SKILL.md", "../../../.claude/skills/lean-task/SKILL.md"))
        self.assertIn("adapter", self.check(False))
        shutil.rmtree(path.parent)
        self.assertIn("adapter", self.check(False))

    def test_empty_description_is_rejected(self):
        path = self.root / ".agents/skills/lean-task/SKILL.md"
        lines = ["description: " if line.startswith("description:") else line for line in path.read_text().splitlines()]
        path.write_text("\n".join(lines) + "\n")
        self.check(False)

    def test_internal_commands_cannot_be_exposed(self):
        for name in ("lean-scope", "lean-research", "lean-grill", "lean-review", "lean-gate", "lean-multi-agent"):
            with self.subTest(name=name):
                path = self.root / ".claude/skills" / name / "SKILL.md"
                original = path.read_text()
                path.write_text(original.replace("user-invocable: false", "user-invocable: true"))
                self.assertIn("command visibility", self.check(False))
                path.write_text(original)

    def test_user_commands_cannot_be_hidden_or_lose_argument_hints(self):
        for name in ("lean-init", "lean-task", "lean-model-update", "lean-compress", "clean-queue", "lean-takeover-workflow"):
            with self.subTest(name=name):
                path = self.root / ".claude/skills" / name / "SKILL.md"
                original = path.read_text()
                path.write_text(original.replace("user-invocable: true", "user-invocable: false"))
                self.assertIn("command visibility", self.check(False))
                path.write_text("\n".join(line for line in original.splitlines() if not line.startswith("argument-hint:")) + "\n")
                self.assertIn("argument hint", self.check(False))
                path.write_text(original)

    def test_workflow_skills_must_remain_agent_invocable(self):
        path = self.root / ".claude/skills/lean-scope/SKILL.md"
        path.write_text(path.read_text().replace("user-invocable: false", "user-invocable: false\ndisable-model-invocation: true"))
        self.assertIn("available to the agent", self.check(False))


if __name__ == "__main__":
    unittest.main()
