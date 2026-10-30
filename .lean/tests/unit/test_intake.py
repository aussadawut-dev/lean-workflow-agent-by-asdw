"""Requirement intake and batch boundaries through the public CLI."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import install, lean, git, commit
from lean import evidence, intake, guard


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        install(self.root)
        git(self.root, 'init', '-q')
        commit(self.root)

    def run_cli(self, *args, ok=True):
        result = lean(self.root, *args)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def add(self, rid='R1', **kw):
        args = ['intake', 'add', '--id', rid, '--kind', kw.pop('kind', 'feature'),
                '--text', rid, '--task', 'TASK-1', '--acceptance', 'observable result']
        for key, value in kw.items():
            args += ['--' + key.replace('_', '-'), value]
        return self.run_cli(*args)

    def start(self, bid='B1', rid='R1', controller='codex', ok=True):
        return self.run_cli('batch', 'start', '--id', bid, '--controller', controller,
                            '--requirements', rid, ok=ok)

    def test_new_feature_queues_without_full_mode_and_freeze_protects_scope(self):
        self.add()
        data = json.loads(self.run_cli('intake', 'list').stdout)
        self.assertEqual(data['requirements']['R1']['status'], 'queued')
        self.start()
        self.run_cli('batch', 'freeze', '--id', 'B1', '--contract',
                     'Contract: risk=HIGH quality=HIGH acceptance=observable result')
        self.add('R2')
        self.start('B2', 'R2', ok=False)
        self.run_cli('intake', 'cancel', '--id', 'R1', '--reason', 'scope changed', ok=False)
        readiness = json.loads(self.run_cli('batch', 'readiness', '--id', 'B1').stdout)
        self.assertEqual(readiness['implementation'], 'READY')
        self.assertEqual(readiness['gate'], 'NOT_RUN')
        self.assertFalse(readiness['can_close'])
        self.run_cli('batch', 'reopen', '--id', 'B1', '--reason', 'user redirect')
        self.assertIn('invalid', self.run_cli('batch', 'freeze', '--id', 'B1', '--contract',
                      'Contract: risk=HIGH quality=HIGH acceptance=observable result', ok=False).stderr)

    def test_one_primary_per_controller_checkpoint_and_dependencies(self):
        self.add()
        self.add('R2', depends='R1')
        self.start('B2', 'R2', ok=False)
        self.start()
        self.start('B2', 'R2', ok=False)
        self.run_cli('batch', 'checkpoint', '--id', 'B1', '--reason', 'explicit user interrupt')
        self.start('B2', 'R2', ok=False)  # Checkpoint does not satisfy dependency.
        self.add('R3')
        self.start('B3', 'R3')
        self.start('B4', 'R1', controller='other', ok=False)  # no stolen paused work

    def test_traceability_and_supersession_are_lossless(self):
        self.run_cli('intake', 'add', '--id', 'bad', '--kind', 'feature', '--text', 'x',
                     '--task', '', '--acceptance', '', ok=False)
        self.add()
        self.add('R2', kind='direction', supersedes='R1')
        data = json.loads(self.run_cli('intake', 'list').stdout)
        self.assertEqual(data['requirements']['R1']['status'], 'superseded')
        self.assertEqual(data['requirements']['R2']['supersedes'], ['R1'])
        self.run_cli('intake', 'check')
        self.run_cli('intake', 'cancel', '--id', 'R2', '--reason', 'user cancelled')
        data = json.loads(self.run_cli('intake', 'list').stdout)
        self.assertEqual(data['requirements']['R2']['status'], 'cancelled')

    def test_corrupt_ledger_cycle_is_rejected_without_writes(self):
        self.add()
        self.add('R2')
        path = self.root / 'docs/tracking/INTAKE.md'
        data = json.loads(path.read_text().split('```json\n')[1].split('```')[0])
        data['requirements']['R1']['dependencies'] = ['R2']
        data['requirements']['R2']['dependencies'] = ['R1']
        path.write_text('# Requirement intake\n\n```json\n' + json.dumps(data) + '\n```\n')
        before = path.read_bytes()
        self.run_cli('intake', 'check', ok=False)
        self.run_cli('intake', 'cancel', '--id', 'R1', '--reason', 'x', ok=False)
        self.assertEqual(before, path.read_bytes())

    def freeze(self, risk='MEDIUM', acceptance='observable result'):
        contract = f'Contract: risk={risk} quality=HIGH acceptance={acceptance}'
        self.run_cli('batch', 'freeze', '--id', 'B1', '--contract', contract)
        return contract

    def mark_gate_pass(self):
        # Model the real gate's exact-state cache in this disposable fixture.
        runtime = self.root / '.agent-runtime'
        runtime.mkdir(exist_ok=True)
        (runtime / 'gate-cache').write_text(evidence.state(self.root))

    def readiness(self):
        return json.loads(self.run_cli('batch', 'readiness', '--id', 'B1').stdout)

    def test_close_requires_current_review_and_gate_then_satisfies_dependencies(self):
        self.add()
        self.add('R2', depends='R1')
        self.start()
        self.freeze()
        self.run_cli('batch', 'finish', '--id', 'B1', ok=False)
        self.run_cli('batch', 'review', '--id', 'B1', '--evidence', 'focused semantic review PASS')
        self.assertEqual(self.readiness()['review'], 'PASS')
        self.assertFalse(self.readiness()['can_close'])
        self.mark_gate_pass()
        self.assertTrue(self.readiness()['can_close'])
        self.run_cli('batch', 'finish', '--id', 'B1')
        self.start('B2', 'R2')

    def test_shipping_change_stales_review_and_gate_without_changing_implementation(self):
        self.add()
        self.start()
        self.freeze()
        self.run_cli('batch', 'review', '--id', 'B1', '--evidence', 'review PASS')
        self.mark_gate_pass()
        (self.root / 'new-shipping-file.py').write_text('changed = True\n')
        ready = self.readiness()
        self.assertEqual(ready['implementation'], 'READY')
        self.assertNotEqual(ready['review'], 'PASS')
        self.assertEqual(ready['gate'], 'STALE')
        self.assertFalse(ready['can_close'])

    def test_high_review_cannot_be_self_attested(self):
        self.add()
        self.start()
        contract = self.freeze('HIGH')
        self.run_cli('batch', 'review', '--id', 'B1', '--evidence', 'self PASS', ok=False)
        self.run_cli('evidence', 'record-review', '--contract', contract, '--reviewer', 'fixture-reviewer',
                     '--state', evidence.captured_state(self.root), '--verdict', 'PASS', '--evidence', 'fixture review')
        self.assertEqual(self.readiness()['review'], 'PASS')
        (self.root / 'changed.txt').write_text('new content')
        self.assertNotEqual(self.readiness()['review'], 'PASS')

    def test_redirect_returns_old_scope_to_queue_without_losing_trace(self):
        self.add()
        self.start()
        self.freeze()
        self.add('R2')
        self.run_cli('batch', 'scope', '--id', 'B1', '--requirements', 'R2', '--reason', 'redirect', ok=False)
        self.run_cli('batch', 'reopen', '--id', 'B1', '--reason', 'user redirects')
        self.run_cli('batch', 'scope', '--id', 'B1', '--requirements', 'R2', '--reason', 'user redirects')
        self.add('R3', kind='direction', supersedes='R1')
        self.freeze(acceptance='new observable acceptance')
        data = json.loads(self.run_cli('intake', 'list').stdout)
        self.assertEqual(data['requirements']['R1']['status'], 'superseded')
        self.assertEqual(data['batches']['B1']['requirements'], ['R2'])
        self.assertEqual(data['requirements']['R3']['status'], 'queued')

    def test_mode_check_validates_ledger_and_path_cannot_escape(self):
        self.add()
        data = intake.load(self.root)
        data['requirements']['R1']['task'] = ''
        path = self.root / intake.PATH
        path.write_text(intake.PREFIX + json.dumps(data) + '\n' + intake.SUFFIX)
        self.run_cli('mode', 'check', ok=False)
        path.unlink()
        outside = self.root / 'outside'
        outside.write_text('untouched')
        path.symlink_to(outside)
        self.run_cli('intake', 'check', ok=False)
        self.assertEqual(outside.read_text(), 'untouched')

    def test_primary_wip_and_whitespace_controller_cannot_bypass(self):
        self.add()
        self.add('R2')
        self.start()
        for controller in ('codex', ' codex', 'codex '):
            self.start('B2', 'R2', controller=controller, ok=False)
        self.run_cli('batch', 'checkpoint', '--id', 'B1', '--reason', 'user interrupt')
        self.start('B2', 'R2')
        self.run_cli('batch', 'resume', '--id', 'B1', ok=False)

    def test_read_commands_pass_guard_without_contract_but_mutations_do_not(self):
        for command in ('intake list', 'intake check', 'batch readiness --id B1'):
            self.assertFalse(guard.shell_writes('python3 .lean/bin/lean ' + command), command)
        for command in ('intake add', 'intake cancel', 'batch start', 'batch freeze', 'batch finish', 'batch review'):
            self.assertTrue(guard.shell_writes('python3 .lean/bin/lean ' + command), command)

    def test_lower_review_does_not_cover_different_staged_bytes(self):
        self.add()
        self.start()
        self.freeze()
        path = self.root / 'shipping.txt'
        path.write_text('staged old version')
        git(self.root, 'add', 'shipping.txt')
        path.write_text('reviewed working version')
        self.run_cli('batch', 'review', '--id', 'B1', '--evidence', 'reviewed working bytes')
        self.mark_gate_pass()
        self.assertNotEqual(self.readiness()['review'], 'PASS')
        self.assertFalse(self.readiness()['can_close'])
        git(self.root, 'add', 'shipping.txt')
        self.assertEqual(self.readiness()['review'], 'PASS')

    def test_retire_all_work_preserves_requirements_for_cancel_or_supersede(self):
        self.add()
        self.start()
        self.freeze()
        self.run_cli('batch', 'retire', '--id', 'B1', '--reason', 'user cancelled work', ok=False)
        self.run_cli('batch', 'reopen', '--id', 'B1', '--reason', 'user cancelled work')
        self.run_cli('batch', 'retire', '--id', 'B1', '--reason', 'user cancelled work')
        self.run_cli('intake', 'cancel', '--id', 'R1', '--reason', 'user cancelled')
        self.add('R2')
        self.start('B2', 'R2')
        data = json.loads(self.run_cli('intake', 'list').stdout)
        self.assertEqual(data['requirements']['R1']['status'], 'cancelled')
        self.assertEqual(data['batches']['B1']['status'], 'retired')

    def test_read_commands_do_not_create_runtime_files(self):
        runtime = self.root / '.agent-runtime'
        self.assertFalse(runtime.exists())
        self.run_cli('intake', 'list')
        self.run_cli('intake', 'check')
        self.run_cli('batch', 'readiness', '--id', 'missing', ok=False)
        self.assertFalse(runtime.exists())


if __name__ == '__main__':
    unittest.main()
