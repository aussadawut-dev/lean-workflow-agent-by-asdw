"""Shared procedure settings remain separate from model/runtime configuration."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SkillEffortTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lean effort ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / '.lean/scripts', self.root / '.lean/scripts')
        self.originals = {}
        for name in ('lean-scope', 'lean-research'):
            path = self.root / '.lean/skills' / name / 'SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_text(f'---\nname: {name}\neffort: medium\n---\nProcedure.\n')
            self.originals[path] = path.read_bytes()
        self.settings = self.root / '.lean/skill-effort.json'
        self.command = ['python3', str(self.root / '.lean/scripts/skill_effort.py'), '--root', str(self.root)]

    def run_cli(self, *args):
        return subprocess.run([*self.command, *args], text=True, capture_output=True)

    def test_inspect_is_read_only_and_defaults_to_standard(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('lean-scope: standard', result.stdout)
        self.assertFalse(self.settings.exists())
        self.assertFalse((self.root / '.agent-runtime').exists())

    def test_global_override_reset_and_no_model_changes(self):
        self.assertEqual(self.run_cli('high').returncode, 0)
        self.assertEqual(self.run_cli('ultra', 'lean-research').returncode, 0)
        self.assertEqual(json.loads(self.settings.read_text()), {'default': 'high', 'skills': {'lean-research': 'ultra'}})
        result = self.run_cli()
        self.assertIn('lean-scope: high', result.stdout)
        self.assertIn('lean-research: ultra', result.stdout)
        self.assertEqual(self.run_cli('reset', 'lean-research').returncode, 0)
        self.assertEqual(json.loads(self.settings.read_text())['skills'], {})
        self.assertEqual(self.run_cli('standard').returncode, 0)
        self.assertEqual(json.loads(self.settings.read_text()), {'default': 'standard', 'skills': {}})
        self.assertEqual(self.run_cli('reset').returncode, 0)
        self.assertFalse(self.settings.exists())
        for path, original in self.originals.items():
            self.assertEqual(path.read_bytes(), original)

    def test_invalid_arguments_and_saved_settings_preserve_bytes(self):
        self.assertEqual(self.run_cli('high').returncode, 0)
        before = self.settings.read_bytes()
        for args in [('max',), ('ultra', 'missing'), ('high', 'lean-scope', 'extra')]:
            self.assertEqual(self.run_cli(*args).returncode, 2)
            self.assertEqual(self.settings.read_bytes(), before)
        for invalid in ('{"default":[],"skills":{}}', '{"default":"max","skills":{}}',
                        '{"default":"high","skills":[]}', '{"default":"high","skills":{"missing":"high"}}',
                        '{"default":"high","skills":{"lean-scope":[]}}',
                        '{"default":"high","default":"ultra","skills":{}}'):
            self.settings.write_text(invalid)
            for args in [(), ('high',), ('reset',)]:
                self.assertEqual(self.run_cli(*args).returncode, 2)
                self.assertEqual(self.settings.read_text(), invalid)

    def test_settings_and_parent_symlinks_never_touch_external_files(self):
        external = self.root / 'external.json'
        external.write_text('{"default":"high","skills":{}}')
        self.settings.symlink_to(external)
        for args in [(), ('ultra',), ('reset',)]:
            self.assertEqual(self.run_cli(*args).returncode, 2)
        self.assertEqual(external.read_text(), '{"default":"high","skills":{}}')
        self.settings.unlink()
        records = self.root / 'records'
        records.mkdir(exist_ok=True)
        (records / '.lean').symlink_to(self.root / '.lean')
        result = subprocess.run([*self.command[:-1], str(records), 'ultra'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.settings.exists())

    def test_explicit_record_root_has_its_own_settings(self):
        records = self.root / 'records'
        records.mkdir()
        result = subprocess.run([*self.command[:-1], str(records), 'ultra', 'lean-scope'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((records / '.lean/skill-effort.json').read_text()),
                         {'default': 'standard', 'skills': {'lean-scope': 'ultra'}})
        self.assertFalse(self.settings.exists())

    def test_concurrent_named_updates_preserve_both_overrides(self):
        processes = [subprocess.Popen([*self.command, level, name], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
                     for level, name in [('high', 'lean-scope'), ('ultra', 'lean-research')]]
        results = [(process, *process.communicate(timeout=10)) for process in processes]
        for process, stdout, stderr in results:
            self.assertEqual(process.returncode, 0, stdout + stderr)
        self.assertEqual(json.loads(self.settings.read_text())['skills'],
                         {'lean-scope': 'high', 'lean-research': 'ultra'})


if __name__ == '__main__':
    unittest.main()
