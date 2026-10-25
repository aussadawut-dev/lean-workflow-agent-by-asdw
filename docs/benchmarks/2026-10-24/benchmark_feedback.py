#!/usr/bin/env python3
"""Alternate two runner snapshots on a small, deliberately blocked-first fixture.

Feedback latency and total duration are separate observations, not test thresholds.
Run from the repository root; no Quality Gate or full test suite is invoked.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample(source):
    with tempfile.TemporaryDirectory() as temporary:
        start = Path(temporary) / '.lean/tests'
        start.mkdir(parents=True)
        (start / 'test_a.py').write_text(
            "import time, unittest\nfrom pathlib import Path\n"
            "class T(unittest.TestCase):\n def test_slow(self):\n"
            "  Path(__file__).with_name('entered').touch()\n  time.sleep(1.5)\n")
        (start / 'test_b.py').write_text(
            "import time, unittest\nfrom pathlib import Path\n"
            "class T(unittest.TestCase):\n def test_fast_failure(self):\n"
            "  deadline = time.monotonic() + 15\n"
            "  while not Path(__file__).with_name('entered').exists():\n"
            "   if time.monotonic() > deadline: self.fail('barrier timed out')\n"
            "   time.sleep(0.01)\n  self.fail('planted fast failure')\n")
        (start / 'test_c.py').write_text(
            "import unittest\nclass T(unittest.TestCase):\n def test_pass(self): pass\n")
        command = [sys.executable, str(source), '--start-dir', str(start), '-j', '2']
        before = os.getloadavg()
        began = time.monotonic()
        process = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        events = []
        # Every fixture has bounded waits; communicate's timeout also bounds teardown.
        try:
            for line in process.stdout:
                events.append({'seconds': time.monotonic() - began, 'line': line.rstrip()})
            process.wait(timeout=20)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
        total = time.monotonic() - began
        failures = [event for event in events if event['line'].startswith('FAIL') and 'test_b.py' in event['line']]
        text = '\n'.join(event['line'] for event in events)
        assert process.returncode == 1 and len(failures) == 1, text
        assert 'test_b.py: FAIL: test_fast_failure' in text and text.endswith('FAILED (1)'), text
        assert all(any(event['line'].endswith(name) for event in events) for name in ('test_a.py', 'test_b.py', 'test_c.py'))
        return {'feedback_seconds': failures[0]['seconds'], 'total_seconds': total,
                'returncode': process.returncode, 'load_before': before, 'load_after': os.getloadavg(),
                'events': events}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pairs', type=int, default=5)
    args = parser.parse_args()
    assert args.pairs > 0
    sources = {'baseline': args.baseline.resolve(), 'candidate': args.candidate.resolve()}
    report = {'host': {'platform': platform.platform(), 'python': sys.version, 'cpu_count': os.cpu_count()},
              'source_sha256': {name: digest(path) for name, path in sources.items()},
              'harness_sha256': digest(Path(__file__)),
              'method': 'Sequential alternating pairs; two workers; first job sleeps 1.5s after marker; second fails after marker; third passes. Startup included, setup excluded; no warmup.',
              'runs': []}
    for pair in range(args.pairs):
        for name in (['baseline', 'candidate'] if pair % 2 == 0 else ['candidate', 'baseline']):
            result = dict(pair=pair + 1, version=name, **sample(sources[name]))
            assert digest(sources[name]) == report['source_sha256'][name]
            report['runs'].append(result)
            args.output.write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps({key: result[key] for key in ('pair', 'version', 'feedback_seconds', 'total_seconds')}), flush=True)
    report['medians'] = {
        name: {key: statistics.median(run[key] for run in report['runs'] if run['version'] == name)
               for key in ('feedback_seconds', 'total_seconds')} for name in sources}
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
