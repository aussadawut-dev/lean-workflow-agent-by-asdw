"""Second intervention: same frozen task/model plus deterministic exact-source packet.

Keeps failed first-intervention results. Eight additional bounded sessions, never reruns controls.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load('base_matrix', 'run_matrix.py')
packet = load('packet', 'source_packet.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    tasks = json.loads((HERE / 'tasks.json').read_text())['tasks']
    jobs = [{'id': f'{task["id"]}-r{repeat}-packet', 'task': task['id'], 'repeat': repeat, 'arm': 'packet'}
            for repeat in (1, 2) for task in (tasks if repeat == 1 else list(reversed(tasks)))]
    if not args.run:
        print(json.dumps({'additional_sessions': 8, 'max_concurrent': 1, 'jobs': jobs}, indent=2))
        return
    controls = json.loads((HERE / 'matrix.json').read_text())
    if len(controls['runs']) != 24 or not controls.get('app_unchanged'):
        raise SystemExit('Original frozen matrix must complete before second intervention')
    helper = base.helpers()
    app = args.app.resolve()
    if helper.git(app, 'rev-parse', 'HEAD').decode().strip() != base.PIN or helper.git(app, 'status', '--porcelain').strip():
        raise SystemExit('Source must remain clean at frozen pin')
    env = base.clean_env()
    login = subprocess.run(['codex', 'login', 'status'], env=env, capture_output=True, text=True, check=True)
    if 'ChatGPT' not in login.stdout + login.stderr:
        raise SystemExit('Subscription login required')
    profile = (HERE / 'focused-context-v2.md').read_text()
    identity = {**controls['identity'], 'profile_sha256': base.sha(profile),
                'packet_tool_sha256': base.sha((HERE / 'source_packet.py').read_bytes()),
                'packet_runner_sha256': base.sha(Path(__file__).read_bytes())}
    output = HERE / 'matrix-packet.json'
    if output.exists():
        result = json.loads(output.read_text())
        if result['identity'] != identity:
            raise SystemExit('Inputs changed; resume refused')
    else:
        result = {'identity': identity, 'started_at': base.now(), 'schedule': jobs, 'runs': [],
                  'method': 'Second exploratory intervention after first-profile failures. Controls reused, not interleaved with this intervention. Same source/task/model; 2 reversed task-order repeats.'}
    local = base.ROOT / '.agent-runtime/token-matrix'
    done = {row['id'] for row in result['runs']}
    for job in jobs:
        if job['id'] in done:
            continue
        task = next(task for task in tasks if task['id'] == job['task'])
        packet_info = {}
        class PacketHelper:
            git = staticmethod(helper.git)
            @staticmethod
            def export(source, ref, dest, paths=()):
                helper.export(source, ref, dest, paths)
                if dest.name == 'application':
                    entries = packet.entries_for(dest, task['question'])
                    identifiers = re.findall(r'\b[A-Z][A-Z0-9]+_[A-Z0-9_]+\b', task['question'])
                    text, stats = packet.collect(dest, entries, identifiers=identifiers)
                    (dest.parent / 'source-context.md').write_text(text)
                    packet_info.update({'sha256': base.sha(text), 'entries': entries, 'stats': stats})
        with (local / 'dispatch.jsonl').open('a') as log:
            log.write(json.dumps(dict(job, requested_model=task['model'], requested_effort=task['effort'],
                                      size=task['size'], context='fresh/no parent history', at=base.now())) + '\n')
        print(f'START packet {len(result["runs"])+1}/8 {job["id"]}', flush=True)
        row = base.run_one(dict(job, arm='focused'), task, app, HERE, local, env, PacketHelper, profile)
        row['arm'] = 'packet'
        row['source_packet'] = packet_info
        result['runs'].append(row)
        result['app_unchanged'] = (helper.git(app, 'rev-parse', 'HEAD').decode().strip() == base.PIN
                                   and not helper.git(app, 'status', '--porcelain').strip())
        result['last_checkpoint_at'] = base.now()
        base.save(output, result)
        print(f'END {job["id"]} valid={row["valid_completion"]} tokens={row["total_tokens"]} commands={row["command_count"]}', flush=True)
        if not row['valid_completion'] or not result['app_unchanged']:
            raise SystemExit('Incomplete candidate retained; no automatic inference retry')
    result['ended_at'] = base.now()
    base.save(output, result)


if __name__ == '__main__':
    main()
