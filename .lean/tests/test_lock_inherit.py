"""The gate lock must not outlive the gate run through descendants, yet nested calls still see it."""
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
GATE = str(ROOT / '.lean/scripts/quality-gate.sh')
LOCK = str(ROOT / '.lean/scripts/gate_lock.py')
BUSY = 'Quality Gate busy: another gate is running in this checkout; validation NOT_RUN. Retry after it finishes.'


def children(pid):
    """[(pid, command)] of direct children of pid."""
    out = subprocess.run(['ps', '-axo', 'pid=,ppid=,command='], capture_output=True, text=True,
                         stdin=subprocess.DEVNULL).stdout
    found = []
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[1] == str(pid):
            found.append((int(parts[0]), parts[2]))
    return found


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class LockInheritTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lean lock inherit ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.lean').mkdir()
        self.pids = []
        self.addCleanup(self.reap)

    def reap(self):
        for pid in self.pids + [int(p.read_text()) for p in self.root.glob('*.pid') if p.read_text().strip().isdigit()]:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def project(self, command):
        (self.root / '.lean/PROJECT.md').write_text(f'<!-- gate:start -->\n```sh\n{command}\n```\n<!-- gate:end -->\n')

    def gate(self, timeout=20, **kwargs):
        return subprocess.run(['bash', GATE, '--root', str(self.root)], stdin=subprocess.DEVNULL, text=True,
                              capture_output=True, timeout=timeout, **kwargs)

    def wait_for(self, name):
        deadline = time.monotonic() + 10
        while not (self.root / name).exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue((self.root / name).exists(), name)

    def lock_free(self):
        descriptor = os.open(self.root / '.agent-runtime/quality-gate.lock', os.O_RDWR)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False
        finally:
            os.close(descriptor)

    def wait_until(self, condition, seconds=15):
        deadline = time.monotonic() + seconds
        while not condition() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(condition())

    def holder(self):
        process = subprocess.Popen([sys.executable, LOCK, '--run', str(self.root), GATE, '--root', str(self.root)],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        self.addCleanup(lambda: [process.stdout.close(), process.stderr.close()])
        return process

    def kill_holder_and_watch(self, project):
        self.project(project)
        holder = self.holder()
        self.wait_for('c.pid')
        sleeper = int((self.root / 'c.pid').read_text())
        self.assertTrue(self.lock_free() is False)
        holder.kill()
        holder.wait()
        overlap = []
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            free, running = self.lock_free(), alive(sleeper)
            if free and running:
                overlap.append(time.monotonic())
            if free and not running:
                break
            time.sleep(0.05)
        self.assertEqual(overlap, [], 'the lock was free while the gate was still running')
        self.assertFalse(alive(sleeper))
        self.assertTrue(self.lock_free())

    def test_sigkilled_holder_stops_the_gate_before_the_lock_is_free(self):
        self.kill_holder_and_watch('printf ready > ready; sleep 30 & echo $! > "$PWD/c.pid"; wait')

    def test_sigkilled_holder_with_a_term_ignoring_gate_is_killed_before_release(self):
        self.kill_holder_and_watch('trap "" TERM; sleep 30 & echo $! > "$PWD/c.pid"; while :; do sleep 0.1; done')

    def test_one_guardian_while_running_and_none_left_afterwards(self):
        self.project('printf ready > ready; while [ ! -f release ]; do sleep 0.05; done')
        holder = self.holder()
        self.wait_for('ready')
        guards = [pid for pid, command in children(holder.pid) if '--guard' in command]
        self.assertEqual(len(guards), 1)
        (self.root / 'release').touch()
        holder.communicate(timeout=20)
        self.assertEqual(holder.returncode, 0)
        self.assertFalse(alive(guards[0]))
        self.assertTrue(self.lock_free())

    def test_sigkilled_guardian_keeps_the_lock_with_the_holder_and_the_gate_finishes(self):
        # Residual risk: the holder's own descriptor still holds the flock, so the lock is NOT lost, but the gate is
        # then only as protected as before the guardian existed (a later SIGKILL of the holder leaves it running).
        self.project('printf ready > ready; while [ ! -f release ]; do sleep 0.05; done')
        holder = self.holder()
        self.wait_for('ready')
        (guard,) = [pid for pid, command in children(holder.pid) if '--guard' in command]
        os.kill(guard, signal.SIGKILL)
        time.sleep(0.5)
        self.assertFalse(self.lock_free())
        self.assertIn(BUSY, self.gate().stderr)
        (self.root / 'release').touch()
        holder.communicate(timeout=20)
        self.assertEqual(holder.returncode, 0)
        self.assertTrue(self.lock_free())

    def window_case(self, pause_env, kill_after, project='echo $$ > "$PWD/g.pid"; exec sleep 30'):
        """SIGKILL the holder inside a spawn window; the gate must die before the lock is ever free."""
        self.project(project)
        process = subprocess.Popen([sys.executable, LOCK, '--run', str(self.root), GATE, '--root', str(self.root)],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   env={**os.environ, **pause_env})
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        time.sleep(kill_after)
        process.kill()
        process.wait()
        deadline = time.monotonic() + 15
        gate = None
        overlap = []
        while time.monotonic() < deadline:
            if gate is None and (self.root / 'g.pid').exists():
                text = (self.root / 'g.pid').read_text().strip()
                gate = int(text) if text.isdigit() else None
            free = self.lock_free()
            running = gate is not None and alive(gate)
            if free and running:
                overlap.append(time.monotonic())
            if free and (gate is not None or time.monotonic() > deadline - 10):
                if not running:
                    break
            time.sleep(0.02)
        self.assertEqual(overlap, [], 'the lock was free while the gate was still running')
        if gate is not None:
            self.assertFalse(alive(gate))
        self.assertTrue(self.lock_free())
        return gate

    def test_holder_killed_right_after_the_gate_is_forked_cannot_orphan_the_gate(self):
        # Deterministic: the test hook keeps the holder alive for 3 s after Popen returns (before it could tell the
        # guardian anything in the old protocol); the gate starts, then the holder is SIGKILLed in the window.
        self.window_case({'LEAN_GATE_LOCK_TEST_PAUSE_AFTER_POPEN': '3'}, 1.5)
        self.assertTrue((self.root / 'g.pid').exists(), 'the gate never started')

    def test_holder_killed_before_the_child_announces_its_pid_still_stops_the_gate(self):
        # The child pauses before announcing (and holding the pipe); the holder dies first; the gate starts later.
        # The gate would finish by touching `survived`; it must be stopped before that, whenever it got that far.
        self.window_case({'LEAN_GATE_LOCK_TEST_PAUSE_BEFORE_PID': '2'}, 1.0, 'echo $$ > "$PWD/g.pid"; sleep 2; touch survived')
        time.sleep(2.5)
        self.assertFalse((self.root / 'survived').exists(), 'the gate ran on after the holder was killed')

    def test_only_the_holder_holds_the_control_pipe_write_end(self):
        if subprocess.run(['which', 'lsof'], capture_output=True, stdin=subprocess.DEVNULL).returncode != 0:
            self.skipTest('lsof unavailable')
        self.project('lsof -nP -a -p $$ -d 3-255 -F t > "$PWD/gate.fds" 2>/dev/null; printf ready > ready; '
                     'while [ ! -f release ]; do sleep 0.05; done')
        holder = self.holder()
        self.wait_for('ready')
        gate_fds = (self.root / 'gate.fds').read_text().split()
        self.assertNotIn('tPIPE', gate_fds, 'the gate inherited a pipe descriptor')
        mine = subprocess.run(['lsof', '-nP', '-a', '-p', str(holder.pid), '-d', '3-255', '-F', 't'], text=True,
                              capture_output=True, stdin=subprocess.DEVNULL).stdout.split()
        self.assertIn('tPIPE', mine, 'the holder should own the control pipe')
        (self.root / 'release').touch()
        holder.communicate(timeout=20)
        self.assertEqual(holder.returncode, 0)

    def test_guardian_without_a_pid_kills_orphans_of_the_holder_group(self):
        script = (
            'import importlib.util, os, sys, tempfile\n'
            'spec = importlib.util.spec_from_file_location("gate_lock", sys.argv[1])\n'
            'g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)\n'
            'fd = g.lock_file(__import__("pathlib").Path(sys.argv[2]), create=True)\n'
            'import fcntl; fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n'
            'proc, control = g.start_guardian(fd)\n'
            'if os.fork() == 0:\n'
            '    if os.fork() == 0:\n'
            '        open(sys.argv[2] + "/o.pid", "w").write(str(os.getpid()))\n'
            '        os.execvp("sleep", ["sleep", "30"])\n'
            '    os._exit(0)\n'
            'os.wait()\n'
            'import time\n'
            'while not os.path.exists(sys.argv[2] + "/o.pid") or not open(sys.argv[2] + "/o.pid").read(): time.sleep(0.01)\n'
            'time.sleep(0.2)\n'
            'os.close(control)\n'  # EOF with no pid and no D, holder "dies"
            'os._exit(0)\n')
        done = subprocess.run([sys.executable, '-c', script, LOCK, str(self.root)], stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
                              start_new_session=True)
        self.assertEqual(done.returncode, 0)
        orphan = int((self.root / 'o.pid').read_text())
        self.pids.append(orphan)
        deadline = time.monotonic() + 15
        overlap = []
        while time.monotonic() < deadline:
            free, running = self.lock_free(), alive(orphan)
            if free and running:
                overlap.append(1)
            if free and not running:
                break
            time.sleep(0.02)
        self.assertEqual(overlap, [])
        self.assertFalse(alive(orphan))
        self.assertTrue(self.lock_free())

    def test_outputs_and_exit_codes(self):
        (self.root / '.agent-runtime').mkdir()

        def run(script):
            return subprocess.run([sys.executable, LOCK, '--run', str(self.root), '-c', script], text=True,
                                  stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
        failed = run('echo out; echo err >&2; exit 3')
        self.assertEqual((failed.returncode, failed.stdout, failed.stderr), (3, 'out\n', 'err\n'))
        ok = run('true')
        self.assertEqual((ok.returncode, ok.stdout, ok.stderr), (0, '', ''))
        self.assertEqual(run('kill -TERM $$').returncode, 128 - -15)
        self.assertEqual(subprocess.run([sys.executable, LOCK], capture_output=True, text=True).returncode, 2)

    def test_detached_background_process_does_not_keep_the_lock(self):
        self.project('(nohup sleep 25 >/dev/null 2>&1 </dev/null & echo $! > "$PWD/bg.pid")')
        self.assertEqual(self.gate().returncode, 0)
        pid = int((self.root / 'bg.pid').read_text())
        self.assertTrue(alive(pid))
        started = time.monotonic()
        second = self.gate()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotIn('busy', second.stderr)
        self.assertLess(time.monotonic() - started, 10)
        self.assertTrue(alive(pid))

    def test_nested_check_sees_lock_and_second_gate_is_busy_while_running(self):
        self.project(f'python3 {LOCK} --check "$PWD" && printf nested > nested; '
                     'printf ready > ready; while [ ! -f release ]; do sleep 0.05; done')
        process = subprocess.Popen(['bash', GATE, '--root', str(self.root)], stdin=subprocess.DEVNULL, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        self.wait_for('ready')
        try:
            self.assertEqual((self.root / 'nested').read_text(), 'nested')
            busy = self.gate()
            self.assertEqual(busy.returncode, 2)
            self.assertIn(BUSY, busy.stderr)
        finally:
            (self.root / 'release').touch()
            process.communicate(timeout=20)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(subprocess.run([sys.executable, LOCK, '--check', str(self.root)]).returncode, 1)

    def test_holder_crash_releases_the_lock(self):
        self.project('[ -f release ] || { printf ready > ready; sleep 30 & echo $! > "$PWD/c.pid"; wait; }')
        holder = subprocess.Popen([sys.executable, LOCK, '--run', str(self.root), GATE, '--root', str(self.root)],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: holder.kill() if holder.poll() is None else None)
        self.wait_for('c.pid')
        busy = self.gate()
        self.assertIn(BUSY, busy.stderr)
        holder.kill()
        holder.wait()
        (self.root / 'release').touch()
        self.wait_until(lambda: self.lock_free())  # the guardian releases it once the gate is dead
        result = self.gate()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_forged_or_stale_variables_do_not_bypass_the_lock(self):
        holder_project = 'printf ready > ready; while [ ! -f release ]; do sleep 0.05; done'
        self.project(holder_project)
        process = subprocess.Popen(['bash', GATE, '--root', str(self.root)], stdin=subprocess.DEVNULL, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        self.wait_for('ready')
        try:
            token = (self.root / '.agent-runtime/quality-gate.lock').read_text()
            owner = int(token.split('|')[0])
            for env in ({'LEAN_GATE_LOCK_FD': '3'}, {'LEAN_GATE_LOCK_TOKEN': 'garbage'},
                        {'LEAN_GATE_LOCK_TOKEN': f'{owner}|x|y'},
                        # Even the real token is useless to a process that is not a descendant of the holder.
                        {'LEAN_GATE_LOCK_TOKEN': token}):
                check = subprocess.run([sys.executable, LOCK, '--check', str(self.root)], stdin=subprocess.DEVNULL,
                                       env={**os.environ, **env})
                self.assertEqual(check.returncode, 1, env)
                result = self.gate(env={**os.environ, **env})
                self.assertEqual(result.returncode, 2, env)
                self.assertIn(BUSY, result.stderr)
        finally:
            (self.root / 'release').touch()
            process.communicate(timeout=20)
        self.assertEqual(process.returncode, 0)
        stale = subprocess.run([sys.executable, LOCK, '--check', str(self.root)], stdin=subprocess.DEVNULL,
                               env={**os.environ, 'LEAN_GATE_LOCK_TOKEN': token})
        self.assertEqual(stale.returncode, 1)
        self.assertEqual(self.gate(env={**os.environ, 'LEAN_GATE_LOCK_TOKEN': token}).returncode, 0)


RACE_SCRIPT = r"""
import importlib.util, os, signal, sys, tempfile
from unittest import mock
spec = importlib.util.spec_from_file_location('gate_lock', sys.argv[1])
gate_lock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate_lock)
seen = []

class Child:
    def send_signal(self, number):
        seen.append(number)
    def wait(self):
        return 0

real_popen = gate_lock.subprocess.Popen

def fake_popen(*args, **kwargs):
    if not (args and args[0] and args[0][0] == '/bin/bash'):
        return real_popen(*args, **kwargs)  # e.g. the `ps` calls that run() makes first
    os.kill(os.getpid(), signal.SIGTERM)  # a signal that arrives while the gate child is being created
    return Child()

with tempfile.TemporaryFile() as handle, mock.patch.object(gate_lock.subprocess, 'Popen', fake_popen):
    gate_lock.run(handle.fileno(), ['-c', 'true'])
print('forwarded' if seen == [signal.SIGTERM] else 'lost %r' % (seen,))
"""


class SignalWindowTests(unittest.TestCase):
    def test_a_signal_arriving_while_the_child_is_created_is_forwarded_not_fatal(self):
        # Run in a subprocess: before the fix the default SIGTERM action would kill the process holding the lock
        # and leave the gate child running without it.
        done = subprocess.run([sys.executable, '-c', RACE_SCRIPT, LOCK], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, 'forwarded'), done.stderr)


if __name__ == '__main__':
    unittest.main()
