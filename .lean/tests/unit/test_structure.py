"""`lean lint`: a fresh copy of the release passes, and each broken invariant is named."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, install_release, lean  # noqa: E402
from lean import __version__, structure  # noqa: E402


class StandardLibraryOnlyTests(unittest.TestCase):
    def test_workflow_code_imports_only_the_standard_library(self):
        import ast
        import importlib.util
        for path in sorted((ROOT / ".lean/lean").glob("*.py")) + [ROOT / ".lean/bin/lean"]:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    top = name.split(".")[0]
                    if top == "lean":
                        continue  # The workflow's own package.
                    spec = importlib.util.find_spec(top)
                    origin = (spec.origin or "") if spec else ""
                    with self.subTest(module=top, file=path.name):
                        self.assertIsNotNone(spec, f"{top} is not importable")
                        self.assertNotIn("site-packages", origin, f"{top} is a third-party package")


class LintTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        install_release(self.root)

    def failures(self):
        return structure.check(self.root)

    def assertFails(self, expected):
        failures = self.failures()
        self.assertTrue(any(expected in failure for failure in failures), failures)

    def test_the_registered_release_is_self_contained_and_passes(self):
        self.assertEqual(self.failures(), [])
        result = lean(self.root, "lint")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("lint ok", result.stdout)

    def test_a_release_copy_brings_the_project_files_its_project_md_names(self):
        # An installation's PROJECT.md may name its own `.lean/` documents (Casetodian's LOCAL-EXTENSIONS.md);
        # the shipped tests must still pass there.
        with tempfile.TemporaryDirectory() as other, tempfile.TemporaryDirectory() as copy:
            source = Path(other)
            install_release(source, init=False)
            project = source / ".lean/PROJECT.md"
            project.write_text(project.read_text() + "\nLocal rules: `.lean/LOCAL-EXTENSIONS.md`.\n")
            (source / ".lean/LOCAL-EXTENSIONS.md").write_text("See `.lean/local/NOTES.md`.\n")
            (source / ".lean/local").mkdir()
            (source / ".lean/local/NOTES.md").write_text("notes\n")
            install_release(copy, source=source)
            self.assertEqual(structure.check(Path(copy)), [])
            self.assertTrue((Path(copy) / ".lean/local/NOTES.md").is_file())
            # A reference that climbs out of `.lean/` is never followed.
            (source / "x.md").write_text("outside\n")
            project.write_text(project.read_text() + "Also `.lean/../x.md`.\n")
            with tempfile.TemporaryDirectory() as second:
                install_release(second, source=source)
                self.assertFalse((Path(second) / "x.md").exists())

    def test_a_release_document_naming_an_unregistered_file_still_fails(self):
        # Only PROJECT.md brings project files along; an omission from the registry is never papered over.
        with tempfile.TemporaryDirectory() as other, tempfile.TemporaryDirectory() as copy:
            source = Path(other)
            install_release(source, init=False)
            registry = source / ".lean/assets.json"
            data = json.loads(registry.read_text())
            data["files"].remove(".claude/agents/reviewer.md")
            registry.write_text(json.dumps(data))
            install_release(copy, source=source)
            self.assertIn("missing .claude/agents/reviewer.md (from AGENTS.md)", structure.check(Path(copy)))
            self.assertFalse((Path(copy) / ".lean/gate.json").exists(), "optional configuration stays out")

    def test_skill_links_must_point_at_canonical_skills(self):
        link = self.root / ".claude/skills/lean-task"
        link.unlink()
        self.assertFails("incorrect discovery link: .claude/skills/lean-task")
        os.symlink("../../.lean/skills/lean-gate", link)
        self.assertFails("incorrect discovery link: .claude/skills/lean-task")

    def test_retired_and_broken_links_are_reported(self):
        os.symlink("../../.lean/skills/lean-prune", self.root / ".agents/skills/lean-prune")
        self.assertFails("retired or broken discovery link: .agents/skills/lean-prune")

    def test_project_skills_beside_the_links_need_frontmatter(self):
        custom = self.root / ".claude/skills/deploy"
        custom.mkdir()
        (custom / "SKILL.md").write_text("no frontmatter\n")
        self.assertFails("no closed frontmatter")
        (custom / "SKILL.md").write_text("---\nname: deploy\ndescription: Ship it.\n---\nSteps.\n")
        self.assertEqual(self.failures(), [])

    def test_unregistered_workflow_files_and_canonical_skills_are_reported(self):
        (self.root / ".lean/lean/extra.py").write_text("x = 1\n")
        self.assertFails("workflow file missing from .lean/assets.json: .lean/lean/extra.py")
        (self.root / ".lean/skills/lean-new").mkdir()
        self.assertFails("unregistered canonical skill: .lean/skills/lean-new")

    def test_syntax_errors_and_a_non_executable_entry_are_reported(self):
        (self.root / ".lean/lean/gate.py").write_text("def broken(:\n")
        (self.root / ".lean/bin/lean").chmod(0o644)
        self.assertFails("syntax error: .lean/lean/gate.py")
        self.assertFails("missing or non-executable: .lean/bin/lean")

    def test_markdown_references_imports_and_policy_routes_must_resolve(self):
        path = self.root / ".lean/policy/TOOLS.md"
        path.write_text(path.read_text() + "\nSee `.lean/scripts/workflow.py` and `GHOST.md`.\n")
        self.assertFails("missing .lean/scripts/workflow.py (from .lean/policy/TOOLS.md)")
        self.assertFails("missing sibling policy GHOST.md")
        agents = self.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "\n@.lean/GONE.md\n")
        self.assertFails("missing import .lean/GONE.md")

    def test_only_documents_agents_follow_must_name_existing_paths(self):
        notes = self.root / "docs/notes/2026-evaluation.md"
        notes.parent.mkdir(parents=True)
        notes.write_text("The 4.x gate ran `.lean/scripts/quality-gate.sh`.\n")
        self.assertEqual(self.failures(), [], "an unrouted history document may name retired paths")
        project = self.root / ".lean/PROJECT.md"
        # Its own routes section: an installation's PROJECT.md may end with any other heading.
        project.write_text(project.read_text() + "\n## Documentation routes\n\n- Evaluations -> `docs/notes/2026-evaluation.md`\n")
        self.assertFails("missing .lean/scripts/quality-gate.sh (from docs/notes/2026-evaluation.md)")
        agents = self.root / "AGENTS.md"
        agents.write_text(agents.read_text() + "\n- Run `.lean/scripts/submodule.py context` first.\n")
        self.assertFails("missing .lean/scripts/submodule.py (from AGENTS.md)")

    def test_an_unreadable_routed_document_is_reported_not_a_crash(self):
        project = self.root / ".lean/PROJECT.md"
        project.write_text(project.read_text() + "\n## Documentation routes\n\n- Notes -> `docs/blob.md`\n")
        (self.root / "docs").mkdir()
        (self.root / "docs/blob.md").write_bytes(b"\xff\xfe not text")
        self.assertFails("unreadable instruction document (not UTF-8 text?): docs/blob.md")

    def test_hooks_must_call_the_cli_and_never_seed_on_stop(self):
        (self.root / ".codex/hooks.json").write_text('{"hooks": {"Stop": [{"hooks": [{"command": "true"}]}]}}')
        self.assertFails("hooks must call the lean CLI: .codex/hooks.json")
        settings = self.root / ".claude/settings.json"
        settings.write_text(settings.read_text().replace("stop --cache-tree", "stop --seed"))
        self.assertFails("--seed must not appear in .claude/settings.json")
        settings.write_text("{not json")
        self.assertFails("invalid JSON: .claude/settings.json")

    def test_versions_must_agree(self):
        router = self.root / ".lean/README.md"
        router.write_text(router.read_text().replace(f"Baseline {__version__}", "Baseline 0.0.1"))
        self.assertFails("workflow version differs")

    def test_gate_markers_model_list_and_runtime_ignore(self):
        project = self.root / ".lean/PROJECT.md"
        project.write_text(project.read_text() + "\n<!-- gate:start -->\n")
        self.assertFails("expected one gate:start marker")
        (self.root / ".lean/models.json").write_text('{"schema": 1, "max_agents": 0, "providers": {}}')
        self.assertFails(".lean/models.json: max_agents")
        (self.root / ".gitignore").write_text("")
        self.assertFails("not ignored by git: .agent-runtime/")

    def test_high_review_routing_must_stay_independent_and_model_sized(self):
        task = self.root / ".lean/skills/lean-task/SKILL.md"
        task.write_text(task.read_text().replace("independent", "separate"))
        self.assertFails("HIGH reviewer routing requires independent review")


if __name__ == "__main__":
    unittest.main()
