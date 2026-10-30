"""Gate entry points serialize checks within a checkout and fail closed when busy."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT, install, stop_refusal  # noqa: E402

LEAN = str(ROOT / '.lean/bin/lean')


def clean_env(**extra):
    env = {key: value for key, value in os.environ.items()
           if key not in ('LEAN_GATE_FORCE', 'LEAN_GATE_LOCK_FD')}
    env.update(extra)
    return env


class GateLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lean gate lock ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.lean').mkdir()
        (self.root / '.lean/PROJECT.md').write_text('<!-- gate:start -->\n```sh\nprintf ran >> runs\n```\n<!-- gate:end -->\n')
        self.runtime = self.root / '.agent-runtime'

    def test_direct_failure_is_reported_without_cache(self):
        (self.root / '.lean/PROJECT.md').write_text('<!-- gate:start -->\n```sh\nfalse\n```\n<!-- gate:end -->\n')
        failed = self.gate()
        self.assertEqual(failed.returncode, 2, failed.stderr)
        status = subprocess.run([sys.executable, LEAN, '--root', str(self.root), 'gate', 'status'],
                                capture_output=True, text=True)
        self.assertEqual(status.stdout.strip(), 'FAIL')

    def test_direct_pass_is_recorded_without_enabling_cache(self):
        passed = self.gate()
        self.assertEqual(passed.returncode, 0, passed.stderr)
        status = subprocess.run([sys.executable, LEAN, '--root', str(self.root), 'gate', 'status'],
                                capture_output=True, text=True)
        self.assertEqual(status.stdout.strip(), 'PASS')
        self.assertFalse((self.runtime / 'gate-cache').exists())

    def test_recorded_pass_becomes_stale_after_an_input_edit(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitignore').write_text('.agent-runtime/\nruns\n')
        self.assertEqual(self.gate().returncode, 0)
        from lean import gate
        self.assertEqual(gate.status(self.root), 'PASS')
        (self.root / 'app.txt').write_text('changed')
        self.assertEqual(gate.status(self.root), 'STALE')
        self.assertEqual(gate.status(self.root, verify=False), 'LAST_PASS')

    def test_gate_cannot_record_a_pass_for_inputs_changed_by_its_checks(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitignore').write_text('.agent-runtime/\n')
        (self.root / '.lean/PROJECT.md').write_text(
            '<!-- gate:start -->\n```sh\nprintf changed > app.txt\n```\n<!-- gate:end -->\n')
        result = self.gate()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('shipping inputs changed during validation', result.stderr)
        from lean import gate
        self.assertEqual(gate.status(self.root), 'UNVERIFIED')

    def test_fresh_hook_rerun_cannot_reuse_previous_pass_coverage(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitignore').write_text('.agent-runtime/\n')
        (self.root / 'app.txt').write_text('original')
        (self.root / '.lean/PROJECT.md').write_text(
            '<!-- gate:start -->\n```sh\nif [ -f .agent-runtime/mutate ]; then printf changed > app.txt; fi\n```\n<!-- gate:end -->\n')
        first = self.gate(hook=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        (self.runtime / 'mutate').touch()
        second = self.gate(hook=True)
        self.assertEqual((self.root / 'app.txt').read_text(), 'changed')
        self.assertEqual(second.returncode, 2, second.stderr)
        self.assertIn('shipping inputs changed during validation', second.stderr)
        from lean import gate
        self.assertEqual(gate.status(self.root), 'UNVERIFIED')

    def test_closure_retains_explicit_review_requirement(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitignore').write_text('.agent-runtime/\nruns\n')
        (self.root / '.lean/config.json').write_text(json.dumps(
            {'mode': 'tracker', 'configured': True, 'execution': 'direct'}))
        tracking = self.root / 'docs/tracking'
        tracking.mkdir(parents=True)
        tracker = tracking / 'TCK001.md'
        tracker.write_text('# Workset\nStatus: VALIDATING\n\n## Evidence\n')

        def cli(*args):
            return subprocess.run([sys.executable, LEAN, '--root', str(self.root), *args],
                                  capture_output=True, text=True, env=clean_env())

        for risk in ('LOW', 'MEDIUM'):
            contract = f'Contract: risk={risk} quality=STANDARD acceptance=explicit review required'
            for invalid in ('REWORK', 'missing'):
                with self.subTest(risk=risk, receipt=invalid):
                    state = cli('evidence', 'state').stdout.strip()
                    reviewed = cli('evidence', 'record-review', '--contract', contract,
                                   '--reviewer', 'fixture', '--state', state, '--verdict', 'PASS',
                                   '--evidence', 'fixture review')
                    self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
                    passed = cli('gate', 'run', '--contract', contract, '--require-review')
                    self.assertEqual(passed.returncode, 0, passed.stderr)
                    if invalid == 'REWORK':
                        reviewed = cli('evidence', 'record-review', '--contract', contract,
                                       '--reviewer', 'fixture', '--state', state, '--verdict', 'REWORK',
                                       '--evidence', 'new finding')
                        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
                    else:
                        (self.runtime / 'review.json').unlink()
                    before = tracker.read_bytes()
                    closed = cli('tracker', 'status', '--id', 'TCK001', '--status', 'DONE',
                                 '--contract', contract, '--evidence', 'invalid closure')
                    self.assertNotEqual(closed.returncode, 0, closed.stdout + closed.stderr)
                    self.assertEqual(tracker.read_bytes(), before)

    def test_closure_retains_high_risk_review_floor_after_complete_commit(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitignore').write_text('.agent-runtime/\n')
        (self.root / '.lean/config.json').write_text(json.dumps(
            {'mode': 'tracker', 'configured': True, 'execution': 'direct'}))
        (self.root / '.lean/PROJECT.md').write_text(
            '<!-- gate:start -->\n```sh\ntrue\n```\n<!-- gate:end -->\n\n## High-risk areas\n- `app.txt`\n')
        (self.root / 'app.txt').write_text('shipping code')
        tracking = self.root / 'docs/tracking'
        tracking.mkdir(parents=True)
        tracker = tracking / 'TCK001.md'
        tracker.write_text('# Workset\nStatus: VALIDATING\n\n## Evidence\n')

        def cli(*args):
            return subprocess.run([sys.executable, LEAN, '--root', str(self.root), *args],
                                  capture_output=True, text=True, env=clean_env())

        low = 'Contract: risk=LOW quality=STANDARD acceptance=fixture closure'
        high = 'Contract: risk=HIGH quality=HIGH acceptance=review shipping code'
        reviewed = cli('evidence', 'record-review', '--contract', high, '--reviewer', 'fixture',
                       '--state', cli('evidence', 'state').stdout.strip(), '--verdict', 'PASS',
                       '--evidence', 'high review')
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        passed = cli('gate', 'run', '--contract', low)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=test', '-c',
                        'user.email=test@example.invalid', 'commit', '-qm', 'complete fixture'], check=True)
        reviewed = cli('evidence', 'record-review', '--contract', high, '--reviewer', 'fixture',
                       '--state', cli('evidence', 'state').stdout.strip(), '--verdict', 'REWORK',
                       '--evidence', 'new finding')
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        closed = cli('tracker', 'status', '--id', 'TCK001', '--status', 'DONE', '--contract', low,
                     '--evidence', 'invalid closure')
        self.assertNotEqual(closed.returncode, 0, closed.stdout + closed.stderr)
        self.assertNotIn('Status: DONE', tracker.read_text())

    def gate(self, hook=False, **kwargs):
        command = ['hook', 'claude', 'stop'] if hook else ['gate', 'run']
        return stop_refusal(subprocess.run([sys.executable, LEAN, '--root', str(self.root), *command], input='{}',
                                           env=clean_env(CLAUDE_PROJECT_DIR=str(self.root)),
                                           text=True, capture_output=True, timeout=10, **kwargs))

    def test_busy_lock_blocks_direct_and_claude_without_running_checks(self):
        self.runtime.mkdir()
        with (self.runtime / 'quality-gate.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for hook in (False, True):
                result = self.gate(hook)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('NOT_RUN', result.stderr)
                self.assertFalse((self.root / 'runs').exists())
        self.assertEqual(self.gate().returncode, 0)

    def test_busy_claude_stop_is_released_after_the_refusal_cap(self):
        # A long gate in another session must not block this one's Stops forever (4.17.1 fix).
        from lean import gate
        self.runtime.mkdir()

        def stop(active):
            return subprocess.run([sys.executable, LEAN, '--root', str(self.root), 'hook', 'claude', 'stop'],
                                  input=json.dumps({'stop_hook_active': active}), text=True, capture_output=True,
                                  timeout=10, env=clean_env(CLAUDE_PROJECT_DIR=str(self.root)))

        with (self.runtime / 'quality-gate.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for attempt in range(gate.MAX_REFUSALS):
                blocked = stop(attempt > 0)
                self.assertEqual(json.loads(blocked.stdout)['decision'], 'block', blocked.stdout)
                self.assertIn('busy', blocked.stdout)
            released = stop(True)
            self.assertEqual(released.returncode, 0, released.stderr)
            message = json.loads(released.stdout)
            self.assertNotIn('decision', message)
            self.assertIn('UNVERIFIED', message['systemMessage'])
            self.assertIn('busy', message['systemMessage'])
            # A fresh Stop starts counting again.
            self.assertEqual(json.loads(stop(False).stdout)['decision'], 'block')
        self.assertFalse((self.root / 'runs').exists())
        self.assertFalse((self.runtime / 'gate-cache').exists(), 'a busy release never records a pass')

    def test_busy_counts_are_kept_per_session(self):
        # Another session's fresh Stop must not restart this session's count.
        from lean import gate
        self.runtime.mkdir()

        def stop(session, active):
            result = subprocess.run([sys.executable, LEAN, '--root', str(self.root), 'hook', 'claude', 'stop'],
                                    input=json.dumps({'session_id': session, 'stop_hook_active': active}), text=True,
                                    capture_output=True, timeout=10, env=clean_env(CLAUDE_PROJECT_DIR=str(self.root)))
            return json.loads(result.stdout)

        with (self.runtime / 'quality-gate.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for attempt in range(gate.MAX_REFUSALS):
                self.assertIn('decision', stop('a', attempt > 0))
                self.assertIn('decision', stop('b', False))  # B starts fresh each time.
            released = stop('a', True)
            self.assertNotIn('decision', released)
            self.assertIn('UNVERIFIED', released['systemMessage'])
            # A fresh Stop sweeps counters older than a day; recent ones stay.
            stale, recent = self.runtime / 'gate-busy.0000000000000000', self.runtime / 'gate-busy.1111111111111111'
            for path in (stale, recent):
                path.write_text('1')
            os.utime(stale, (time.time() - 2 * 86400,) * 2)
            stop('c', False)
            self.assertFalse(stale.exists())
            self.assertTrue(recent.exists())

    def test_busy_claude_stop_with_an_unwritable_counter_releases_continued_stops(self):
        self.runtime.mkdir()
        for blocker in ('directory', 'read-only'):
            with self.subTest(counter=blocker):
                counter = self.runtime / 'gate-busy'
                if counter.is_dir():
                    counter.rmdir()
                elif counter.exists():
                    counter.chmod(0o600)
                    counter.unlink()
                if blocker == 'directory':
                    counter.mkdir()
                else:
                    counter.write_text('1')
                    counter.chmod(0o400)
                with (self.runtime / 'quality-gate.lock').open('w') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    for active in (False, True):
                        result = subprocess.run([sys.executable, LEAN, '--root', str(self.root), 'hook', 'claude', 'stop'],
                                                input=json.dumps({'stop_hook_active': active}), text=True,
                                                capture_output=True, timeout=10,
                                                env=clean_env(CLAUDE_PROJECT_DIR=str(self.root)))
                        message = json.loads(result.stdout)
                        self.assertEqual('decision' in message, not active, result.stdout)
                if blocker == 'read-only':
                    counter.chmod(0o600)

    def test_direct_runner_without_arguments_uses_the_working_directory(self):
        # A copy of the workflow gates its own checkout by default.
        install(self.root)
        result = subprocess.run([sys.executable, str(self.root / '.lean/bin/lean'), 'gate', 'run'], cwd=self.root,
                                text=True, capture_output=True, timeout=10, env=clean_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'runs').read_text(), 'ran')

    def test_running_gate_holds_lock_and_releases_after_failure(self):
        self.root.joinpath('.lean/PROJECT.md').write_text(
            '<!-- gate:start -->\n```sh\nprintf ready > ready; while [ ! -f release ]; do sleep 0.05; done; false\n```\n<!-- gate:end -->\n')
        process = subprocess.Popen([sys.executable, LEAN, '--root', str(self.root), 'gate', 'run'], env=clean_env(),
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        deadline = time.monotonic() + 10
        while not (self.root / 'ready').exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue((self.root / 'ready').exists())
        try:
            result = self.gate()
        finally:
            (self.root / 'release').touch()
            stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('NOT_RUN', result.stderr)
        self.assertEqual(process.returncode, 2, stdout + stderr)
        retry = self.gate()
        self.assertIn('Quality Gate failed', retry.stderr)
        self.assertNotIn('busy', retry.stderr)

    def test_symlinked_runtime_or_lock_never_touches_external_target(self):
        outside = self.root / 'outside'
        outside.mkdir()
        self.runtime.symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.gate().returncode, 2)
        self.assertEqual(list(outside.iterdir()), [])
        self.runtime.unlink()
        self.runtime.mkdir()
        target = outside / 'target'
        target.write_text('preserve')
        (self.runtime / 'quality-gate.lock').symlink_to(target)
        self.assertEqual(self.gate().returncode, 2)
        self.assertEqual(target.read_text(), 'preserve')
        self.assertFalse((self.root / 'runs').exists())

    def test_forged_environment_cannot_bypass_busy_lock(self):
        self.runtime.mkdir()
        with (self.runtime / 'quality-gate.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for descriptor in ('0', '3', '4', '999'):
                result = subprocess.run([sys.executable, LEAN, '--root', str(self.root), 'gate', 'run'],
                                        env=clean_env(LEAN_GATE_LOCK_FD=descriptor),
                                        text=True, input='{}', capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('NOT_RUN', result.stderr)
                self.assertFalse((self.root / 'runs').exists())

    def test_lock_code_changes_require_control_acceptance(self):
        import shutil
        fixture = self.root / 'fixture'
        install(fixture)
        shutil.copy2(self.root / '.lean/PROJECT.md', fixture / '.lean/PROJECT.md')
        command = [sys.executable, str(fixture / '.lean/bin/lean'), '--root', str(fixture), 'gate', 'run']
        self.assertEqual(subprocess.run(command, capture_output=True, env=clean_env()).returncode, 0)
        helper = fixture / '.lean/lean/gate.py'
        helper.write_text(helper.read_text() + '\n')
        result = subprocess.run(command, text=True, capture_output=True, env=clean_env())
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('controls changed', result.stderr)


if __name__ == '__main__':
    unittest.main()
