#!/usr/bin/env python3
"""Run each test_*.py file in its own process, several at a time.

Same coverage as `python3 -m unittest discover -s .lean/tests -p 'test_*.py'`,
with wall time bounded by the slowest file instead of the sum of all files.
`--shards N` also splits each file's tests across up to N processes, and a
named `*.sh` suite runs with bash in the same pool.
"""
import argparse
import os
import re
import subprocess
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
# unittest's `FAIL: name` / `ERROR: name` headers and a shell suite's `FAIL name` lines.
FAILED_NAME = re.compile(r"(?:FAIL|ERROR): \S|FAIL \S")


def positive(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def test_ids(start, name):
    """The file's test ids in declaration order, or [] when it cannot be split safely."""
    loader = unittest.TestLoader()
    ids = []

    def walk(tests):
        for test in tests:
            if isinstance(test, unittest.TestSuite):
                walk(test)
            else:
                ids.append(test.id())
    walk(loader.discover(str(start), pattern=name, top_level_dir=str(start)))
    # A file that cannot import loads as a placeholder; its whole-file run reports the error.
    if loader.errors or any(test_id.startswith("unittest.loader.") for test_id in ids):
        return []
    return ids


def jobs_for(start, name, shards):
    """(label, command, environment) for each process that runs `name`."""
    if name.endswith(".sh"):
        return [(name, ["bash", str(start / name)], None)]
    whole = [(name, [sys.executable, "-m", "unittest", "discover", "-s", str(start), "-p", name], None)]
    ids = test_ids(start, name) if shards > 1 else []
    if len(ids) < 2:
        return whole
    count = min(shards, len(ids))
    # Named tests import from the start directory, as discover's top-level directory does.
    path = os.pathsep.join(filter(None, (str(start), os.environ.get("PYTHONPATH"))))
    environment = dict(os.environ, PYTHONPATH=path)
    return [(f"{name} [{n + 1}/{count}]", [sys.executable, "-m", "unittest", *ids[n::count]], environment)
            for n in range(count)]


def run_job(start, job):
    label, command, environment = job
    began = time.monotonic()
    result = subprocess.run(command, cwd=start.parents[1], env=environment, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return label, result.returncode, time.monotonic() - began, result.stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--shards", type=positive, default=1,
                        help="split each test file's tests across up to N processes")
    parser.add_argument("--start-dir", type=Path, default=HERE)
    parser.add_argument("patterns", nargs="*",
                        help="test file names to run (default: all test_*.py); a *.sh name runs with bash")
    args = parser.parse_args(argv)
    start = args.start_dir.resolve()
    names = args.patterns or sorted(path.name for path in start.glob("test_*.py"))
    if not names:
        print(f"no test files found in {start}", file=sys.stderr)
        return 1
    # unittest discover passes a name that matches nothing on Python < 3.12.
    missing = [name for name in names if not (start / name).is_file()]
    if missing:
        print(f"test files not found in {start}: {' '.join(missing)}", file=sys.stderr)
        return 1
    jobs = [job for name in names for job in jobs_for(start, name, args.shards)]
    began = time.monotonic()
    failed = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for label, code, seconds, output in pool.map(lambda job: run_job(start, job), jobs):
            print(f"{'ok  ' if code == 0 else 'FAIL'} {seconds:6.1f}s {label}", flush=True)
            if code != 0:
                failed.append((label, output))
    for label, output in failed:
        print(f"\n===== {label} =====\n{output}", end="")
    # Repeat every failing name last, where a gate's short output tail still shows them all.
    failing = dict.fromkeys(f"{label}: {line}" for label, output in failed
                            for line in output.splitlines() if FAILED_NAME.match(line))
    if failing:
        print("\nFailed tests:\n" + "\n".join(failing), end="")
    processes = f" ({len(jobs)} processes)" if len(jobs) != len(names) else ""
    print(f"\n{len(names)} files{processes} in {time.monotonic() - began:.1f}s: "
          + (f"FAILED ({len(failed)})" if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
