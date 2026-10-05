"""Mode transitions preserve records and serialize with worker operations."""
import contextlib
import fcntl
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/workflow.py'
spec = importlib.util.spec_from_file_location('workflow', SCRIPT)
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)


class DowngradeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / '.lean/templates').mkdir(parents=True)
        templates = SCRIPT.parents[1] / 'templates'
        for name in ('tracker.md', 'queue-item.json'):
            (self.root / '.lean/templates' / name).write_bytes((templates / name).read_bytes())
        (self.root / '.gitignore').write_text('.agent-runtime/\n')

    def cli(self, *args, ok=True):
        result = subprocess.run(['python3', str(SCRIPT), '--root', str(self.root), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def setup_mode(self, mode='full'):
        self.cli('configure', mode, '--execution', 'delegated')
        value = json.loads((self.root / '.lean/config.json').read_text())
        value['project_extension'] = {'keep': True}
        (self.root / '.lean/config.json').write_text(json.dumps(value))

    def tracker(self, status='PLANNED'):
        path = self.root / 'docs/tracking/TCK001.md'
        path.write_text(f'# Task\nStatus: {status}\n\n## Evidence\n- test evidence\n')
        return path

    def item(self, status='READY'):
        path = self.root / '.agents/queue/items/Q0001.json'
        path.write_text(json.dumps({'id': 'Q0001', 'title': 'Task', 'tracker': 'TCK001',
                                   'status': status, 'dependencies': [], 'scopes': ['src'],
                                   'evidence': 'verified' if status == 'DONE' else None}))
        return path

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def test_all_routes_preserve_records_and_config_extensions(self):
        for source, target in [('full', 'tracker'), ('full', 'standard'), ('tracker', 'standard')]:
            with self.subTest(source=source, target=target):
                self.setup_mode(source)
                tracker = self.tracker()
                if source == 'full':
                    self.item()
                before = self.snapshot()
                self.cli('downgrade', target, '--apply', '--keep-pending')
                self.assertEqual(tracker.read_bytes(), before['docs/tracking/TCK001.md'])
                for name, content in before.items():
                    if name != '.lean/config.json':
                        self.assertEqual((self.root / name).read_bytes(), content)
                value = json.loads(self.cli('show').stdout)
                self.assertEqual(value['mode'], target)
                self.assertEqual(value['execution'], 'delegated')
                self.assertEqual(value['project_extension'], {'keep': True})
                self.assertTrue(value['configured'])
                # Reset only the mode for the next route; retain every record.
                if target != "standard":
                    self.cli("downgrade", "standard", "--apply", "--keep-pending")

    def test_preview_preserves_entire_tree_and_expired_claim(self):
        self.setup_mode()
        self.tracker()
        self.item()
        claim = json.loads(self.cli('queue', 'claim', '--id', 'Q0001', '--agent', 'worker',
                                   '--request-id', 'request-123').stdout)
        claim['expires_at'] = 0
        path = self.root / '.agent-runtime/claims/Q0001.json'
        path.write_text(json.dumps(claim))
        before = self.snapshot()
        result = self.cli('downgrade', 'tracker', '--dry-run', ok=False)
        report = json.loads(result.stdout)
        self.assertEqual(report['pending_queue'], ['Q0001'])
        self.assertEqual(report['expired_claims'], ['Q0001'])
        self.assertEqual(self.snapshot(), before)
        self.cli('downgrade', 'tracker', '--apply', '--keep-pending')
        self.assertEqual(path.read_bytes(), before['.agent-runtime/claims/Q0001.json'])

    def test_preview_without_runtime_does_not_create_files(self):
        self.setup_mode('tracker')
        (self.root / ".agent-runtime/queue.lock").unlink()
        (self.root / ".agent-runtime").rmdir()
        # Preview must not create a runtime directory or lock.
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.root.rglob('*') if p.is_file()}
        self.cli('downgrade', 'standard', '--dry-run')
        after = {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.root / ".agent-runtime").exists())

    def test_active_lease_refuses_without_mutating_records(self):
        self.setup_mode()
        self.tracker()
        self.item()
        self.cli('queue', 'claim', '--id', 'Q0001', '--agent', 'worker', '--request-id', 'request-123')
        before = self.snapshot()
        result = self.cli('downgrade', 'tracker', '--apply', '--keep-pending', ok=False)
        self.assertIn('active claims', result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_active_tracker_states_block_standard_but_not_tracker(self):
        self.setup_mode()
        for state in ('IN_PROGRESS', 'VALIDATING', 'REVIEWING'):
            self.tracker(state)
            result = self.cli('downgrade', 'standard', '--apply', '--keep-pending', ok=False)
            self.assertIn('TCK001', result.stdout)
        self.cli('downgrade', 'tracker', '--apply')

    def test_pending_work_requires_explicit_preservation(self):
        self.setup_mode()
        self.tracker('BLOCKED')
        self.item('BLOCKED')
        before = self.snapshot()
        self.cli('downgrade', 'standard', '--apply', ok=False)
        self.assertEqual(before, self.snapshot())
        self.cli('downgrade', 'standard', '--apply', '--keep-pending')

    def test_malformed_records_and_claims_cannot_be_hidden(self):
        self.setup_mode()
        path = self.tracker()
        original = path.read_text()
        cases = [(path, 'Status: BOGUS\n'),
                 (self.root / '.agents/queue/items/Q0001.json', '{}'),
                 (self.root / '.agent-runtime/claims/Q0001.json', '{}')]
        for bad, content in cases:
            with self.subTest(path=bad):
                bad.parent.mkdir(parents=True, exist_ok=True)
                bad.write_text(content)
                before = self.snapshot()
                self.cli('downgrade', 'standard', '--apply', '--keep-pending', ok=False)
                self.assertEqual(before, self.snapshot())
                bad.unlink()
                path.write_text(original)

    def test_round_trip_checks_done_tracker_against_retained_queue(self):
        self.setup_mode()
        self.tracker()
        queue = self.item()
        self.cli('downgrade', 'tracker', '--apply', '--keep-pending')
        self.cli('tracker', 'status', '--id', 'TCK001', '--status', 'DONE', '--evidence', 'tracker complete')
        before = self.snapshot()
        result = self.cli('configure', 'full', ok=False)
        self.assertIn('unfinished queue', result.stderr)
        self.assertEqual((self.root / '.lean/config.json').read_bytes(), before['.lean/config.json'])
        self.cli('tracker', 'status', '--id', 'TCK001', '--status', 'PLANNED')
        self.cli('configure', 'full')
        self.assertEqual(queue.read_bytes(), before['.agents/queue/items/Q0001.json'])
        self.cli('check')

    def test_finished_work_needs_no_pending_acknowledgment(self):
        self.setup_mode()
        tracker = self.tracker('DONE')
        queue = self.item('DONE')
        before = self.snapshot()
        result = self.cli('downgrade', 'standard', '--apply')
        self.assertTrue(json.loads(result.stdout)['applied'])
        self.assertEqual(tracker.read_bytes(), before['docs/tracking/TCK001.md'])
        self.assertEqual(queue.read_bytes(), before['.agents/queue/items/Q0001.json'])
        self.cli('configure', 'full')
        self.cli('check')

    def test_same_mode_upgrade_and_implicit_downgrade_are_refused(self):
        self.setup_mode('tracker')
        for target in ('tracker', 'full'):
            self.cli('downgrade', target, '--apply', ok=False)
        self.cli('configure', 'standard', ok=False)
        self.cli('downgrade', 'standard', ok=False)  # explicit preview/apply required

    def test_real_waiting_worker_observes_downgrade_before_claim(self):
        self.setup_mode()
        self.tracker()
        self.item()
        # Child signals immediately before acquiring the actual shared flock.
        program = """
import importlib.util, sys, contextlib
from pathlib import Path
spec = importlib.util.spec_from_file_location('workflow', sys.argv[1])
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
original = w.locked
@contextlib.contextmanager
def signalled(root, **kwargs):
    print('waiting', flush=True)
    with original(root, **kwargs):
        yield
w.locked = signalled
sys.argv = [sys.argv[1], '--root', sys.argv[2], 'queue', 'claim',
            '--id', 'Q0001', '--agent', 'worker', '--request-id', 'request-123']
sys.exit(w.main())
"""
        lock_path = self.root / '.agent-runtime/queue.lock'
        with lock_path.open('r') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            child = subprocess.Popen(['python3', '-c', program, str(SCRIPT), str(self.root)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                # A bounded pipe wait makes test failures unable to hang the suite.
                import select
                ready, _, _ = select.select([child.stdout], [], [], 5)
                self.assertTrue(ready, 'worker did not reach lock')
                self.assertEqual(child.stdout.readline().strip(), 'waiting')
                self.assertIsNone(child.poll())
                # Parent owns the same lock that apply uses; run the real transition.
                @contextlib.contextmanager
                def already_owned(root, **kwargs):
                    yield
                with patch.object(workflow, 'locked', already_owned):
                    self.assertEqual(workflow.downgrade(self.root, 'tracker', True, True), 0)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                try:
                    stdout, stderr = child.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.communicate()
                    raise
        self.assertEqual(child.returncode, 2, stdout + stderr)
        self.assertIn('full mode required', stderr)
        self.assertFalse((self.root / '.agent-runtime/claims/Q0001.json').exists())

    def test_apply_rechecks_live_claim_created_after_preview(self):
        self.setup_mode()
        self.tracker()
        self.item()
        self.cli('downgrade', 'tracker', '--dry-run', '--keep-pending')
        self.cli('queue', 'claim', '--id', 'Q0001', '--agent', 'worker', '--request-id', 'request-123')
        before = self.snapshot()
        self.cli('downgrade', 'tracker', '--apply', '--keep-pending', ok=False)
        self.assertEqual(before, self.snapshot())

    def test_worker_rechecks_mode_after_waiting_for_lock(self):
        self.setup_mode()
        self.tracker()
        self.item()
        @contextlib.contextmanager
        def changed_while_waiting(root, **kwargs):
            value = workflow.config(root)
            value['mode'] = 'standard'
            workflow.write_json(root / '.lean/config.json', value)
            yield
        for command, args in [(workflow.queue_command, SimpleNamespace(action='claim', id='Q0001',
                                  agent='worker', request_id='request-123')),
                              (workflow.tracker_command, SimpleNamespace(action='status', id='TCK001',
                                  status='IN_PROGRESS', evidence=''))]:
            self.setup_mode()
            before = self.tracker().read_bytes()
            with patch.object(workflow, 'locked', changed_while_waiting):
                with self.assertRaisesRegex(ValueError, 'mode required'):
                    command(self.root, args)
            self.assertEqual((self.root / 'docs/tracking/TCK001.md').read_bytes(), before)
            self.assertFalse((self.root / '.agent-runtime/claims/Q0001.json').exists())


if __name__ == '__main__':
    unittest.main()
