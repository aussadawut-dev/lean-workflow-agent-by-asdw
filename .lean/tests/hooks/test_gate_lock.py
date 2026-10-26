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
