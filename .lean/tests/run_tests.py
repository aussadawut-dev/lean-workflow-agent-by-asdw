#!/usr/bin/env python3
"""Run each test_*.py file in its own process, several at a time.

Same coverage as `python3 -m unittest discover -s .lean/tests -p 'test_*.py'`,
with wall time bounded by the slowest file instead of the sum of all files.
"""
import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_file(start, name):
    began = time.monotonic()
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(start), "-p", name],
                            cwd=start.parents[1], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return name, result.returncode, time.monotonic() - began, result.stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--start-dir", type=Path, default=HERE)
    parser.add_argument("patterns", nargs="*", help="test file names to run (default: all test_*.py)")
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
    began = time.monotonic()
    failed = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for name, code, seconds, output in pool.map(lambda name: run_file(start, name), names):
            print(f"{'ok  ' if code == 0 else 'FAIL'} {seconds:6.1f}s {name}", flush=True)
            if code != 0:
                failed.append((name, output))
    for name, output in failed:
        print(f"\n===== {name} =====\n{output}", end="")
    print(f"\n{len(names)} files in {time.monotonic() - began:.1f}s: "
          + (f"FAILED ({len(failed)})" if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
