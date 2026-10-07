"""Cleanup invariants in disposable repositories; never clean the real checkout."""
import importlib.util
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/clean_repo.py'
spec = importlib.util.spec_from_file_location('clean_repo', SCRIPT)
clean = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clean)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lean-clean-tests-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'repo'
        self.root.mkdir()
        self.session = self.base / 'session'
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Cleanup Test')
        self.file('obsolete.py', 'print("old")\n')
        self.file('index.md', 'obsolete.py\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args])

    def file(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
        return path

    def item(self, name='obsolete.py', action='remove', **kwargs):
        return dict(path=name, action=action, reason='Retired fixture', evidence=['Callers inspected'],
                    impact='Remove old entry', checks=['Fixture validation'], **kwargs)

    def plan(self, *items):
        return clean.make_plan(self.root, self.session, {'items': list(items or [self.item()])})

    def apply(self, plan):
        return clean.execute(self.session, plan['plan_id'])

    def test_inventory_is_read_only_and_skips_private_boundaries(self):
        self.file('.env', 'secret')
        self.file('__pycache__/one.pyc', 'bytecode')
        self.file('draft.md', 'work in progress')
        self.file('nested/.git/HEAD', 'not a real repo')
        (self.root / 'link').symlink_to(self.base)
        before = self.git('status', '--porcelain', '-z')
        original_open = Path.open
        def guarded_open(path, *args, **kwargs):
            if path.name == '.env':
                raise AssertionError('scan read credentials')
            return original_open(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded_open):
            inventory = clean.scan(self.root)
        rows = {r['path']: r for r in inventory['entries']}
        self.assertTrue(rows['.env']['protected'])
        self.assertTrue(rows['draft.md']['protected'])
        self.assertEqual(rows['nested']['protected'], 'nested repository boundary')
        self.assertEqual(rows['link']['protected'], 'symlink boundary')
        self.assertFalse(rows['__pycache__/one.pyc']['protected'])
        self.assertEqual(before, self.git('status', '--porcelain', '-z'))
        self.assertFalse(self.session.exists())

    def test_remove_replace_restore_preserves_bytes_modes_and_index(self):
        source = self.root / 'obsolete.py'
        source.write_bytes(b'print("old")\r\n')
        source.chmod(0o755)
        self.git('add', '.')
        self.git('commit', '-qm', 'mode fixture')
        index = self.git('ls-files', '--stage')
        original = source.read_bytes()
        plan = self.plan(self.item(), self.item('index.md', 'replace', replacement='current.py\n'))
        self.assertEqual(source.read_bytes(), original)
        self.apply(plan)
        self.assertFalse(source.exists())
        self.assertEqual((self.root / 'index.md').read_text(), 'current.py\n')
        self.assertEqual(index, self.git('ls-files', '--stage'))
        self.apply(plan)  # idempotent retry
        clean.execute(self.session, restore=True)
        clean.execute(self.session, restore=True)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(source.stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.root / 'index.md').read_text(), 'obsolete.py\n')
        self.assertEqual(index, self.git('ls-files', '--stage'))

    def test_generated_directory_and_empty_directories_restore(self):
        self.file('output/generated.bin', 'generated')
        (self.root / 'output/empty').mkdir()
        plan = self.plan(self.item('output', regenerate='Verified project build command'))
        self.apply(plan)
        self.assertFalse((self.root / 'output').exists())
        clean.execute(self.session, restore=True)
        self.assertEqual((self.root / 'output/generated.bin').read_text(), 'generated')
        self.assertTrue((self.root / 'output/empty').is_dir())

    def test_protected_dirty_staged_untracked_and_hardlinks_refused(self):
        cases = ['.env', 'draft.md', '.env-folder/public.txt', '.agents/queue/history/item.json',
                 '.claude/.gate-cache', 'data.sqlite', '.lean/skills', 'LICENSE']
        for name in cases:
            with self.subTest(name=name):
                if name == '.lean/skills':
                    (self.root / name).mkdir(parents=True)
                else:
                    self.file(name, 'retained')
                with self.assertRaises(ValueError):
                    self.plan(self.item(name))
        os.link(self.root / 'obsolete.py', self.root / 'hardlink')
        with self.assertRaises(ValueError):
            self.plan()
        (self.root / 'hardlink').unlink()
        self.file('obsolete.py', 'dirty')
        with self.assertRaises(ValueError):
            self.plan()
        self.git('add', 'obsolete.py')
        with self.assertRaises(ValueError):
            self.plan()
        self.assertFalse(self.session.exists())

    def test_protected_names_are_case_insensitive(self):
        for name in ('.GIT/config', '.CLAUDE/state', 'AGENTS.md', '.LEAN/PROJECT.md', 'data.SQLITE', '.ENV/private'):
            with self.subTest(name=name):
                self.assertIsNotNone(clean.protected(name))

    def test_registered_workflow_assets_retained_but_obsolete_files_eligible(self):
        self.file('.lean/scripts/current.py', 'active helper')
        self.file('.lean/scripts/obsolete.py', 'retired helper')
        self.file('.lean/assets.json', json.dumps({'files': ['.lean/scripts/current.py']}))
        self.git('add', '.')
        self.git('commit', '-qm', 'workflow fixture')
        with self.assertRaises(ValueError):
            self.plan(self.item('.lean/scripts/current.py'))
        with self.assertRaises(ValueError):
            self.plan(self.item('.lean/scripts'))
        plan = self.plan(self.item('.lean/scripts/obsolete.py'))
        self.apply(plan)
        self.assertTrue((self.root / '.lean/scripts/current.py').exists())
        clean.execute(self.session, restore=True)

    def test_symlink_nested_repo_traversal_and_overlaps_refused(self):
        self.file('nested/.git/HEAD', 'boundary')
        (self.root / 'link').symlink_to(self.base)
        for name in ('../outside', '/absolute', 'link', 'link/file', 'nested', '.git/config'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.plan(self.item(name, regenerate='build'))
        with self.assertRaises(ValueError):
            self.plan(self.item(), self.item())

    def test_apply_requires_approval_and_refuses_all_drift_before_mutation(self):
        plan = self.plan(self.item(), self.item('index.md'))
        with self.assertRaises(ValueError):
            clean.execute(self.session, 'wrong')
        self.file('obsolete.py', 'changed since proposal')
        with self.assertRaises(ValueError):
            self.apply(plan)
        self.assertTrue((self.root / 'index.md').exists())
        self.assertEqual((self.root / 'obsolete.py').read_text(), 'changed since proposal')

    def test_index_changes_and_new_directory_children_block(self):
        plan = self.plan()
        self.git('rm', '--cached', 'obsolete.py')
        with self.assertRaises(ValueError):
            self.apply(plan)
        self.assertTrue((self.root / 'obsolete.py').exists())
        self.session = self.base / 'second'
        self.file('output/file', 'output')
        plan = self.plan(self.item('output', regenerate='build'))
        self.file('output/new', 'new work')
        with self.assertRaises(ValueError):
            self.apply(plan)
        self.assertTrue((self.root / 'output/file').exists())

    def test_restore_refuses_new_file_or_later_replacement_edit(self):
        plan = self.plan(self.item(), self.item('index.md', 'replace', replacement='new\n'))
        self.apply(plan)
        self.file('obsolete.py', 'new work')
        with self.assertRaises(ValueError):
            clean.execute(self.session, restore=True)
        self.assertEqual((self.root / 'index.md').read_text(), 'new\n')
        (self.root / 'obsolete.py').unlink()
        self.file('index.md', 'later edit')
        with self.assertRaises(ValueError):
            clean.execute(self.session, restore=True)
        self.assertEqual((self.root / 'index.md').read_text(), 'later edit')

    def test_interrupt_after_remove_can_resume_or_restore(self):
        for recovery in ('apply', 'restore'):
            with self.subTest(recovery=recovery):
                self.session = self.base / recovery
                plan = self.plan()
                original = clean.save
                def interrupted(path, value):
                    if value.get('done') == ['obsolete.py']:
                        raise OSError('simulated interruption after unlink')
                    return original(path, value)
                with patch.object(clean, 'save', side_effect=interrupted), self.assertRaises(OSError):
                    self.apply(plan)
                self.assertFalse((self.root / 'obsolete.py').exists())
                if recovery == 'apply':
                    self.apply(plan)
                clean.execute(self.session, restore=True)
                self.assertTrue((self.root / 'obsolete.py').exists())

    def test_interrupt_after_replacement_and_restoration_resumes(self):
        plan = self.plan(self.item('index.md', 'replace', replacement='new\n'))
        original = clean.save
        def interrupted(path, value):
            if value.get('done') == ['index.md']:
                raise OSError('simulated interruption after replacement')
            return original(path, value)
        with patch.object(clean, 'save', side_effect=interrupted), self.assertRaises(OSError):
            self.apply(plan)
        self.apply(plan)
        def restore_interrupt(path, value):
            if value.get('restored') == ['index.md']:
                raise OSError('simulated interruption after restoration')
            return original(path, value)
        with patch.object(clean, 'save', side_effect=restore_interrupt), self.assertRaises(OSError):
            clean.execute(self.session, restore=True)
        clean.execute(self.session, restore=True)
        self.assertEqual((self.root / 'index.md').read_text(), 'obsolete.py\n')

    def test_plan_tamper_session_symlinks_and_inside_session_refused(self):
        with self.assertRaises(ValueError):
            clean.make_plan(self.root, self.root / 'session', {'items': [self.item()]})
        plan = self.plan()
        data = json.loads((self.session / 'plan.json').read_text())
        data['operations'][0]['path'] = 'index.md'
        (self.session / 'plan.json').write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.apply(plan)
        (self.session / 'plan.json').unlink()
        (self.session / 'plan.json').symlink_to(self.root / 'obsolete.py')
        with self.assertRaises(ValueError):
            self.apply(plan)

    def test_cli_scan_and_unknown_options(self):
        result = subprocess.run([sys.executable, str(SCRIPT), 'scan', '--root', str(self.root)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['read_only'])
        invalid = subprocess.run([sys.executable, str(SCRIPT), 'scan', '--root', str(self.root), '--apply'], capture_output=True)
        self.assertNotEqual(invalid.returncode, 0)

    def test_cli_plan_apply_restore_roundtrip(self):
        proposal = self.base / 'proposal.json'
        proposal.write_text(json.dumps({'items': [self.item()]}))
        def run(*args):
            result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        plan = run('plan', '--root', str(self.root), '--session', str(self.session), '--proposal', str(proposal))
        self.assertEqual(run('apply', '--session', str(self.session), '--approval', plan['plan_id'])['phase'], 'applied')
        self.assertEqual(run('restore', '--session', str(self.session))['phase'], 'restored')

    def test_lock_contention_and_snapshot_integrity_block_mutations(self):
        plan = self.plan()
        with (self.session / 'lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(OSError):
                self.apply(plan)
        data = json.loads((self.session / 'plan.json').read_text())
        data['operations'][0]['original'] = clean.encoded(b'corrupted')
        journal = json.loads((self.session / 'journal.json').read_text())
        journal['plan_id'] = clean.digest(clean.packed(data))
        (self.session / 'plan.json').write_text(json.dumps(data))
        (self.session / 'journal.json').write_text(json.dumps(journal))
        with self.assertRaisesRegex(ValueError, 'snapshot integrity'):
            clean.execute(self.session, journal['plan_id'])
        self.assertTrue((self.root / 'obsolete.py').exists())

    def test_session_in_other_repository_or_symlink_refused(self):
        foreign = self.base / 'foreign'
        foreign.mkdir()
        subprocess.run(['git', 'init', '-q', str(foreign)], check=True)
        for session in (foreign / 'session', self.base / 'alias' / 'session'):
            if session.parent.name == 'alias':
                session.parent.symlink_to(self.base)
            with self.assertRaises(ValueError):
                clean.make_plan(self.root, session, {'items': [self.item()]})

    def test_directory_with_protected_child_cannot_be_regenerated(self):
        self.file('output/.env', 'private')
        self.file('output/cache', 'disposable')
        with self.assertRaises(ValueError):
            self.plan(self.item('output', regenerate='build'))
        self.assertEqual((self.root / 'output/.env').read_text(), 'private')

    def test_untracked_empty_directories_and_children_preserved_by_default(self):
        (self.root / 'personal-empty').mkdir()
        (self.root / 'fake.pyc').mkdir()
        self.file('tracked-tree/obsolete.py', 'retired')
        self.git('add', 'tracked-tree/obsolete.py')
        self.git('commit', '-qm', 'tracked subtree')
        (self.root / 'tracked-tree/personal-empty').mkdir()
        for name in ('personal-empty', 'fake.pyc', 'tracked-tree/personal-empty'):
            with self.subTest(name=name):
                rows = {row['path']: row for row in clean.scan(self.root)['entries']}
                self.assertTrue(rows[name]['protected'])
                with self.assertRaises(ValueError):
                    self.plan(self.item(name))
                self.assertTrue((self.root / name).is_dir())
        with self.assertRaises(ValueError):
            self.plan(self.item('tracked-tree'))

    def test_permissions_drift_binary_replacements_and_special_files_block(self):
        plan = self.plan()
        (self.root / 'obsolete.py').chmod(0o755)
        with self.assertRaises(ValueError):
            self.apply(plan)
        self.session = self.base / 'binary-session'
        (self.root / 'binary').write_bytes(b'\x00\xff')
        self.git('add', '.')
        self.git('commit', '-qm', 'binary fixture')
        with self.assertRaises(ValueError):
            self.plan(self.item('binary', 'replace', replacement='text'))
        os.mkfifo(self.root / 'pipe')
        with self.assertRaises(ValueError):
            self.plan(self.item('pipe', regenerate='build'))


if __name__ == '__main__':
    unittest.main()
