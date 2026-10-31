"""Create a blinded quality packet; --run invokes one independent subscription auditor."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('matrix_runner', HERE / 'run_matrix.py')
matrix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matrix)
SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {
    'grades': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'properties': {
        'blind_id': {'type': 'string'},
        'passed_criteria': {'type': 'array', 'items': {'type': 'string'}},
        'failed_criteria': {'type': 'array', 'items': {'type': 'string'}},
        'evidence': {'type': 'string'},
        'unsupported_claims': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['blind_id', 'passed_criteria', 'failed_criteria', 'evidence', 'unsupported_claims']}}},
    'required': ['grades']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    measured = json.loads((HERE / 'matrix.json').read_text())
    if len(measured['runs']) != 24 or not measured.get('app_unchanged'):
        raise SystemExit('Complete valid measured matrix required')
    for filename in ('matrix-packet.json', 'matrix-protocol.json', 'matrix-late.json'):
        extra_path = HERE / filename
        if extra_path.exists():
            extra = json.loads(extra_path.read_text())
            if len(extra['runs']) != 8 or not extra.get('app_unchanged'):
                raise SystemExit('Additional intervention is incomplete: ' + filename)
            measured['runs'].extend(extra['runs'])
    count = len(measured['runs'])
    tasks = json.loads((HERE / 'tasks.json').read_text())['tasks']
    packet = {'tasks': tasks, 'answers': []}
    mapping = {}
    for row in measured['runs']:
        blind_id = 'answer-' + matrix.sha(row['id'])[:12]
        text = (HERE / (row['id'] + '-answer.md')).read_text().removesuffix('\n')
        if matrix.sha(text) != row['answer_sha256']:
            raise SystemExit('Measured answer changed')
        packet['answers'].append({'blind_id': blind_id, 'task': row['task'], 'completed': row['valid_completion'], 'answer': text})
        mapping[blind_id] = row
    packet['answers'].sort(key=lambda item: item['blind_id'])
    local = matrix.ROOT / '.agent-runtime/token-matrix'
    local.mkdir(parents=True, exist_ok=True)
    (local / 'quality-packet.json').write_text(json.dumps(packet, indent=2))
    if not args.run:
        print(f'Prepared {count} blinded answers; no token counts or arm names in packet')
        return
    helper = matrix.helpers()
    app = args.app.resolve()
    if helper.git(app, 'rev-parse', 'HEAD').decode().strip() != matrix.PIN or helper.git(app, 'status', '--porcelain').strip():
        raise SystemExit('Source pin/cleanliness changed')
    with tempfile.TemporaryDirectory(prefix='lean-quality-') as temp:
        root = Path(temp)
        (root / 'application').mkdir()
        helper.export(app, matrix.PIN, root / 'application')
        (root / 'packet.json').write_text(json.dumps(packet, indent=2))
        manifest = {'tasks': []}
        for task in tasks:
            filename = 'answers-' + task['id'] + '.json'
            group = [answer for answer in packet['answers'] if answer['task'] == task['id']]
            (root / filename).write_text(json.dumps(group, indent=2))
            manifest['tasks'].append({'task': task, 'answers_file': filename, 'count': len(group)})
        (root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        (root / 'schema.json').write_text(json.dumps(SCHEMA))
        prompt = '''Independently audit the source accuracy and evidence quality of all blinded Casetodian answers described by manifest.json. Start with manifest.json, then process each task group and source together. Read answers in small batches (for example three per tool output) so no answer is lost to output truncation; the large packet.json is only a complete archive, not the preferred initial read. No parent conversation, token counts, treatment names or cost objective are provided. Each task includes frozen expected criteria; verify each against actual implementation/tests in application/ before grading. An answer with completed=false did not finish within the fixed protocol: fail all criteria and explicitly state incomplete; its partial text is not a completed deliverable. For completed answers a criterion passes only if the answer substantively covers its material facts accurately; equivalent wording is valid, merely reproducing a keyword is not. A missing material fact, contradiction or unsupported safety guarantee fails that criterion. Treat stated source limitations fairly: no tests were executed by these investigators. Record concrete factual unsupported claims, not style preferences. For concurrency criterion C6 inspect actual locking/re-read behavior and accept an accurately bounded analysis or a valid source-based rebuttal, not a required unsupported exploit claim. If the frozen expected criterion is wrong, report the inconsistency in evidence; do not invent a fact to match it.
Return one entry per blind_id, all criteria partitioned exactly once between passed_criteria/failed_criteria. Give concise source path:line evidence supporting every failure and any material unsupported claim. Do not change product files or measured answers. Do not read outside this temporary fixture, use network/credentials/database, run tests/build, or spawn agents. This is source-only independent grading, not an application gate or workflow version comparison. Read packet and relevant symbol/test blocks in batches; budget 30 tool calls, 600 seconds. Return only JSON conforming to schema.json.'''
        command = ['codex', 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--json',
                   '-m', 'gpt-6.1-sol', '-c', 'model_reasoning_effort="high"', '--sandbox', 'read-only',
                   '--skip-git-repo-check', '--output-schema', str(root / 'schema.json'), '-C', str(root), '-']
        trace = local / 'quality-audit.jsonl'
        with trace.open('w') as stdout, (local / 'quality-audit.stderr').open('w') as stderr:
            child = subprocess.Popen(command, env=matrix.clean_env(), stdin=subprocess.PIPE, stdout=stdout,
                                     stderr=stderr, text=True, start_new_session=True)
            child.stdin.write(prompt)
            child.stdin.close()
            try:
                code = child.wait(timeout=600)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                raise SystemExit('Auditor timed out; raw trace retained, no automatic retry')
        parsed = matrix.parse_events(trace)
        if code or parsed['usage_events'] != 1 or parsed['runtime_errors']:
            raise SystemExit('Auditor incomplete; inspect retained trace')
        answer = json.loads(parsed['answer'])
    by_task = {task['id']: task for task in tasks}
    grades = []
    seen = set()
    for grade in answer['grades']:
        blind = grade['blind_id']
        if blind not in mapping or blind in seen:
            raise SystemExit('Duplicate or unknown blinded answer')
        seen.add(blind)
        row = mapping[blind]
        expected = {criterion['id'] for criterion in by_task[row['task']]['criteria']}
        passed, failed = set(grade['passed_criteria']), set(grade['failed_criteria'])
        if passed & failed or passed | failed != expected:
            raise SystemExit('Auditor failed to partition frozen criteria')
        grades.append({'id': row['id'], 'answer_sha256': row['answer_sha256'],
                       'criteria': {key: int(key in passed) for key in sorted(expected)},
                       'evidence': grade['evidence'], 'unsupported_claims': grade['unsupported_claims']})
    if seen != set(mapping):
        raise SystemExit('Auditor did not cover all answers')
    output = {'method': 'Fresh independent model, randomized answer identifiers, no arm/token data; frozen rubric and pinned source',
              'model_requested': 'gpt-6.1-sol', 'effort_requested': 'high', 'size': 'L',
              'packet_sha256': matrix.sha(json.dumps(packet, indent=2)),
              'auditor_usage': parsed['usage'], 'trace_sha256': parsed['trace_sha256'], 'grades': grades}
    (HERE / 'grades.json').write_text(json.dumps(output, indent=2) + '\n')
    print(f'Independent blinded grades retained: {count} answers; auditor usage is separate from workload metric')


if __name__ == '__main__':
    main()
