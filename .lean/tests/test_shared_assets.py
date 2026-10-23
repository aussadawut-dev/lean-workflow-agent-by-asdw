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
from shared_assets import (CORE_LINKS, PRE_PLAYBOOK_LINKS, PRE_PLAYBOOK_SKILLS,
                           RETIRED_SKILLS, SKILL_LINKS, V4_CORE_LINKS, V4_SKILLS,
                           V4_SKILL_LINKS, declared_links)


class SharedAssetsTests(unittest.TestCase):
    def test_pre_playbook_registries_remain_readable_but_mixed_generations_fail(self):
        files = [f'.lean/skills/{name}/SKILL.md' for name in PRE_PLAYBOOK_SKILLS]
        for links in (CORE_LINKS, PRE_PLAYBOOK_LINKS):
            self.assertEqual(declared_links({'schema': 2, 'files': files, 'links': links}), links)
        with self.assertRaises(ValueError):
            declared_links({'schema': 2, 'files': files, 'links': SKILL_LINKS})
        current_files = files + ['.lean/skills/lean-playbook/SKILL.md']
        for links in (CORE_LINKS, SKILL_LINKS):
            self.assertEqual(declared_links({'schema': 2, 'files': current_files, 'links': links}), links)
        with self.assertRaises(ValueError):
            declared_links({'schema': 2, 'files': current_files, 'links': PRE_PLAYBOOK_LINKS})

    def test_previous_core_and_full_registries_remain_readable(self):
        v4_files = [f'.lean/skills/{name}/SKILL.md' for name in V4_SKILLS] + ['AGENTS.md', '.lean/assets.json']
        old_files = [name for name in v4_files if 'skill-effort' not in name and 'skill_effort' not in name
                     and name not in ('.lean/skills/lean-pattern/SKILL.md', '.lean/skills/lean-audit/SKILL.md', '.lean/skills/lean-quality-gate-mode/SKILL.md')]
        old_core = {path: target for path, target in V4_CORE_LINKS.items() if not path.endswith('/lean-skill-effort')}
        self.assertEqual(declared_links({'schema': 2, 'files': old_files, 'links': old_core}), old_core)
        extras = ('lean-clean-queue', 'lean-clean-repo', 'lean-compress', 'lean-model-update',
                  'lean-takeover-workflow', 'lean-use-submodule', 'lean-update-workflow')
        old_full = dict(old_core)
        for tree in ('.agents/skills', '.claude/skills'):
            old_full.update({f'{tree}/{name}': f'../../.lean/skills/{name}' for name in extras})
        self.assertEqual(declared_links({'schema': 2, 'files': old_files, 'links': old_full}), old_full)
        with self.assertRaises(ValueError):
            declared_links({'schema': 2, 'files': old_files, 'links': V4_CORE_LINKS})

    def test_previous_nine_core_and_seven_optional_registry_remains_readable(self):
        v4_files = [f'.lean/skills/{name}/SKILL.md' for name in V4_SKILLS] + ['AGENTS.md', '.lean/assets.json']
        previous_files = [name for name in v4_files
                          if name not in ('.lean/skills/lean-pattern/SKILL.md', '.lean/skills/lean-audit/SKILL.md', '.lean/skills/lean-quality-gate-mode/SKILL.md')]
        core = V4_CORE_LINKS
        full = dict(core)
        for tree in ('.agents/skills', '.claude/skills'):
            for name in ('lean-clean-queue', 'lean-clean-repo', 'lean-compress', 'lean-model-update',
                         'lean-takeover-workflow', 'lean-use-submodule', 'lean-update-workflow'):
                full[f'{tree}/{name}'] = f'../../.lean/skills/{name}'
        for links in (core, full):
            self.assertEqual(declared_links({'schema': 2, 'files': previous_files, 'links': links}), links)
        # A half-installed new generation must not masquerade as a previous release.
        with self.assertRaises(ValueError):
            declared_links({'schema': 2, 'files': previous_files + ['.lean/skills/lean-pattern/SKILL.md'],
                            'links': core})

    def test_intensity_is_shared_but_project_settings_never_ship(self):
        registry = json.loads((ROOT / '.lean/assets.json').read_text())
        self.assertNotIn('.lean/skill-effort.json', registry['files'])
        self.assertNotIn('.codex/quality-gate.json', registry['files'])
        for path in (ROOT / '.lean/skills').glob('*/SKILL.md'):
            content = path.read_text()
            self.assertIn('.lean/policy/SKILL-EFFORT.md', content, path)
            self.assertIn('user-invocable: true', content, path)
            self.assertIn('argument-hint:', content, path)

    def test_previous_pattern_audit_generation_remains_readable(self):
        v4_files = [f'.lean/skills/{name}/SKILL.md' for name in V4_SKILLS] + ['AGENTS.md', '.lean/assets.json']
        files = [name for name in v4_files if name != '.lean/skills/lean-quality-gate-mode/SKILL.md']
        full = dict(V4_CORE_LINKS)
        extras = ('lean-clean-queue', 'lean-clean-repo', 'lean-compress', 'lean-model-update',
                  'lean-takeover-workflow', 'lean-use-submodule', 'lean-update-workflow', 'lean-pattern', 'lean-audit')
        for tree in ('.agents/skills', '.claude/skills'):
            full.update({f'{tree}/{name}': f'../../.lean/skills/{name}' for name in extras})
        for links in (V4_CORE_LINKS, full):
            self.assertEqual(declared_links({'schema': 2, 'files': files, 'links': links}), links)
        for links in (V4_CORE_LINKS, V4_SKILL_LINKS):
            self.assertEqual(declared_links({'schema': 2, 'files': v4_files, 'links': links}), links)

    def test_discovery_uses_one_source_and_resources(self):
        names = sorted(p.name for p in (ROOT / ".lean/skills").iterdir())
        self.assertEqual(len(names), 18)
        self.assertTrue(all(name.startswith("lean-") for name in names), names)
        self.assertIn("lean-prune", names)
        for tree in (".claude/skills", ".agents/skills"):
            for retired in ("clean-queue", *sorted(RETIRED_SKILLS)):
                old = ROOT / tree / retired
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

    def test_compress_routes_reads_by_impact_without_losing_preservation(self):
        content = (ROOT / '.lean/skills/lean-compress/SKILL.md').read_text()
        section = content.split('## Read what the target needs', 1)[1].split('\n## ', 1)[0]
        paragraphs = [p for p in section.split('\n\n') if p.strip()]
        named = next(p for p in paragraphs if p.startswith('`/lean-compress PATH...`'))
        workflow = next(p for p in paragraphs if p.startswith('`/lean-compress workflow`'))
        for required in ('fully read each target', 'canonical', 'callers', 'scripts, hooks and tests',
                         'edits stay limited to the named paths'):
            self.assertIn(required, named)
        self.assertIn('inventory', workflow)
        self.assertIn('prose', workflow)
        self.assertIn('not a full read of every script or test', workflow)
        self.assertNotIn('fully read every authorized workflow file', section)
        for required in ('coverage', 'unread', 'changed revision', 'before/after rule map',
                         'byte-for-byte', 'authorization', 'PROJECT Quality Gate'):
            self.assertIn(required, content)

    def test_optional_skills_bound_rework_and_stop_without_waiving_checks(self):
        # Instruction contracts, not proof of future LLM behavior or token savings.
        for name in ('pattern', 'audit', 'prune', 'catalog', 'compress', 'takeover', 'target', 'update'):
            with self.subTest(skill=name):
                text = (ROOT / f'.lean/skills/lean-{name}/SKILL.md').read_text()
                self.assertIn('delta context', text)
                self.assertIn('Stop when', text)
                self.assertIn('SKILL-EFFORT.md', text)
        takeover = (ROOT / '.lean/skills/lean-takeover/SKILL.md').read_text()
        update = (ROOT / '.lean/skills/lean-update/SKILL.md').read_text()
        self.assertIn('Fully read every authorized workflow file', takeover)
        self.assertIn('Full-read', update)
        self.assertIn('HIGH independent review', update)

    def test_wording_only_review_lowers_reviewer_cost_not_the_floor(self):
        content = (ROOT / '.lean/policy/MODELS.md').read_text()
        section = content.split('## Independent review', 1)[1].split('\n## ', 1)[0]
        self.assertIn('wording-only', section)
        paragraph = next(p for p in section.split('\n\n') if 'wording-only' in p)
        # Cheaper review needs a defined test, an equivalence check and an exit back to the normal reviewer.
        for required in ('economical capable', 'only instruction or documentation prose',
                         'executable code, tests, hooks or configuration disqualifies',
                         'normative keyword', 'YAML frontmatter', 'table layout', 'list hierarchy',
                         'against the before/after text itself',
                         'when any condition fails, when the map is missing or incomplete',
                         'counts as a review round', 'normal starting point'):
            self.assertIn(required, paragraph)
        for kept in ('HIGH floor', 'independence', 'receipt', 'round limits'):
            self.assertIn(kept, paragraph)

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
