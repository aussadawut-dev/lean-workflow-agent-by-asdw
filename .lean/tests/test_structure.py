"""Regression checks for shared authority and shared skill discovery links."""
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
            shutil.copytree(ROOT / name, self.root / name, symlinks=True,
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

    def test_shared_frontmatter_name_is_validated(self):
        path = self.root / ".lean/skills/lean-task/SKILL.md"
        path.write_text(path.read_text().replace("name: lean-task", "name: wrong"))
        self.assertIn("name", self.check(False).lower())

    def test_runtime_links_cannot_be_missing_wrong_or_copies(self):
        for tree in (".claude/skills", ".agents/skills"):
            for name in ("lean-task", "lean-gate", "lean-init", "lean-review"):
                with self.subTest(tree=tree, name=name):
                    link = self.root / tree / name
                    original = link.readlink()
                    link.unlink()
                    self.assertIn("discovery link", self.check(False))
                    wrong = "lean-task" if name == "lean-init" else "lean-init"
                    link.symlink_to(f"../../.lean/skills/{wrong}")
                    self.assertIn("discovery link", self.check(False))
                    link.unlink()
                    shutil.copytree(self.root / ".lean/skills" / name, link)
                    self.assertIn("discovery link", self.check(False))
                    shutil.rmtree(link)
                    link.symlink_to(original)

    def test_canonical_boundary_and_missing_target_are_rejected(self):
        path = self.root / ".lean/skills/lean-task"
        shutil.rmtree(path)
        self.assertIn("target", self.check(False))
        path.symlink_to(self.root / ".lean/skills/lean-init")
        self.assertIn("boundary", self.check(False))

    def test_optional_discovery_is_absent_or_canonical(self):
        for tree in (".agents/skills", ".claude/skills"):
            link = self.root / tree / "lean-compress"
            if link.is_symlink():
                link.unlink()
            self.check()
            link.symlink_to("../../.lean/skills/lean-compress")
            self.check()
            link.unlink()
            link.symlink_to("../../.lean/skills/lean-init")
            self.assertIn("discovery link", self.check(False))
            link.unlink()

    def test_provider_local_extensions_are_preserved(self):
        for tree in (".claude/skills", ".agents/skills"):
            path = self.root / tree / "project-helper"
            path.mkdir()
            (path / "SKILL.md").write_text("---\nname: project-helper\ndescription: Project task\n---\n")
        self.check()

    def test_empty_description_is_rejected(self):
        path = self.root / ".lean/skills/lean-task/SKILL.md"
        lines = ["description: " if line.startswith("description:") else line for line in path.read_text().splitlines()]
        path.write_text("\n".join(lines) + "\n")
        self.check(False)

    def test_core_procedures_cannot_be_hidden(self):
        for name in ("lean-scope", "lean-research", "lean-grill", "lean-review", "lean-gate", "lean-multi-agent"):
            with self.subTest(name=name):
                path = self.root / ".lean/skills" / name / "SKILL.md"
                original = path.read_text()
                path.write_text(original.replace("user-invocable: true", "user-invocable: false"))
                self.assertIn("command visibility", self.check(False))
                path.write_text(original)

    def test_user_commands_cannot_be_hidden_or_lose_argument_hints(self):
        for name in ("lean-init", "lean-task", "lean-model-update", "lean-compress", "lean-clean-queue", "lean-takeover-workflow", "lean-use-submodule"):
            with self.subTest(name=name):
                path = self.root / ".lean/skills" / name / "SKILL.md"
                original = path.read_text()
                path.write_text(original.replace("user-invocable: true", "user-invocable: false"))
                self.assertIn("command visibility", self.check(False))
                path.write_text("\n".join(line for line in original.splitlines() if not line.startswith("argument-hint:")) + "\n")
                self.assertIn("argument hint", self.check(False))
                path.write_text(original)

    def test_workflow_skills_must_remain_agent_invocable(self):
        path = self.root / ".lean/skills/lean-scope/SKILL.md"
        path.write_text(path.read_text().replace("user-invocable: true", "user-invocable: true\ndisable-model-invocation: true"))
        self.assertIn("available to the agent", self.check(False))


class SkillLevelContractTests(unittest.TestCase):
    """Pin agent instruction boundaries; these do not execute or grade an LLM."""

    def text(self, skill):
        return (ROOT / ".lean/skills" / skill / "SKILL.md").read_text()

    def test_optional_levels_preserve_default_and_authority(self):
        for skill in ("lean-scope", "lean-research", "lean-grill"):
            with self.subTest(skill=skill):
                text = self.text(skill)
                self.assertIn("saved skill override, saved default, then `standard`", text)
                self.assertIn("A request for one skill does not raise the others", text)
                self.assertIn("a later skill-specific request overrides an earlier group request", text)
                self.assertIn("ambiguous or names an unsupported level, clarify", text)
                self.assertIn("Do not silently lower a requested level", text)
                self.assertIn("Do not change those settings or spawn agents", text)
                self.assertIn("do not expand the user's intended scope", text)
                self.assertIn("otherwise resolve its saved override/default under SKILL-EFFORT", text)
                self.assertIn("user-invocable: true", text)
                for level in ("standard", "high", "ultra"):
                    self.assertIn("- **" + level + "**", text)
                self.assertIn("**high** — Add to standard", text)
                self.assertIn("**ultra** — Add to high", text)

    def test_scope_precision_keeps_approval_boundary(self):
        text = self.text("lean-scope")
        self.assertIn("Map each behavior to observable acceptance criteria", text)
        self.assertIn("states/transitions, edge cases, failures, recovery, exceptions", text)
        self.assertIn("trace requirements through behavior, acceptance and validation", text)
        self.assertIn("matching approval before dependent work", text)
        self.assertIn("If the user requested analysis or a spec only", text)

    def test_grill_depth_does_not_bypass_answers_or_reopen_decisions(self):
        text = self.text("lean-grill")
        self.assertIn("Ask about details needed for precise acceptance", text)
        self.assertIn("question in multiple rounds", text)
        self.assertIn("wait for answers before dependent follow-ups", text)
        self.assertIn("without reopening settled choices absent new evidence or conflict", text)
        self.assertIn("not to meet a question quota", text)
        self.assertIn("READY_WITH_ASSUMPTIONS", text)
        self.assertIn("Do not start dependent code while a material decision remains open", text)

    def test_research_breadth_is_not_false_corroboration_or_write_authority(self):
        text = self.text("lean-research")
        self.assertIn("more relevant vendors, projects or approaches", text)
        self.assertIn("investigate the strongest candidates in depth", text)
        self.assertIn("Do not count syndicated copies as independent corroboration", text)
        self.assertIn("one vendor's pages as multiple vendors", text)
        self.assertIn("not a cap on high/ultra discovery", text)
        self.assertIn("explain the limit rather than inventing breadth or certainty", text)
        self.assertIn("research does not authorize a prototype, dependency installation or external write", text)
        self.assertIn("claim-level evidence for decisive differences", text)


if __name__ == "__main__":
    unittest.main()
