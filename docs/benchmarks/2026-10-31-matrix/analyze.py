"""Validate and summarize measured trials; refuses success without complete quality evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('matrix_runner', HERE / 'run_matrix.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def analyze(data, grades, candidate="focused"):
    tasks = json.loads((HERE / 'tasks.json').read_text())['tasks']
    expected = {row['id'].replace('-focused', '-' + candidate) for row in runner.schedule(tasks)}
    rows = data['runs']
    ids = [row['id'] for row in rows]
    if len(set(ids)) != len(ids) or set(ids) != expected:
        raise ValueError('Incomplete, duplicate or unexpected trials')
    if not data.get('app_unchanged'):
        raise ValueError('Changed application')
    for row in rows:
        if not row.get('valid_completion'):
            continue
        usage = row['usage']
        if row['total_tokens'] != usage['input_tokens'] + usage['output_tokens']:
            raise ValueError('Double-counted or inconsistent total tokens')
        if not 0 <= usage['cached_input_tokens'] <= usage['input_tokens']:
            raise ValueError('Invalid cached subset')
        if not 0 <= usage['reasoning_output_tokens'] <= usage['output_tokens']:
            raise ValueError('Invalid reasoning subset')
    for task in tasks:
        prompts = {row['prompt_sha256'] for row in rows if row['task'] == task['id']}
        settings = {(row['model_requested'], row['effort_requested']) for row in rows if row['task'] == task['id']}
        if len(prompts) != 1 or settings != {(task['model'], task['effort'])}:
            raise ValueError('Unequal task/model/effort within task')
    by_id = {grade['id']: grade for grade in grades['grades']}
    if len(by_id) != len(grades['grades']) or set(by_id) != expected:
        raise ValueError('Quality evidence must cover every measured answer exactly once')
    summary = {}
    for task in tasks:
        tid = task['id']
        criteria = {c['id'] for c in task['criteria']}
        hard = {c['id'] for c in task['criteria'] if c['hard']}
        arms = {}
        for arm in ('v4.17.0', 'v5.8.0', candidate):
            selected = [row for row in rows if row['task'] == tid and row['arm'] == arm]
            quality = []
            for row in selected:
                grade = by_id[row['id']]
                if grade.get('answer_sha256') != row['answer_sha256'] or set(grade['criteria']) != criteria:
                    raise ValueError('Stale or incomplete quality evidence')
                if any(value not in (0, 1) for value in grade['criteria'].values()):
                    raise ValueError('Criterion grades must be binary')
                if not row['valid_completion'] and any(grade['criteria'].values()):
                    raise ValueError('Incomplete deliverable cannot receive a completed quality pass')
                score = sum(grade['criteria'].values()) / len(criteria)
                hard_pass = all(grade['criteria'][key] == 1 for key in hard)
                quality.append({'id': row['id'], 'score': score, 'hard_pass': hard_pass,
                                'unsupported_claims': grade.get('unsupported_claims', [])})
            complete = all(row['valid_completion'] for row in selected)
            arms[arm] = {'all_completed': complete, 'mean_total_tokens': statistics.mean(row['total_tokens'] for row in selected) if complete else None,
                         'total_token_samples': [row['total_tokens'] if row['valid_completion'] else None for row in selected],
                         'mean_uncached_input': statistics.mean(row['uncached_input_tokens'] for row in selected) if complete else None,
                         'mean_cached_input': statistics.mean(row['usage']['cached_input_tokens'] for row in selected) if complete else None,
                         'mean_output': statistics.mean(row['usage']['output_tokens'] for row in selected) if complete else None,
                         'mean_commands': statistics.mean(row['command_count'] for row in selected),
                         'mean_quality': statistics.mean(q['score'] for q in quality),
                         'all_hard_pass': all(q['hard_pass'] for q in quality),
                         'no_unsupported_claims': all(not q['unsupported_claims'] for q in quality), 'quality_samples': quality}
        focused = arms[candidate]
        base = arms['v4.17.0']
        current = arms['v5.8.0']
        ratio = (focused['mean_total_tokens'] / base['mean_total_tokens']
                 if focused['all_completed'] and base['all_completed'] else None)
        no_quality_loss = (focused['all_completed'] and focused['all_hard_pass'] and focused['no_unsupported_claims'] and focused['mean_quality'] >= max(base['mean_quality'], current['mean_quality']))
        summary[tid] = {'arms': arms, 'focused_reduction_vs_4_17_pct': 100 * (1 - ratio) if ratio is not None else None,
                        'focused_reduction_vs_5_8_pct': (100 * (1 - focused['mean_total_tokens'] / current['mean_total_tokens'])
                                                            if focused['all_completed'] and current['all_completed'] else None),
                        'no_quality_loss': no_quality_loss, 'meets_20_pct': ratio is not None and ratio <= .8,
                        'target_met': no_quality_loss and ratio is not None and ratio <= .8}
    reductions = [row['focused_reduction_vs_4_17_pct'] for row in summary.values()]
    aggregate = statistics.mean(reductions) if all(value is not None for value in reductions) else None
    return {'candidate': candidate, 'per_task': summary, 'equal_weight_reduction_vs_4_17_pct': aggregate,
            'target_met': aggregate is not None and aggregate >= 20 and all(row['target_met'] for row in summary.values()),
            'note': 'Two observations per arm/task; descriptive result, not statistical noninferiority or exact quota cost.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=HERE / 'matrix.json')
    parser.add_argument('--grades', type=Path, default=HERE / 'grades.json')
    parser.add_argument('--candidate', choices=('focused', 'packet', 'protocol', 'late'), default='focused')
    parser.add_argument('--output', type=Path, default=HERE / 'summary.json')
    args = parser.parse_args()
    data = json.loads(args.results.read_text())
    grades = json.loads(args.grades.read_text())
    if args.candidate in ('packet', 'protocol', 'late'):
        extra = json.loads((HERE / ('matrix-' + args.candidate + '.json')).read_text())
        data['runs'] = [row for row in data['runs'] if row['arm'] != 'focused'] + extra['runs']
        data['app_unchanged'] = data['app_unchanged'] and extra['app_unchanged']
    ids = {row['id'] for row in data['runs']}
    grades['grades'] = [grade for grade in grades['grades'] if grade['id'] in ids]
    for row in data['runs']:
        path = args.results.parent / (row['id'] + '-answer.md')
        if hashlib.sha256(path.read_text().removesuffix('\n').encode()).hexdigest() != row['answer_sha256']:
            raise SystemExit('Answer bytes differ from measured artifact')
    summary = analyze(data, grades, candidate=args.candidate)
    args.output.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({key: value for key, value in summary.items() if key != 'per_task'}, indent=2))


if __name__ == '__main__':
    main()
