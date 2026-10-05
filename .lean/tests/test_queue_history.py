"""Completion timestamps are trustworthy input for age-based queue cleanup."""
import json
import contextlib
import hashlib
import importlib.util
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/workflow.py'


class QueueHistoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / '.lean/templates').mkdir(parents=True)
        for name in ('tracker.md', 'queue-item.json'):
            (self.root / '.lean/templates' / name).write_bytes((SCRIPT.parents[1] / 'templates' / name).read_bytes())
        (self.root / '.gitignore').write_text('.agent-runtime/\n')
        self.cli('configure', 'full')
        (self.root / 'docs/tracking/TCK001.md').write_text('# Task\nStatus: PLANNED\n\n## Evidence\n')
        self.item_path = self.root / '.agents/queue/items/Q0001.json'
        self.item_path.write_text(json.dumps({'id': 'Q0001', 'title': 'Task', 'tracker': 'TCK001',
             'status': 'READY', 'scopes': ['src'], 'dependencies': [], 'evidence': None}))

    def cli(self, *args, ok=True):
        result = subprocess.run(['python3', str(SCRIPT), '--root', str(self.root), *args],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_completion_records_utc_time_without_changing_creation_time(self):
        item = json.loads(self.item_path.read_text())
        item['created_at'] = '2020-01-01T00:00:00Z'
        self.item_path.write_text(json.dumps(item))
        before = datetime.now(timezone.utc)
        claim = json.loads(self.cli('queue', 'claim', '--id', 'Q0001', '--agent', 'worker',
                                    '--request-id', 'history-request-0001').stdout)
        self.cli('queue', 'complete', '--id', 'Q0001', '--token', claim['token'], '--evidence', 'tests passed')
        item = json.loads(self.item_path.read_text())
        completed = datetime.fromisoformat(item['completed_at'].replace('Z', '+00:00'))
        self.assertLessEqual(before, completed)
        self.assertLessEqual(completed, datetime.now(timezone.utc))
        self.assertEqual(item['created_at'], '2020-01-01T00:00:00Z')

    def test_invalid_completion_time_is_rejected(self):
        item = json.loads(self.item_path.read_text())
        item.update(status='DONE', evidence='tests passed', completed_at='yesterday')
        self.item_path.write_text(json.dumps(item))
        self.cli('check', ok=False)

    def done(self, age=None, item_id='Q0001', dependencies=()):
        item = json.loads(self.item_path.read_text())
        item.update(id=item_id, status='DONE', evidence='tests passed', dependencies=list(dependencies))
        if age is not None:
            item['completed_at'] = (datetime.now(timezone.utc) - timedelta(days=age)).isoformat()
        path = self.item_path.parent / (item_id + '.json')
        path.write_text(json.dumps(item, indent=2) + '\n')
        return path

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_old_keeps_recent_pending_and_unknown_age(self):
        old = self.done(31)
        recent = self.done(29, 'Q0002')
        unknown = self.done(None, 'Q0003')
        item = json.loads(unknown.read_text())
        item.pop('completed_at', None)
        unknown.write_text(json.dumps(item))
        blocked = self.done(40, 'Q0004')
        item = json.loads(blocked.read_text())
        item.update(status='BLOCKED', evidence=None)
        blocked.write_text(json.dumps(item))
        before = self.snapshot()
        report = json.loads(self.cli('clean-queue', 'old', '--dry-run').stdout)
        self.assertEqual(report['selected'], ['Q0001'])
        self.assertEqual(report['unknown_age'], ['Q0003'])
        self.assertEqual(before, self.snapshot())
        self.cli('clean-queue', 'old', '--apply')
        self.assertFalse(old.exists())
        for path in (recent, unknown, blocked):
            self.assertEqual(path.read_bytes(), before[str(path.relative_to(self.root))])

    def test_all_keeps_original_bytes_unknown_fields_and_tracker(self):
        path = self.done()
        original = json.loads(path.read_text())
        original['project_notes'] = {'keep': ['everything']}
        raw = json.dumps(original, indent=4).replace('\n', '\r\n').encode() + b'\r\n'
        path.write_bytes(raw)
        tracker = (self.root / 'docs/tracking/TCK001.md').read_bytes()
        self.cli('clean-queue', 'all', '--apply')
        history = self.root / '.agents/queue/history/Q0001.json'
        record = json.loads(history.read_text())
        self.assertEqual(record['content'].encode(), raw)
        self.assertEqual(record['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(record['reason'], 'all')
        self.assertEqual(json.loads(self.cli('queue', 'history', '--id', 'Q0001').stdout), record)
        self.assertEqual((self.root / 'docs/tracking/TCK001.md').read_bytes(), tracker)
        self.assertNotIn('Q0001', self.cli('queue', 'list').stdout)
        self.cli('check')
        self.cli('queue', 'claim', '--id', 'Q0001', '--agent', 'worker', '--request-id', 'history-claim-123', ok=False)
        before = self.snapshot()
        self.cli('clean-queue', 'all', '--apply')
        self.assertEqual(before, self.snapshot())

    def test_archived_dependency_and_done_tracker_still_validate(self):
        self.done(40)
        other = self.done(1, 'Q0002', ['Q0001'])
        item = json.loads(other.read_text())
        item.update(status='READY', evidence=None)
        item.pop('completed_at')
        other.write_text(json.dumps(item))
        self.cli('clean-queue', 'old', '--apply')
        claim = json.loads(self.cli('queue', 'claim', '--id', 'Q0002', '--agent', 'worker',
                                   '--request-id', 'history-request-0002').stdout)
        self.cli('queue', 'complete', '--id', 'Q0002', '--token', claim['token'], '--evidence', 'tests passed')
        self.cli('tracker', 'status', '--id', 'TCK001', '--status', 'DONE', '--evidence', 'review passed')
        self.cli('clean-queue', 'all', '--apply')
        self.cli('check')
        self.cli('downgrade', 'standard', '--apply')
        self.cli('configure', 'full')
        self.cli('check')

    def test_active_claim_on_done_record_blocks_cleanup_without_changes(self):
        claim = json.loads(self.cli('queue', 'claim', '--id', 'Q0001', '--agent', 'worker',
                                   '--request-id', 'history-request-0001').stdout)
        self.done(40)  # interrupted completion: evidence written, lease still present
        before = self.snapshot()
        self.cli('clean-queue', 'all', '--apply', ok=False)
        self.assertEqual(before, self.snapshot())
        self.cli('queue', 'complete', '--id', 'Q0001', '--token', claim['token'], '--evidence', 'tests passed')
        self.cli('clean-queue', 'all', '--apply')

    def test_all_leaves_live_ready_and_blocked_queue_items(self):
        self.done(40)
        ready = self.done(10, 'Q0002')
        blocked = self.done(10, 'Q0003')
        for path, state in ((ready, 'READY'), (blocked, 'BLOCKED')):
            value = json.loads(path.read_text())
            value.update(status=state, evidence=None, scopes=[path.stem])
            value.pop('completed_at')
            path.write_text(json.dumps(value))
        self.cli('queue', 'claim', '--id', 'Q0002', '--agent', 'worker', '--request-id', 'history-ready-0002')
        before = self.snapshot()
        self.cli('clean-queue', 'all', '--apply')
        for path in (ready, blocked):
            self.assertEqual(path.read_bytes(), before[str(path.relative_to(self.root))])
        self.assertIn('Q0002 READY worker', self.cli('queue', 'list').stdout)

    def test_30_day_boundary_uses_completion_time_not_file_mtime(self):
        spec = importlib.util.spec_from_file_location('workflow_history', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        now = datetime(2026, 10, 5, tzinfo=timezone.utc).timestamp()
        self.done()
        value = json.loads(self.item_path.read_text())
        value['completed_at'] = datetime.fromtimestamp(now - 30 * 86400, timezone.utc).isoformat()
        self.item_path.write_text(json.dumps(value))
        with patch.object(module.time, 'time', return_value=now), contextlib.redirect_stdout(__import__('io').StringIO()) as output:
            module.clean_queue(self.root, 'old', False)
        self.assertEqual(json.loads(output.getvalue())['selected'], [])
        value['completed_at'] = datetime.fromtimestamp(now - 30 * 86400 - 1, timezone.utc).isoformat()
        self.item_path.write_text(json.dumps(value))
        with patch.object(module.time, 'time', return_value=now), contextlib.redirect_stdout(__import__('io').StringIO()) as output:
            module.clean_queue(self.root, 'old', False)
        self.assertEqual(json.loads(output.getvalue())['selected'], ['Q0001'])

    def test_interrupted_archive_is_readable_and_retry_finishes_removal(self):
        self.done(40)
        original = self.item_path.read_bytes()
        self.cli('clean-queue', 'all', '--apply')
        # Simulate interruption after archive publication but before source unlink.
        self.item_path.write_bytes(original)
        self.assertNotIn('Q0001', self.cli('queue', 'list').stdout)
        self.cli('check')
        before = (self.root / '.agents/queue/history/Q0001.json').read_bytes()
        self.cli('clean-queue', 'old', '--apply')
        self.assertFalse(self.item_path.exists())
        self.assertEqual((self.root / '.agents/queue/history/Q0001.json').read_bytes(), before)

    def test_reused_archived_id_and_corrupt_history_are_rejected(self):
        self.done(40)
        original = self.item_path.read_bytes()
        self.cli('clean-queue', 'all', '--apply')
        self.item_path.write_bytes(original.replace(b'tests passed', b'new work'))
        self.cli('check', ok=False)
        self.item_path.unlink()
        archive = self.root / '.agents/queue/history/Q0001.json'
        record = json.loads(archive.read_text())
        record['content'] = record['content'].replace('tests passed', 'changed')
        archive.write_text(json.dumps(record))
        self.cli('check', ok=False)
        before = self.snapshot()
        self.cli('clean-queue', 'all', '--apply', ok=False)
        self.assertEqual(before, self.snapshot())

    def test_expired_lease_preserved_and_preview_never_creates_runtime(self):
        self.done(40)
        runtime = self.root / '.agent-runtime'
        (runtime / 'queue.lock').unlink()
        runtime.rmdir()
        before = self.snapshot()
        self.cli('clean-queue', 'old', '--dry-run')
        self.assertFalse(runtime.exists())
        self.assertEqual(before, self.snapshot())


    def test_expired_claim_is_preserved_during_cleanup(self):
        claim = json.loads(self.cli('queue', 'claim', '--id', 'Q0001', '--agent', 'worker',
                                   '--request-id', 'expired-history-0001').stdout)
        claim['expires_at'] = 0
        path = self.root / '.agent-runtime/claims/Q0001.json'
        path.write_text(json.dumps(claim))
        self.done(40)
        original = path.read_bytes()
        self.cli('clean-queue', 'all', '--apply')
        self.assertEqual(path.read_bytes(), original)
        self.cli('check')

    def test_completion_retry_keeps_original_completion_time(self):
        claim = json.loads(self.cli('queue', 'claim', '--id', 'Q0001', '--agent', 'worker',
                                   '--request-id', 'retry-history-0001').stdout)
        self.cli('queue', 'complete', '--id', 'Q0001', '--token', claim['token'], '--evidence', 'tests passed')
        before = self.item_path.read_bytes()
        path = self.root / '.agent-runtime/claims/Q0001.json'
        path.write_text(json.dumps(claim))  # interrupted lease cleanup
        self.cli('queue', 'complete', '--id', 'Q0001', '--token', claim['token'], '--evidence', 'tests passed')
        self.assertEqual(self.item_path.read_bytes(), before)

    def test_actual_unlink_failure_is_recoverable_without_loss(self):
        spec = importlib.util.spec_from_file_location('workflow_history', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.done(40)
        before = self.item_path.read_bytes()
        original_unlink = Path.unlink
        def interrupted(path, *args, **kwargs):
            if path == self.item_path:
                raise OSError('simulated interruption')
            return original_unlink(path, *args, **kwargs)
        with patch.object(Path, 'unlink', interrupted):
            with self.assertRaisesRegex(OSError, 'simulated interruption'):
                module.clean_queue(self.root, 'all', True)
        self.assertEqual(self.item_path.read_bytes(), before)
        history = self.root / '.agents/queue/history/Q0001.json'
        self.assertEqual(json.loads(history.read_text())['content'].encode(), before)
        self.cli('check')
        self.cli('clean-queue', 'all', '--apply')
        self.assertFalse(self.item_path.exists())

    def test_archive_publication_failure_never_removes_source(self):
        spec = importlib.util.spec_from_file_location('workflow_history', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.done(40)
        before = self.snapshot()
        with patch.object(module, 'write_json', side_effect=OSError('disk write failed')):
            with self.assertRaisesRegex(OSError, 'disk write failed'):
                module.clean_queue(self.root, 'all', True)
        self.assertEqual(before, self.snapshot())

    def test_second_item_failure_retains_first_archive_and_supports_retry(self):
        spec = importlib.util.spec_from_file_location('workflow_history', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.done(40)
        second = self.done(40, 'Q0002', ['Q0001'])
        second_bytes = second.read_bytes()
        original_write = module.write_json
        def fail_second(path, value):
            if path.name == 'Q0002.json':
                raise OSError('second item failed')
            original_write(path, value)
        with patch.object(module, 'write_json', fail_second):
            with self.assertRaisesRegex(OSError, 'second item failed'):
                module.clean_queue(self.root, 'all', True)
        self.assertFalse(self.item_path.exists())
        self.assertEqual(second.read_bytes(), second_bytes)
        self.cli('check')
        self.cli('clean-queue', 'all', '--apply')
        self.assertFalse(second.exists())
        self.cli('check')



if __name__ == '__main__':
    unittest.main()
