"""Hold the checkout gate lock across exec; inherited descriptors allow nested calls."""
import fcntl
import os
from pathlib import Path
import stat
import sys


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


def inherited(root):
    opened = None
    try:
        descriptor = int(os.environ.get('LEAN_GATE_LOCK_FD', ''))
        actual = os.fstat(descriptor)
        opened = lock_file(root)
        expected = os.fstat(opened)
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            return False
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (OSError, ValueError):
        return False
    finally:
        if opened is not None:
            os.close(opened)


def main():
    check = sys.argv[1] == '--check'
    root = Path(sys.argv[2]).resolve()
    if check:
        return 0 if inherited(root) else 1
    try:
        descriptor = lock_file(root, create=True)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.set_inheritable(descriptor, True)
        environment = dict(os.environ, LEAN_GATE_LOCK_FD=str(descriptor))
        os.execve('/bin/bash', ['bash', *sys.argv[3:]], environment)
    except BlockingIOError:
        print('Quality Gate busy: another gate is running in this checkout; validation NOT_RUN. Retry after it finishes.',
              file=sys.stderr)
    except (OSError, ValueError) as error:
        print(f'Quality Gate lock unavailable: {error}; validation NOT_RUN.', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
