#!/usr/bin/env python3
"""Run the final integrated Python suite once, recording actual test IDs.

Reuses the historical recorder, not its two-arm benchmark main. No gate runs.
"""
import argparse
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

from benchmark_ci_sharding import ROOT, TESTS, RUNNER, RECORDER, digest, ids_digest, self_check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    args.runtime.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory() as temporary:
        recorder = Path(temporary)
        (recorder / 'sitecustomize.py').write_text(RECORDER)
        checked = self_check(recorder)
        spec = importlib.util.spec_from_file_location('final_runner', RUNNER)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        names = sorted(path.name for path in TESTS.glob('test_*.py'))
        discovered = sorted(test_id for name in names for test_id in runner.test_ids(TESTS, name))
        assert discovered and len(set(discovered)) == len(discovered)
        sources = sorted((ROOT / '.lean/scripts').glob('*.py')) + sorted(TESTS.glob('*'))
        fingerprints = {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in sources if path.is_file()}
        command = [sys.executable, str(RUNNER), '--shards', '6']
        environment = dict(os.environ,
                           PYTHONPATH=os.pathsep.join(filter(None, (str(recorder), os.environ.get('PYTHONPATH')))),
                           LEAN_RECORD_SOURCE=str(TESTS), LEAN_RECORD_DIR=str(args.runtime.resolve()))
        before = os.getloadavg()
        began = time.monotonic()
        print('START final integrated suite', flush=True)
        with (args.runtime / 'stdout.log').open('w') as stream:
            result = subprocess.run(command, cwd=ROOT, env=environment, text=True, stdout=stream, stderr=subprocess.STDOUT)
        seconds = time.monotonic() - began
        actual = sorted(line for path in args.runtime.glob('*.ids') for line in path.read_text().splitlines())
        counts = Counter(actual)
        report = {'host': {'platform': platform.platform(), 'python': sys.version, 'cpu_count': os.cpu_count()},
                  'command': command, 'returncode': result.returncode, 'seconds': seconds,
                  'load_before': before, 'load_after': os.getloadavg(), 'recorder_self_check': checked,
                  'recorder_sha256': digest(RECORDER.encode()), 'source_sha256': fingerprints,
                  'files': names, 'discovered_ids': discovered, 'discovered_count': len(discovered),
                  'inventory_sha256': ids_digest(discovered), 'actual_ids': actual, 'actual_count': len(actual),
                  'actual_sha256': ids_digest(actual), 'missing': sorted(set(discovered) - set(actual)),
                  'unexpected': sorted(set(actual) - set(discovered)),
                  'duplicates': {key: value for key, value in counts.items() if value > 1},
                  'summary': (args.runtime / 'stdout.log').read_text().strip().splitlines()[-1],
                  'sources_unchanged': all(digest((ROOT / path).read_bytes()) == value for path, value in fingerprints.items())}
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({key: report[key] for key in ('seconds', 'returncode', 'actual_count', 'missing', 'unexpected', 'duplicates', 'sources_unchanged', 'summary')}), flush=True)
        assert result.returncode == 0 and actual == discovered and report['sources_unchanged'], 'failed; see retained report/logs'


if __name__ == '__main__':
    main()
