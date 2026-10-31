"""Two fresh subscription Codex sessions on real, pinned Casetodian source. Stdlib only."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import re
from pathlib import Path
import selectors
import subprocess
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
MODEL = 'gpt-6.1-sol'
EFFORT = 'medium'
PROMPT = '''Contract: risk=LOW quality=STANDARD acceptance=Explain Gmail connector removal coverage from current source with exact paths and limitations.
Investigate Casetodian's removal of the Gmail OAuth/API connector. Determine: (1) which old HTTP endpoints are no longer served and what tests establish; (2) exactly which stored secret fields the migration deletes and which credentials it preserves; (3) whether smtp.gmail.com still follows ordinary SMTP even with GMAIL_API_ENABLED=1. Inspect implementation as well as relevant tests, cite exact paths/lines, and identify any gaps in the evidence. Return at most 600 words.
This is a read-only, offline investigation in a disposable benchmark copy. Application files are under application/. Read root AGENTS.md, .lean/README.md and .lean/PROJECT.md as required; follow this release's normal context selection. No target is registered; do not run target routing. Do not read application/AGENTS.md: its workspace routing is inapplicable to this controlled copy. Do not edit product files, run tests/build/install/full gate, access secrets/network/providers/database, or spawn other agents. Ignored workflow runtime writes are permitted if mandatory. Budget: finish within 15 tool calls and 5 minutes. Report only source inspection, not test execution. Do not claim whole-project DONE.'''
PROJECT = '''# Project Context

Read-only Casetodian investigation benchmark. The application snapshot is application/ (React/Vite web, Hono API, pnpm workspace, PostgreSQL/Prisma). Workflow files are in this root. Standard/direct execution, no target registration. Do not install dependencies or run application checks: the task requests source analysis only, not implementation or validation. Relevant paths: application/apps/api/src/app.ts and routes/, application/packages/server/src/smtp-client.ts, application/prisma/migrations/ and tests alongside the implementation. No application source modifications, credentials, external calls, database, delegation or publication are authorized. Workflow runtime writes may be used for required bookkeeping. No shipping change means no full gate for this analysis-only child session.
'''


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def export(source, ref, dest, paths=()):
    with tarfile.open(fileobj=io.BytesIO(git(source, 'archive', ref, *paths))) as archive:
        archive.extractall(dest, filter='data')


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def quota(env):
    """Read account usage without starting an inference thread; discard account identifiers."""
    process = subprocess.Popen(['codex', 'app-server', '--stdio'], env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    def send(value):
        process.stdin.write(json.dumps(value) + '\n')
        process.stdin.flush()
    try:
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'lean-token-benchmark', 'version': '1'}}})
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if not selector.select(timeout=1):
                if process.poll() is not None:
                    break
                continue
            line = process.stdout.readline()
            if not line:
                break
            value = json.loads(line)
            if value.get('id') == 1:
                send({'method': 'initialized'})
                send({'id': 2, 'method': 'account/rateLimits/read'})
            elif value.get('id') == 2:
                data = value.get('result', {})
                return {'at': timestamp(), 'available': bool(data),
                        'rateLimits': data.get('rateLimits'), 'rateLimitsByLimitId': data.get('rateLimitsByLimitId'),
                        'error': value.get('error', {}).get('message')}
        return {'at': timestamp(), 'available': False, 'error': 'No quota response within 20s'}
    finally:
        selector.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    app = args.app.resolve()
    if Path(git(app, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != app:
        raise SystemExit('Not an initialized application repository')
    if git(app, 'status', '--porcelain').strip():
        raise SystemExit('Application must be clean')
    env = {k: v for k, v in os.environ.items() if not (k.endswith('_API_KEY') or k.startswith(('LEAN_', 'CLAUDE_')) or k == 'CODEX_THREAD_ID')}
    auth = subprocess.run(['codex', 'login', 'status'], env=env, capture_output=True, text=True, check=True)
    if 'ChatGPT' not in auth.stdout + auth.stderr:
        raise SystemExit('Subscription login required')
    local = ROOT / '.agent-runtime/token-benchmark'
    local.mkdir(parents=True, exist_ok=True)
    result = {'started_at': timestamp(), 'model_requested': MODEL, 'effort_requested': EFFORT,
              'cli_version': subprocess.check_output(['codex', '--version'], text=True).strip(),
              'auth': 'ChatGPT subscription; environment API keys removed; user config ignored',
              'app_head': git(app, 'rev-parse', 'HEAD').decode().strip(),
              'prompt_sha256': hashlib.sha256(PROMPT.encode()).hexdigest(),
              'project_sha256': hashlib.sha256(PROJECT.encode()).hexdigest(),
              'method': 'Single sequential A/B pair, 4.17.0 then 5.8.0; controlled source investigation, no full implementation/gate',
              'arms': []}
    for ref in ('v4.17.0', 'v5.8.0'):
        print(f'Preparing {ref}', flush=True)
        with tempfile.TemporaryDirectory(prefix=f'lean-tokens-{ref}-') as temporary:
            root = Path(temporary)
            export(ROOT, ref, root, ('AGENTS.md', 'CLAUDE.md', '.lean', '.codex'))
            application = root / 'application'
            application.mkdir()
            export(app, result['app_head'], application)
            (root / '.lean/PROJECT.md').write_text(PROJECT)
            (root / '.lean/config.json').write_text('{"mode":"standard","configured":true,"execution":"direct"}\n')
            (root / '.gitignore').write_text('.agent-runtime/\n')
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run(['git', '-C', str(root), 'add', '-A'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Benchmark', '-c', 'user.email=benchmark@localhost', 'commit', '-qm', 'pin investigation fixture'], check=True)
            before = quota(env)
            command = ['codex', 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--json',
                       '-m', MODEL, '-c', f'model_reasoning_effort="{EFFORT}"',
                       '--sandbox', 'workspace-write', '-C', str(root), '-']
            print(f'Running {ref}: {MODEL}/{EFFORT}', flush=True)
            began = time.monotonic()
            try:
                run = subprocess.run(command, env=env, input=PROMPT, text=True, capture_output=True, timeout=300)
            except subprocess.TimeoutExpired as exc:
                result['arms'].append({'ref': ref, 'error': '300s timeout; no retry', 'quota_before': before})
                args.output.write_text(json.dumps(result, indent=2) + '\n')
                raise SystemExit('Agent exceeded budget') from exc
            (local / f'{ref}.jsonl').write_text(run.stdout)
            (local / f'{ref}.stderr').write_text(run.stderr)
            events = []
            for line in run.stdout.splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            usage = [event.get('usage') for event in events if event.get('type') == 'turn.completed']
            messages = [event['item'].get('text', '') for event in events
                        if event.get('type') == 'item.completed' and event.get('item', {}).get('type') == 'agent_message']
            tools = [event['item'] for event in events if event.get('type') == 'item.completed'
                     and event.get('item', {}).get('type') == 'command_execution']
            raw_answer = messages[-1] if messages else ''
            answer = re.sub(r'\[([^\]]+)\]\((?:[^)]*/)?(application/[^)]+)\)', r'`\2`', raw_answer)
            (args.output.parent / f'{ref}-answer.md').write_text(answer + '\n')
            row = {'ref': ref, 'workflow_commit': git(ROOT, 'rev-parse', ref + '^{commit}').decode().strip(),
                   'exit_code': run.returncode, 'elapsed_s': round(time.monotonic() - began, 2),
                   'usage': usage, 'command_count': len(tools), 'command_exit_codes': [item.get('exit_code') for item in tools],
                   'event_types': sorted(set(event.get('type', '') for event in events)),
                   'tool_output_bytes': sum(len(item.get('aggregated_output', '').encode()) for item in tools),
                   'fixture_changes': git(root, 'status', '--porcelain').decode().strip(),
                   'quota_before': before, 'quota_after': quota(env), 'answer_sha256': hashlib.sha256(answer.encode()).hexdigest(),
                   'raw_answer_sha256': hashlib.sha256(raw_answer.encode()).hexdigest()}
            result['arms'].append(row)
            result['ended_at'] = timestamp()
            result['app_unchanged'] = (git(app, 'rev-parse', 'HEAD').decode().strip() == result['app_head']
                                       and not git(app, 'status', '--porcelain').strip())
            args.output.write_text(json.dumps(result, indent=2) + '\n')
            print(f'{ref}: exit={run.returncode}, usage={usage}, commands={len(tools)}', flush=True)
            if run.returncode or not usage or not answer:
                raise SystemExit('Missing successful answer/actual usage; inspect local trace, no automatic inference retry')


if __name__ == '__main__':
    main()
