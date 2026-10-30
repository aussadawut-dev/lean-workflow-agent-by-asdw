"""Selected targets keep their ledger locally but share workspace shipping evidence."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from target_support import TargetFixture
from lean import evidence

CONTRACT = 'Contract: risk=MEDIUM quality=HIGH acceptance=target batch passes'


class IntakeTargetTests(TargetFixture):
    def test_target_batch_uses_shared_review_gate_and_application_content(self):
        context = self.install()
        self.gate_file(context, 'true')
        self.workflow('intake', 'add', '--id', 'R1', '--kind', 'feature', '--text', 'feature',
                      '--task', 'TASK-1', '--acceptance', 'target batch passes')
        self.workflow('batch', 'start', '--id', 'B1', '--controller', 'codex', '--requirements', 'R1')
        self.workflow('batch', 'freeze', '--id', 'B1', '--contract', CONTRACT)
        ledger = Path(context['record_root']) / 'docs/tracking/INTAKE.md'
        self.assertTrue(ledger.is_file())
        self.assertFalse((self.root / 'docs/tracking/INTAKE.md').exists())
        self.workflow('batch', 'review', '--id', 'B1', '--evidence', 'focused review PASS')
        ready = json.loads(self.workflow('batch', 'readiness', '--id', 'B1').stdout)
        self.assertEqual(ready['review'], 'PASS')
        result = self.workflow('gate', 'run', '--cache-tree', '--contract', CONTRACT)
        self.assertIn('PASS', result.stdout + result.stderr)
        ready = json.loads(self.workflow('batch', 'readiness', '--id', 'B1').stdout)
        self.assertEqual(ready['gate'], 'PASS')
        self.assertTrue(ready['can_close'])
        self.workflow('batch', 'finish', '--id', 'B1')
        ready = json.loads(self.workflow('batch', 'readiness', '--id', 'B1').stdout)
        self.assertEqual(ready['review'], 'PASS')
        self.assertEqual(ready['gate'], 'STALE')  # Final record synchronization still needs the gate.
        app_file = Path(context['project_root']) / 'app.txt'
        app_file.write_text('new application shipping bytes\n')
        ready = json.loads(self.workflow('batch', 'readiness', '--id', 'B1').stdout)
        self.assertNotEqual(ready['review'], 'PASS')
        self.assertEqual(ready['gate'], 'STALE')
        self.assertFalse(ready['can_close'])

    def test_target_high_batch_accepts_workspace_receipt(self):
        context = self.install()
        self.gate_file(context, 'true')
        contract = CONTRACT.replace('risk=MEDIUM', 'risk=HIGH')
        self.workflow('intake', 'add', '--id', 'R1', '--kind', 'feature', '--text', 'feature',
                      '--task', 'TASK-1', '--acceptance', 'target batch passes')
        self.workflow('batch', 'start', '--id', 'B1', '--controller', 'codex', '--requirements', 'R1')
        self.workflow('batch', 'freeze', '--id', 'B1', '--contract', contract)
        self.reviewed(contract)
        ready = json.loads(self.workflow('batch', 'readiness', '--id', 'B1').stdout)
        self.assertEqual(ready['review'], 'PASS')
        self.workflow('gate', 'run', '--cache-tree', '--contract', contract)
        self.workflow('batch', 'finish', '--id', 'B1')
        ready = json.loads(self.workflow('batch', 'readiness', '--id', 'B1').stdout)
        self.assertEqual(ready['review'], 'PASS')


if __name__ == '__main__':
    unittest.main()
