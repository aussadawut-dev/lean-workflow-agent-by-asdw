"""Hold the checkout gate lock while the gate runs; a private owner token allows nested calls."""
import fcntl
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import time


def lock_file(root, create=False):
    runtime = root / '.agent-runtime'
    if create:
        runtime.mkdir(exist_ok=True)
    directory = os.open(runtime, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = os.open('quality-gate.lock', os.O_RDWR | os.O_NOFOLLOW | (os.O_CREAT if create else 0),
                             0o600, dir_fd=directory)
    finally:
        os.close(directory)
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(descriptor)
        raise ValueError('gate lock must be a plain file with one link')
    return descriptor


def process_start(pid):
    """Start-time string of a live process, or None (guards against pid reuse)."""
    try:
        result = subprocess.run(['ps', '-o', 'lstart=', '-p', str(pid)], capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    text = ' '.join(result.stdout.split())
    return text if result.returncode == 0 and text else None


def parent_of(pid):
    try:
        result = subprocess.run(['ps', '-o', 'ppid=', '-p', str(pid)], capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=5)
        return int(result.stdout.strip()) if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def is_ancestor(owner):
    pid = os.getpid()
    for _ in range(64):
        pid = parent_of(pid)
        if pid is None or pid <= 1:
            return False
        if pid == owner:
            return True
    return False


def inherited(root):
    """True only inside a run of the live lock holder.

    Design: the holder keeps the flock descriptor private (never inherited) and exports a token
    "pid|start|nonce" that is also written into the lock file. A flock belongs to the open file
    description, so a descriptor inherited by checks would let a detached dev server or watcher keep
    the checkout locked after the gate ended. With no inherited descriptor the lock dies with the
    holder, and nested calls prove ownership instead: the token must match the file, the file must
    still be flocked by someone else, and the recorded owner must be alive (same start time) and an
    ancestor of this process, so merely exporting the variable grants nothing.
    """
    opened = None
    try:
        token = os.environ.get('LEAN_GATE_LOCK_TOKEN', '')
        pid, start, nonce = token.split('|', 2)
        owner = int(pid)
        if not nonce:
            return False
        opened = lock_file(root)
        if os.read(opened, 4096).decode('utf-8', 'replace') != token:
            return False
        try:
            fcntl.flock(opened, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return False  # nobody holds the lock: stale token
        except BlockingIOError:
            pass
        return process_start(owner) == start and is_ancestor(owner)
    except (OSError, ValueError):
        return False
    finally:
        if opened is not None:
            os.close(opened)


def process_table():
    """{pid: ppid} of every process, or {} when ps is unavailable."""
    try:
        result = subprocess.run(['ps', '-axo', 'pid=,ppid='], capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return {}
    table = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            table[int(parts[0])] = int(parts[1])
    return table


def tree_of(root_pid, known):
    """root_pid plus every descendant now visible plus the remembered ones that are still alive."""
    table = process_table()
    found = {root_pid}
    grew = True
    while grew:
        grew = False
        for pid, ppid in table.items():
            if ppid in found and pid not in found:
                found.add(pid)
                grew = True
    return found | {pid for pid in known if pid in table}


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def terminate_tree(gate_pid, start, grace=2.0, ceiling=10.0):
    """SIGTERM the gate and its descendants, SIGKILL leftovers after the grace, return once the gate is gone."""
    def gone():
        return not pid_alive(gate_pid) or (start is not None and process_start(gate_pid) != start)
    known = set()
    deadline = time.monotonic() + grace
    first = True
    while True:
        known = tree_of(gate_pid, known) - {os.getpid()}
        if gone() and not (known - {gate_pid}):
            return
        if first or time.monotonic() >= deadline:
            number = signal.SIGTERM if first else signal.SIGKILL
            for pid in sorted(known, reverse=True):
                try:
                    os.kill(pid, number)
                except OSError:
                    pass
            first = False
            if number == signal.SIGKILL:
                break
        time.sleep(0.05)
    limit = time.monotonic() + ceiling
    while time.monotonic() < limit and not gone():
        for pid in tree_of(gate_pid, known) - {os.getpid()}:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        time.sleep(0.05)


def group_orphans(pgid, exclude):
    """Orphans (parent 1) of process group pgid, plus all their descendants, minus exclude. {} when ps fails."""
    try:
        result = subprocess.run(['ps', '-axo', 'pid=,ppid=,pgid='], capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return set()
    rows = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and all(part.isdigit() for part in parts):
            rows.append(tuple(int(part) for part in parts))
    found = {pid for pid, ppid, group in rows if group == pgid and ppid == 1 and pid not in exclude}
    grew = True
    while grew:
        grew = False
        for pid, ppid, _group in rows:
            if ppid in found and pid not in found and pid not in exclude:
                found.add(pid)
                grew = True
    return found


def terminate_group_orphans(pgid, exclude, grace=2.0, ceiling=10.0):
    """Last resort when the holder died before the gate's pid was known: SIGTERM, then SIGKILL, what it orphaned."""
    start = time.monotonic()
    termed = False
    while time.monotonic() - start < ceiling:
        victims = group_orphans(pgid, exclude)
        if not victims:
            return
        number = signal.SIGKILL if time.monotonic() - start >= grace else signal.SIGTERM
        if number == signal.SIGTERM and termed:
            time.sleep(0.05)
            continue
        termed = termed or number == signal.SIGTERM
        for pid in victims:
            try:
                os.kill(pid, number)
            except OSError:
                pass
        time.sleep(0.05)


def guard(arguments):
    """Guardian: inherits the flock descriptor so the lock outlives a SIGKILLed holder until the gate is dead.

    The gate child announces its own pid ("P<pid>;") on the control pipe from inside the forked child, before
    exec, then closes the pipe; the holder sends "D" on a clean finish. The gate and its descendants never hold
    the pipe, so end-of-file means the holder is gone. A pid is therefore always known by the time of
    end-of-file unless the child died first. End-of-file without "D" means the holder died abnormally: the gate
    is terminated first and only then does the guardian exit, releasing the lock. With no pid ever received,
    the guardian falls back to the orphans (parent 1) of the holder's process group (argument 4, optional) and
    their descendants. The guardian watches the gate's own pid only, so a detached background process started
    by the gate never extends the lock. It ignores terminal and group signals; a SIGKILL of the whole group
    kills it together with the gate.
    """
    control, ready = int(arguments[1]), int(arguments[2])
    holder = os.getppid()
    pgid = int(arguments[4]) if len(arguments) > 4 and arguments[4].isdigit() else None
    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT, signal.SIGPIPE):
        signal.signal(number, signal.SIG_IGN)
    os.write(ready, b'R')
    os.close(ready)
    buffer = b''
    gate_pid = start = None
    while True:
        try:
            data = os.read(control, 4096) if select.select([control], [], [], 0.2)[0] else None
        except InterruptedError:
            continue
        except OSError:
            data = b''
        if data == b'':
            if gate_pid is not None:
                terminate_tree(gate_pid, start)
            elif pgid is not None:
                time.sleep(1.0)  # a late announcement cannot arrive on a closed pipe; give a forked child time to show up
                terminate_group_orphans(pgid, {os.getpid(), holder})
            return 0
        if data:
            buffer += data
            if b'D' in buffer:
                return 0
            if gate_pid is None and b';' in buffer:
                digits = buffer[1:buffer.index(b';')]
                if buffer.startswith(b'P') and digits.isdigit():
                    gate_pid = int(digits)
                    start = process_start(gate_pid)


def start_guardian(descriptor):
    """Spawn the guardian holding the lock descriptor; return (process, control write end)."""
    control_read, control_write = os.pipe()
    ready_read, ready_write = os.pipe()
    try:
        process = subprocess.Popen([sys.executable, '-B', os.path.abspath(__file__), '--guard', str(control_read),
                                    str(ready_write), str(descriptor), str(os.getpgrp())],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   close_fds=True, pass_fds=(descriptor, control_read, ready_write))
    except BaseException:
        os.close(control_write)
        raise
    finally:
        os.close(control_read)
        os.close(ready_write)
    try:
        confirmed = select.select([ready_read], [], [], 15)[0] and os.read(ready_read, 1) == b'R'
    finally:
        os.close(ready_read)
    if not confirmed:
        os.close(control_write)
        process.kill()
        process.wait()
        raise OSError('the lock guardian did not start')
    return process, control_write


def announce(control, pause=0.0):
    """Runs in the forked gate child before exec: tell the guardian this pid, then drop the pipe for good."""
    if pause > 0:
        time.sleep(pause)  # test hook only
    try:
        os.write(control, b'P%d;' % os.getpid())
    except OSError:
        pass  # guardian already gone: the gate must still run, exactly as before the guardian existed
    finally:
        os.close(control)


def run(descriptor, command):
    """Run the gate as a child while this process (and its guardian) hold the lock; mirror its exit status."""
    token = '|'.join((str(os.getpid()), process_start(os.getpid()) or '', os.urandom(16).hex()))
    os.ftruncate(descriptor, 0)
    os.pwrite(descriptor, token.encode(), 0)
    environment = {k: v for k, v in os.environ.items() if k != 'LEAN_GATE_LOCK_FD'}
    environment['LEAN_GATE_LOCK_TOKEN'] = token
    started = []
    early = []
    pause_before_pid = float(os.environ.get('LEAN_GATE_LOCK_TEST_PAUSE_BEFORE_PID') or 0)

    def forward(number, _frame):
        if not started:
            early.append(number)  # the child does not exist yet: deliver it as soon as it does
            return
        try:
            started[0].send_signal(number)
        except OSError:
            pass
    # Handlers go in BEFORE the child is created: a signal in that window would otherwise kill this holder and
    # leave the gate running without the lock.
    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
        signal.signal(number, forward)
    guardian, control = start_guardian(descriptor)
    try:
        child = subprocess.Popen(['/bin/bash', *command], env=environment, close_fds=True,
                                 preexec_fn=lambda: announce(control, pause_before_pid))
        started.append(child)
        pause = float(os.environ.get('LEAN_GATE_LOCK_TEST_PAUSE_AFTER_POPEN') or 0)
        if pause > 0:
            time.sleep(pause)  # test hook: lets a test SIGKILL the holder inside this window
        for number in early:
            forward(number, None)
        while True:
            try:
                status = child.wait()
                break
            except InterruptedError:
                continue
    finally:
        try:
            os.write(control, b'D')
        except OSError:
            pass
        os.close(control)
        try:
            guardian.wait(timeout=20)  # the lock is free only once the guardian has let go
        except subprocess.TimeoutExpired:
            guardian.kill()
            guardian.wait()
    return 128 - status if status < 0 else status


USAGE = 'usage: gate_lock.py --check ROOT | gate_lock.py --run ROOT [bash args...]  (internal quality-gate wrapper)'


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h'):
        print(USAGE)
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == '--guard' and len(sys.argv) >= 5:
        try:
            return guard(sys.argv[1:])
        except (OSError, ValueError):
            return 1
    if len(sys.argv) < 3:
        print(USAGE, file=sys.stderr)
        return 2
    check = sys.argv[1] == '--check'
    root = Path(sys.argv[2]).resolve()
    if check:
        return 0 if inherited(root) else 1
    try:
        descriptor = lock_file(root, create=True)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.set_inheritable(descriptor, False)
        return run(descriptor, sys.argv[3:])
    except BlockingIOError:
        print('Quality Gate busy: another gate is running in this checkout; validation NOT_RUN. Retry after it finishes.',
              file=sys.stderr)
    except (OSError, ValueError) as error:
        print(f'Quality Gate lock unavailable: {error}; validation NOT_RUN.', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
