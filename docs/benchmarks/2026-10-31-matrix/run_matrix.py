"""Actual-token source-investigation matrix. Launches subscription inference only with --run."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PIN = 'd2ef08cf1a84aaaf5db527ea44a62a1c811c7701'
ARMS = ('v4.17.0', 'v5.8.0', 'focused')
# Reverse each repeat's order and rotate positions across the task bank.
ORDERS = [('v4.17.0', 'v5.8.0', 'focused'), ('v5.8.0', 'focused', 'v4.17.0'),
          ('focused', 'v4.17.0', 'v5.8.0'), ('v4.17.0', 'focused', 'v5.8.0')]
PROJECT = '''# Project Context

Offline, source-only Casetodian investigation. Hono API: application/apps/api/src/; server use cases and repositories: application/packages/server/src/modules/; transports: application/packages/server/src/infrastructure/providers/; schemas: application/packages/contracts/src/; Prisma: application/prisma/. Relevant tests are beside these modules or in server/src and api/src/routes. Follow imports and use the user's known starting paths. Standard/direct, no registered target. No product edits, tests, build, install, database, secrets or application-provider/network calls. This task requests source inspection only, not implementation or application validation. Ignored workflow bookkeeping is permitted where mandatory. Do not run a full gate for this child analysis; no shipping change is authorized. Do not spawn agents.
'''
BOUNDARY = '''This is an offline read-only investigation in a disposable copy. Source paths in the question are relative to application/. Read root AGENTS.md, .lean/README.md and .lean/PROJECT.md and follow this release's normal context selection. No target is registered; do not run target routing. Do not read application/AGENTS.md; its external workspace routing is inapplicable to this controlled copy. Do not edit product files, execute tests/build/install/full gate, access secrets/network/providers/database or spawn agents. Mandatory ignored runtime bookkeeping is permitted. Answer at most 650 words, with implementation and test path:line evidence and explicit uncertainty. No test execution, deployed safety or whole-project DONE claims. Do not narrate the benchmark arm or workflow version. Budget: <=20 tool calls and 300 seconds; correctness is more important than brevity.'''


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def helpers():
    path = HERE.parent / '2026-10-31/token_experiment.py'
    spec = importlib.util.spec_from_file_location('earlier_token_experiment', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prompt_for(task):
    return ('Contract: risk=LOW quality=STANDARD acceptance=Answer the assigned source investigation accurately with citations and limitations.\n'
            + task['question'] + '\n' + BOUNDARY)


def schedule(tasks, repetitions=2):
    rows = []
    for repeat in range(repetitions):
        for index, task in enumerate(tasks):
            order = ORDERS[index % len(ORDERS)]
            if repeat % 2:
                order = tuple(reversed(order))
            rows.extend({'id': f"{task['id']}-r{repeat + 1}-{arm}", 'task': task['id'],
                         'repeat': repeat + 1, 'arm': arm} for arm in order)
    return rows


def parse_events(path):
    events, malformed = [], 0
    for line in path.read_text(errors='replace').splitlines():
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError('not an event object')
            events.append(event)
        except (json.JSONDecodeError, ValueError):
            malformed += 1
    usage_rows = [e['usage'] for e in events if e.get('type') == 'turn.completed' and isinstance(e.get('usage'), dict)]
    usage = {key: sum(row.get(key, 0) for row in usage_rows)
             for key in ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens', 'cache_write_input_tokens')}
    messages = [e['item'].get('text', '') for e in events if e.get('type') == 'item.completed'
                and e.get('item', {}).get('type') == 'agent_message']
    commands = [e['item'] for e in events if e.get('type') == 'item.completed'
                and e.get('item', {}).get('type') == 'command_execution']
    raw = messages[-1] if messages else ''
    answer = re.sub(r'\[([^\]]+)\]\((?:[^)]*/)?(application/[^)]+)\)', r'`\2`', raw)
    return {'usage': usage, 'usage_events': len(usage_rows), 'malformed_events': malformed,
            'command_count': len(commands), 'command_exit_codes': [c.get('exit_code') for c in commands],
            'tool_output_bytes': sum(len(c.get('aggregated_output', '').encode()) for c in commands),
            'total_tokens': usage['input_tokens'] + usage['output_tokens'],
            'uncached_input_tokens': usage['input_tokens'] - usage['cached_input_tokens'],
            'answer_sha256': sha(answer), 'raw_answer_sha256': sha(raw),
            'trace_sha256': sha(path.read_bytes()), 'answer': answer,
            'runtime_errors': [e for e in events if e.get('type') in ('error', 'turn.failed')]}


def clean_env():
    return {k: v for k, v in os.environ.items() if not (k.endswith('_API_KEY')
            or k.startswith(('LEAN_', 'CLAUDE_')) or k == 'CODEX_THREAD_ID')}


def save(path, result):
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(result, indent=2) + '\n')
    temporary.replace(path)


def run_one(job, task, app, out, local, env, helper, profile):
    ref = 'v5.8.0' if job['arm'] == 'focused' else job['arm']
    with tempfile.TemporaryDirectory(prefix='lean-matrix-') as temp:
        root = Path(temp)
        helper.export(ROOT, ref, root, ('AGENTS.md', 'CLAUDE.md', '.lean', '.codex'))
        source = root / 'application'
        source.mkdir()
        helper.export(app, PIN, source)
        (root / '.lean/PROJECT.md').write_text(PROJECT)
        (root / '.lean/config.json').write_text('{"mode":"standard","configured":true,"execution":"direct"}\n')
        (root / '.gitignore').write_text('.agent-runtime/\n')
        if job['arm'] == 'focused':
            agents = root / 'AGENTS.md'
            agents.write_text(agents.read_text() + '\n' + profile)
        for command in (['git', 'init', '-q', str(root)], ['git', '-C', str(root), 'add', '-A'],
                        ['git', '-C', str(root), '-c', 'user.name=Benchmark', '-c', 'user.email=benchmark@localhost', 'commit', '-qm', 'pin matrix fixture']):
            subprocess.run(command, check=True, capture_output=True)
        command = ['codex', 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--json',
                   '-m', task['model'], '-c', f'model_reasoning_effort="{task["effort"]}"',
                   '--sandbox', 'workspace-write', '-C', str(root), '-']
        trace = local / (job['id'] + '.jsonl')
        stderr = local / (job['id'] + '.stderr')
        started = now()
        began = time.monotonic()
        timeout = False
        with trace.open('w') as stdout, stderr.open('w') as errors:
            child = subprocess.Popen(command, env=env, stdin=subprocess.PIPE, stdout=stdout, stderr=errors,
                                     text=True, start_new_session=True)
            child.stdin.write(prompt_for(task))
            child.stdin.close()
            try:
                code = child.wait(timeout=300)
            except subprocess.TimeoutExpired:
                timeout = True
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                code = child.returncode
        row = dict(job, started_at=started, ended_at=now(), elapsed_s=round(time.monotonic() - began, 2),
                   model_requested=task['model'], effort_requested=task['effort'], size=task['size'],
                   workflow_commit=helper.git(ROOT, 'rev-parse', ref + '^{commit}').decode().strip(),
                   exit_code=code, timed_out=timeout, prompt_sha256=sha(prompt_for(task)),
                   fixture_changes=helper.git(root, 'status', '--porcelain').decode().strip(), **parse_events(trace))
        answer = row.pop('answer')
        (out / (job['id'] + '-answer.md')).write_text(answer + '\n')
        row['answer_words'] = len(answer.split())
        row['valid_completion'] = bool(code == 0 and row['usage_events'] == 1 and answer and not timeout
                                       and not row['fixture_changes'] and not row['runtime_errors'] and not row['malformed_events'])
        return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path)
    parser.add_argument('--output', type=Path, default=HERE / 'matrix.json')
    parser.add_argument('--run', action='store_true', help='explicitly launch paid-by-subscription inference')
    args = parser.parse_args()
    tasks = json.loads((HERE / 'tasks.json').read_text())['tasks']
    jobs = schedule(tasks)
    if not args.run:
        print(json.dumps({'sessions': len(jobs), 'max_concurrent': 1, 'schedule': jobs}, indent=2))
        return
    if not args.app:
        parser.error('--run requires --app')
    helper = helpers()
    app = args.app.resolve()
    if Path(helper.git(app, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != app:
        raise SystemExit('Uninitialized application repository')
    if helper.git(app, 'rev-parse', 'HEAD').decode().strip() != PIN or helper.git(app, 'status', '--porcelain').strip():
        raise SystemExit('Application must be clean at frozen source revision')
    env = clean_env()
    login = subprocess.run(['codex', 'login', 'status'], env=env, capture_output=True, text=True, check=True)
    if 'ChatGPT' not in login.stdout + login.stderr:
        raise SystemExit('ChatGPT subscription login required')
    out = args.output.resolve().parent
    out.mkdir(parents=True, exist_ok=True)
    local = ROOT / '.agent-runtime/token-matrix'
    local.mkdir(parents=True, exist_ok=True)
    profile = (HERE / 'focused-context.md').read_text()
    identity = {'app_head': PIN, 'task_bank_sha256': sha((HERE / 'tasks.json').read_bytes()),
                'profile_sha256': sha(profile), 'project_sha256': sha(PROJECT),
                'runner_sha256': sha(Path(__file__).read_bytes()),
                'workflow_commits': {arm: helper.git(ROOT, 'rev-parse', arm + '^{commit}').decode().strip() for arm in ARMS[:2]}}
    if args.output.exists():
        result = json.loads(args.output.read_text())
        if result['identity'] != identity:
            raise SystemExit('Resume refused: frozen inputs changed; use a new output path')
    else:
        result = {'identity': identity, 'started_at': now(), 'schedule': jobs,
                  'cli_version': subprocess.check_output(['codex', '--version'], text=True).strip(),
                  'auth': 'ChatGPT subscription; user config ignored and environment API keys stripped',
                  'quota_before': helper.quota(env), 'runs': []}
        save(args.output, result)
    completed = {row['id'] for row in result['runs']}
    for job in jobs:
        if job['id'] in completed:
            continue
        task = next(task for task in tasks if task['id'] == job['task'])
        dispatch = dict(job, requested_model=task['model'], requested_effort=task['effort'], size=task['size'],
                        context='fresh/no parent history', at=now())
        with (local / 'dispatch.jsonl').open('a') as log:
            log.write(json.dumps(dispatch) + '\n')
        print(f"START {len(result['runs'])+1}/{len(jobs)} {job['id']} {task['model']}/{task['effort']}", flush=True)
        row = run_one(job, task, app, out, local, env, helper, profile)
        result['runs'].append(row)
        result['last_checkpoint_at'] = now()
        result['app_unchanged'] = (helper.git(app, 'rev-parse', 'HEAD').decode().strip() == PIN
                                   and not helper.git(app, 'status', '--porcelain').strip())
        save(args.output, result)
        print(f"END {job['id']} valid={row['valid_completion']} tokens={row['total_tokens']} commands={row['command_count']}", flush=True)
        if not row['valid_completion'] or not result['app_unchanged']:
            raise SystemExit('Incomplete trial retained; no automatic inference retry. Diagnose before resuming.')
    result['ended_at'] = now()
    result['quota_after'] = helper.quota(env)
    save(args.output, result)


if __name__ == '__main__':
    main()
