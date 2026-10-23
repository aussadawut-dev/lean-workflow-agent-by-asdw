#!/usr/bin/env python3
"""Sequential CI sharding pairs, with actual unittest start IDs (stdlib only).

Run from the repository root. Recorder overhead is present in both timing arms.
Raw stdout and PID logs stay in ignored runtime storage; sanitized IDs are retained
in the JSON report after each run. Never runs a Quality Gate or remote CI.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / '.lean/tests'
RUNNER = TESTS / 'run_tests.py'
RECORDER = '''import os, sys, unittest
from pathlib import Path
_original_start = unittest.TestResult.startTest
def _start(self, test):
    module = sys.modules.get(type(test).__module__)
    source = getattr(module, '__file__', None)
    if source and Path(source).resolve().parent == Path(os.environ['LEAN_RECORD_SOURCE']).resolve():
        destination = Path(os.environ['LEAN_RECORD_DIR']) / (str(os.getpid()) + '.ids')
        with destination.open('a') as stream:
            stream.write(test.id() + '\\n')
    return _original_start(self, test)
unittest.TestResult.startTest = _start
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ids_digest(ids):
    return digest(('\n'.join(ids) + '\n').encode())


def self_check(recorder):
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        source, logs = base / 'source', base / 'logs'
        source.mkdir()
        logs.mkdir()
        (source / 'test_tiny.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_a(self): pass\n def test_b(self): pass\n')
        environment = dict(os.environ, PYTHONPATH=str(recorder), LEAN_RECORD_SOURCE=str(source), LEAN_RECORD_DIR=str(logs))
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(source)], env=environment, capture_output=True, text=True)
        actual = sorted(line for path in logs.glob('*.ids') for line in path.read_text().splitlines())
        expected = ['test_tiny.T.test_a', 'test_tiny.T.test_b']
        assert result.returncode == 0 and actual == expected, (result, actual)
        # Tests from another source must not enter the actual-source inventory.
        environment['LEAN_RECORD_SOURCE'] = str(base / 'other')
        for path in logs.glob('*.ids'):
            path.unlink()
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(source)], env=environment, capture_output=True, text=True)
        assert result.returncode == 0 and not list(logs.glob('*.ids'))
        return {'passed': True, 'recorded_ids': expected, 'unrelated_source_excluded': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=ROOT / '.agent-runtime/performance-20261024/ci-sharding')
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--pairs', type=int, default=2)
    parser.add_argument('--self-check-only', action='store_true')
    args = parser.parse_args()
    assert args.jobs > 0 and args.pairs > 0
    args.runtime.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        recorder = Path(temporary)
        (recorder / 'sitecustomize.py').write_text(RECORDER)
        checked = self_check(recorder)
        if args.self_check_only:
            print(json.dumps(checked))
            return
        names = sorted(path.name for path in TESTS.glob('test_*.py'))
        spec = importlib.util.spec_from_file_location('lean_bench_runner', RUNNER)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        discovered = sorted(test_id for name in names for test_id in runner.test_ids(TESTS, name))
        assert len(set(discovered)) == len(discovered) and discovered
        sources = sorted((ROOT / '.lean/scripts').glob('*.py')) + sorted(TESTS.glob('*'))
        fingerprints = {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in sources if path.is_file()}
        report = {'host': {'platform': platform.platform(), 'python': sys.version, 'cpu_count': os.cpu_count()},
                  'jobs': args.jobs, 'recorder_self_check': checked, 'recorder_sha256': digest(RECORDER.encode()),
                  'source_sha256': fingerprints, 'files': names, 'discovered_ids': discovered,
                  'discovered_count': len(discovered), 'inventory_sha256': ids_digest(discovered), 'runs': []}
        for pair in range(args.pairs):
            for shards in ([1, 6] if pair % 2 == 0 else [6, 1]):
                label = 'pair%d-shards%d' % (pair + 1, shards)
                logs = args.runtime / label
                logs.mkdir(exist_ok=False)
                command = [sys.executable, str(RUNNER), '-j', str(args.jobs), '--shards', str(shards)]
                environment = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, (str(recorder), os.environ.get('PYTHONPATH')))),
                                   LEAN_RECORD_SOURCE=str(TESTS), LEAN_RECORD_DIR=str(logs))
                before = os.getloadavg()
                began = time.monotonic()
                print('START ' + label, flush=True)
                with (logs / 'stdout.log').open('w') as stream:
                    result = subprocess.run(command, cwd=ROOT, env=environment, text=True, stdout=stream, stderr=subprocess.STDOUT)
                seconds = time.monotonic() - began
                actual = sorted(line for path in logs.glob('*.ids') for line in path.read_text().splitlines())
                counts = Counter(actual)
                run = {'label': label, 'command': command, 'returncode': result.returncode, 'seconds': seconds,
                       'load_before': before, 'load_after': os.getloadavg(), 'actual_count': len(actual),
                       'actual_ids': actual, 'actual_sha256': ids_digest(actual),
                       'missing': sorted(set(discovered) - set(actual)), 'unexpected': sorted(set(actual) - set(discovered)),
                       'duplicates': {key: value for key, value in counts.items() if value > 1},
                       'summary': (logs / 'stdout.log').read_text().strip().splitlines()[-1],
                       'sources_unchanged': all(digest((ROOT / path).read_bytes()) == value for path, value in fingerprints.items())}
                report['runs'].append(run)
                args.output.write_text(json.dumps(report, indent=2) + '\n')
                print('END ' + label + ' ' + json.dumps({key: run[key] for key in ('seconds', 'returncode', 'actual_count', 'missing', 'unexpected', 'duplicates', 'sources_unchanged', 'summary')}), flush=True)
                assert result.returncode == 0 and actual == discovered and run['sources_unchanged'], 'run failed; retained checkpoint'


if __name__ == '__main__':
    main()
