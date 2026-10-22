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
        for name in (".lean", ".claude", ".agents", ".codex"):
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

    def test_model_policy_requires_explicit_spawn_settings(self):
        path = self.root / ".lean/policy/MODELS.md"
        path.write_text(path.read_text().replace("on every spawn", "when convenient"))
        self.assertIn("spawn", self.check(False).lower())

    def test_model_policy_keeps_cheaper_work_in_the_active_session(self):
        path = self.root / ".lean/policy/MODELS.md"
        path.write_text(path.read_text().replace("Spawn only when required or cheaper.", "Spawn freely."))
        self.assertIn("session", self.check(False).lower())

    def test_dispatch_example_cannot_default_to_inherited_settings(self):
        path = self.root / ".lean/skills/lean-agents/SKILL.md"
        content = path.read_text()
        start = content.index("requested model/effort=")
        end = content.index(" |", start)
        path.write_text(content[:start] + "requested model/effort=inherited/inherited" + content[end:])
        self.assertIn("inherited", self.check(False).lower())

    def test_dispatch_requires_a_per_worker_budget(self):
        path = self.root / ".lean/skills/lean-agents/SKILL.md"
        path.write_text(path.read_text().replace("about 50 turns", "as many turns as needed"))
        self.assertIn("budget", self.check(False).lower())

    def test_budget_cannot_remove_required_behavior_tests(self):
        path = self.root / ".lean/skills/lean-agents/SKILL.md"
        path.write_text(path.read_text().replace("never removes required behavior tests", "may trim tests"))
        self.assertIn("behavior tests", self.check(False).lower())

    def test_spent_worker_is_redispatched_not_resumed(self):
        path = self.root / ".lean/skills/lean-agents/SKILL.md"
        path.write_text(path.read_text().replace("Do not resume a worker that spent its budget", "Resume any worker"))
        self.assertIn("instead of resuming", self.check(False).lower())

    def test_codex_turn_cap_gap_stays_recorded(self):
        path = self.root / ".lean/skills/lean-agents/SKILL.md"
        path.write_text(path.read_text().replace("has no per-spawn turn cap", "is capped"))
        self.assertIn("codex", self.check(False).lower())

    def test_controller_checks_a_worker_tree_before_accepting_it(self):
        path = self.root / ".lean/skills/lean-agents/SKILL.md"
        path.write_text(path.read_text().replace("missing handoff report", "short handoff report"))
        self.assertIn("handoff", self.check(False).lower())

    def test_controller_keeps_its_own_claim_alive_while_workers_run(self):
        path = self.root / ".lean/skills/lean-agents/SKILL.md"
        path.write_text(path.read_text().replace("heartbeat it before each dispatch", "leave it"))
        self.assertIn("heartbeat", self.check(False).lower())

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

    def test_retired_or_dangling_skill_slots_are_rejected(self):
        dangling = self.root / ".claude/skills/lean-multi-agent"
        dangling.symlink_to("../../.lean/skills/lean-multi-agent")
        self.assertIn("discovery link", self.check(False))
        dangling.unlink()
        retired_dir = self.root / ".lean/skills/lean-clean-repo"
        retired_dir.mkdir()
        self.assertIn("canonical skill", self.check(False))
        retired_dir.rmdir()
        self.check()

    def test_empty_description_is_rejected(self):
        path = self.root / ".lean/skills/lean-task/SKILL.md"
        lines = ["description: " if line.startswith("description:") else line for line in path.read_text().splitlines()]
        path.write_text("\n".join(lines) + "\n")
        self.check(False)

    def test_core_procedures_cannot_be_hidden(self):
        for name in ("lean-scope", "lean-research", "lean-grill", "lean-review", "lean-gate", "lean-agents", "lean-effort"):
            with self.subTest(name=name):
                path = self.root / ".lean/skills" / name / "SKILL.md"
                original = path.read_text()
                path.write_text(original.replace("user-invocable: true", "user-invocable: false"))
                self.assertIn("command visibility", self.check(False))
                path.write_text(original)

    def test_user_commands_cannot_be_hidden_or_lose_argument_hints(self):
        for name in ("lean-init", "lean-task", "lean-catalog", "lean-compress", "lean-prune", "lean-takeover", "lean-target", "lean-update"):
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


class ContextSelectionContractTests(unittest.TestCase):
    """Protect routing instructions; actual agent read traces need scenario evaluation."""

    def read(self, path):
        return (ROOT / path).read_text()

    def test_entrypoints_route_to_context_selection(self):
        self.assertIn("policy/CONTEXT.md", self.read(".lean/skills/lean-task/SKILL.md"))
        self.assertIn("impact-based context selection", self.read("AGENTS.md"))

    def test_style_edit_starts_local_without_a_folder_allowlist(self):
        context = self.read(".lean/policy/CONTEXT.md")
        self.assertIn("style-only web change", context)
        self.assertIn("follow dependencies across area boundaries", context)
        self.assertIn("Missing or stale routes", context)

    def test_form_change_expands_to_api_and_permissions_when_affected(self):
        context = self.read(".lean/policy/CONTEXT.md")
        self.assertIn("payload, validation, error handling or access", context)
        self.assertIn("API contract/schema", context)
        self.assertIn("permission rules", context)

    def test_feedback_reuses_only_valid_context_and_decisions(self):
        context = self.read(".lean/policy/CONTEXT.md")
        self.assertIn("feedback, current diff and affected dependencies", context)
        self.assertIn("changed files, stale evidence, conflicting requirements", context)
        self.assertIn("Material scope changes still need approval", context)

    def test_selection_never_skips_required_procedures_or_validation(self):
        context = self.read(".lean/policy/CONTEXT.md")
        self.assertIn("Explicitly requested skills still run", context)
        self.assertIn("mandatory high-risk Grill", context)
        self.assertIn("does not select or reduce tests, review depth or Quality Gate commands", context)
        effort = self.read(".lean/policy/SKILL-EFFORT.md")
        self.assertIn("does not activate additional skills", effort)

    def test_standards_routes_load_by_affected_boundary_or_locale_signals(self):
        context = self.read(".lean/policy/CONTEXT.md")
        self.assertIn("routes to accepted project standards", context)
        self.assertIn("module-boundary and dependency-direction rules", context)
        self.assertIn("user-facing copy or locale files", context)


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

    def test_pattern_and_audit_cover_repo_structure_i18n_grammar_and_legacy_grill(self):
        init_text = self.text("lean-init")
        pattern_text = self.text("lean-pattern")
        audit_text = self.text("lean-audit")
        review_policy = (ROOT / ".lean/policy/REVIEW.md").read_text()
        reviewer_role = (ROOT / ".lean/roles/reviewer.md").read_text()
        review_skill = self.text("lean-review")
        standard_template = (ROOT / ".lean/templates/project-standard.md").read_text()
        audit_scenarios = (ROOT / ".lean/skills/lean-audit/references/scenarios.md").read_text()
        self.assertIn("/lean-pattern", init_text)
        self.assertIn("early baseline", pattern_text)
        self.assertIn("module boundaries", pattern_text)
        self.assertIn("dependency direction", pattern_text)
        self.assertIn("hardcoded user-facing strings", pattern_text)
        self.assertIn("grammar and natural phrasing", pattern_text)
        self.assertIn("terminology/glossary", pattern_text)
        self.assertIn("compound/domain term precedence", pattern_text)
        self.assertIn("accept-controls", pattern_text)
        self.assertIn("ratchet/baseline", pattern_text)
        self.assertIn("existing repositories", pattern_text.lower())
        self.assertIn("compound/domain terms overriding general glossary entries", standard_template)
        self.assertIn("deterministic gate-eligible checks", standard_template)
        self.assertIn("ratchet/baseline", standard_template)
        for review_doc in (review_policy, reviewer_role, review_skill):
            self.assertIn("accepted", review_doc)
            self.assertIn("introduced or modified by the diff", review_doc)
            self.assertIn("recommended", review_doc)
        self.assertIn("ACCEPTED_EXCEPTION", review_policy)
        self.assertIn("compound/domain term precedence", review_policy)
        self.assertIn("ACCEPTED_EXCEPTION", reviewer_role)
        self.assertIn("concrete accepted glossary/rule criteria", reviewer_role)
        self.assertIn("module boundary", audit_text)
        self.assertIn("hardcoded user-facing strings", audit_text)
        self.assertIn("grammar and natural phrasing", audit_text)
        self.assertIn("terminology/glossary", audit_text)
        self.assertIn("lean-grill", audit_text)
        self.assertIn("two-track handoff", audit_text)
        self.assertIn("never self-grant exceptions", audit_text)
        self.assertIn("do not pass `scenarios.md`", audit_scenarios)
        self.assertIn("blinding leaks", audit_scenarios)
        self.assertIn("Legacy boundary contract", audit_scenarios)
        self.assertIn("Domain term vs glossary", audit_scenarios)
        self.assertIn("Mandatory i18n deviation", audit_scenarios)


if __name__ == "__main__":
    unittest.main()
