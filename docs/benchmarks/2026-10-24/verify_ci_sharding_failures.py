#!/usr/bin/env python3
"""Disposable success/failure probes for the existing runner, no production edits."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / '.lean/tests/run_tests.py'
PASS = 'import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n'
FAIL = 'import unittest\nclass T(unittest.TestCase):\n def test_bad(self): self.fail("planted failure")\n'
MIXED = FAIL + '\n def test_ok(self): pass\n def test_other(self): pass\n'
CASES = [
    ('passing', {'test_ok.py': PASS}, [], 0, 'OK'),
    ('python_failure', {'test_bad.py': FAIL}, [], 1, 'planted failure'),
    ('failed_shard', {'test_mixed.py': MIXED}, [], 1, 'planted failure'),
    ('shell_failure', {'suite.sh': 'echo planted shell failure\nexit 3\n'}, ['suite.sh'], 1, 'planted shell failure'),
    ('import_failure', {'test_broken.py': 'raise ImportError("planted import failure")\n'}, [], 1, 'planted import failure'),
]


def main():
    assert len(sys.argv) == 2, 'output JSON path required'
    records = []
    for shards in (1, 6):
        for name, files, patterns, expected, marker in CASES:
            with tempfile.TemporaryDirectory() as temporary:
                start = Path(temporary) / '.lean/tests'
                start.mkdir(parents=True)
                for filename, body in files.items():
                    (start / filename).write_text(body)
                # Same CI flags/default worker bound; start-dir only selects disposable probes.
                command = [sys.executable, str(RUNNER), '--shards', str(shards), '--start-dir', str(start), *patterns]
                result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
                output = (result.stdout + result.stderr).replace(temporary, '<fixture>')
                passed = result.returncode == expected and marker in output
                if name == 'failed_shard' and shards == 6:
                    passed = passed and '[1/3]' in output and 'FAILED (1)' in output
                records.append({'case': name, 'shards': shards, 'command': [part.replace(temporary, '<fixture>') for part in command],
                                'expected_returncode': expected, 'returncode': result.returncode, 'passed': passed, 'output': output})
                assert passed, records[-1]
    Path(sys.argv[1]).write_text(json.dumps({'runs': records, 'all_passed': True}, indent=2) + '\n')
    print('10 disposable probes passed (shards 1 and 6; default CPU worker bound)')


if __name__ == '__main__':
    main()
