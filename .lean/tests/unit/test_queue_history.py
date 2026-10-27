"""Completion timestamps are recorded in UTC and validated (queue cleanup left with lean-prune in 5.0)."""
import json
import contextlib
import hashlib
import sys
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from pathlib import Path
import subprocess
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT  # noqa: E402
from lean import records as workflow  # noqa: E402

SCRIPT = ROOT / ".lean/bin/lean"
TEMPLATES = ROOT / ".lean/templates"
MODE_ACTIONS = ("configure", "downgrade", "show", "check", "context")


def cli(*args):
    """The v5 spelling of a 4.x workflow.py call: mode actions moved under `lean mode`."""
    return ("mode", *args) if args and args[0] in MODE_ACTIONS else args


class QueueHistoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / '.lean/templates').mkdir(parents=True)
        for name in ('tracker.md', 'queue-item.json'):
            (self.root / '.lean/templates' / name).write_bytes((TEMPLATES / name).read_bytes())
        (self.root / '.gitignore').write_text('.agent-runtime/\n')
        self.cli('configure', 'full')
        (self.root / 'docs/tracking/TCK001.md').write_text('# Task\nStatus: PLANNED\n\n## Evidence\n')
        self.item_path = self.root / '.agents/queue/items/Q0001.json'
        self.item_path.write_text(json.dumps({'id': 'Q0001', 'title': 'Task', 'tracker': 'TCK001',
             'status': 'READY', 'scopes': ['src'], 'dependencies': [], 'evidence': None}))

    def cli(self, *args, ok=True):
        result = subprocess.run(['python3', str(SCRIPT), '--root', str(self.root), *cli(*args)],
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


if __name__ == '__main__':
    unittest.main()
