"""Offline harness regressions; never invoke inference."""
import importlib.util
import copy
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('matrix_runner', Path(__file__).with_name('run_matrix.py'))
matrix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matrix)


class MatrixTests(unittest.TestCase):
    def test_counterbalanced_unique_complete_schedule(self):
        tasks = json.loads((matrix.HERE / 'tasks.json').read_text())['tasks']
        schedule = matrix.schedule(tasks)
        self.assertEqual(len(schedule), 24)
        self.assertEqual(len({job['id'] for job in schedule}), 24)
        for task in tasks:
            rows = [job for job in schedule if job['task'] == task['id']]
            first = [row['arm'] for row in rows if row['repeat'] == 1]
            second = [row['arm'] for row in rows if row['repeat'] == 2]
            self.assertEqual(set(first), set(matrix.ARMS))
            self.assertEqual(first, list(reversed(second)))

    def test_usage_subsets_not_double_counted_and_nonzero_command_retained(self):
        events = [{'type': 'item.completed', 'item': {'type': 'command_execution', 'exit_code': 1, 'aggregated_output': 'no match'}},
                  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '[source](/tmp/copy/application/a.ts:2)'}},
                  {'type': 'turn.completed', 'usage': {'input_tokens': 100, 'cached_input_tokens': 80, 'output_tokens': 20, 'reasoning_output_tokens': 5}}]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'trace'
            path.write_text('\n'.join(json.dumps(event) for event in events))
            result = matrix.parse_events(path)
        self.assertEqual(result['total_tokens'], 120)
        self.assertEqual(result['uncached_input_tokens'], 20)
        self.assertEqual(result['command_exit_codes'], [1])
        self.assertEqual(result['answer'], '`application/a.ts:2`')

    def test_failed_or_malformed_trace_not_silent_success(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'trace'
            path.write_text('bad event\n{"type":"turn.failed","error":{"message":"quota"}}\n')
            result = matrix.parse_events(path)
        self.assertEqual(result['usage_events'], 0)
        self.assertEqual(result['malformed_events'], 1)
        self.assertEqual(len(result['runtime_errors']), 1)
        self.assertEqual(result['answer'], '')



ANALYSIS_SPEC = importlib.util.spec_from_file_location('matrix_analysis', Path(__file__).with_name('analyze.py'))
analysis = importlib.util.module_from_spec(ANALYSIS_SPEC)
ANALYSIS_SPEC.loader.exec_module(analysis)


class AnalysisTests(unittest.TestCase):
    def fixture(self):
        tasks = json.loads((matrix.HERE / 'tasks.json').read_text())['tasks']
        data = {'app_unchanged': True, 'runs': []}
        grades = {'grades': []}
        by_task = {task['id']: task for task in tasks}
        for job in matrix.schedule(tasks):
            task = by_task[job['task']]
            total = 70 if job['arm'] == 'focused' else 100
            row = dict(job, valid_completion=True, total_tokens=total, uncached_input_tokens=total-30,
                       usage={'input_tokens': total-10, 'cached_input_tokens': 20, 'output_tokens': 10, 'reasoning_output_tokens': 2},
                       prompt_sha256='same-task', model_requested=task['model'], effort_requested=task['effort'],
                       answer_sha256='answer-hash', command_count=3)
            data['runs'].append(row)
            grades['grades'].append({'id': job['id'], 'answer_sha256': 'answer-hash',
                                     'criteria': {criterion['id']: 1 for criterion in task['criteria']}})
        return data, grades

    def test_measured_reduction_requires_complete_quality(self):
        data, grades = self.fixture()
        self.assertTrue(analysis.analyze(data, grades)['target_met'])
        incomplete = copy.deepcopy(grades)
        incomplete['grades'].pop()
        with self.assertRaisesRegex(ValueError, 'every measured answer'):
            analysis.analyze(data, incomplete)

    def test_less_tokens_does_not_hide_security_or_quality_regression(self):
        data, grades = self.fixture()
        critical = next(row for row in grades['grades'] if row['id'] == 'critical-r1-focused')
        critical['criteria']['C6'] = 0
        result = analysis.analyze(data, grades)
        self.assertFalse(result['target_met'])
        self.assertFalse(result['per_task']['critical']['no_quality_loss'])

    def test_unknown_timeout_tokens_not_zero_cost_or_primary_success(self):
        data, grades = self.fixture()
        failed = next(row for row in data['runs'] if row['id'] == 'critical-r1-v5.8.0')
        failed['valid_completion'] = False
        failed['total_tokens'] = 0
        grade = next(row for row in grades['grades'] if row['id'] == failed['id'])
        grade['criteria'] = {key: 0 for key in grade['criteria']}
        result = analysis.analyze(data, grades)
        self.assertIsNone(result['per_task']['critical']['arms']['v5.8.0']['mean_total_tokens'])
        self.assertIsNone(result['per_task']['critical']['focused_reduction_vs_5_8_pct'])
        failed = next(row for row in data['runs'] if row['id'] == 'critical-r1-v4.17.0')
        failed['valid_completion'] = False
        grade = next(row for row in grades['grades'] if row['id'] == failed['id'])
        grade['criteria'] = {key: 0 for key in grade['criteria']}
        result = analysis.analyze(data, grades)
        self.assertFalse(result['target_met'])
        self.assertIsNone(result['equal_weight_reduction_vs_4_17_pct'])

    def test_unsupported_claim_disqualifies_apparent_saving(self):
        data, grades = self.fixture()
        grade = next(row for row in grades['grades'] if row['id'] == 'low-r1-focused')
        grade['unsupported_claims'] = ['unproved guarantee']
        self.assertFalse(analysis.analyze(data, grades)['target_met'])

    def test_missing_trials_or_double_counted_cache_cannot_pass(self):
        data, grades = self.fixture()
        missing = copy.deepcopy(data)
        missing['runs'].pop()
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            analysis.analyze(missing, grades)
        data['runs'][0]['total_tokens'] += 20
        with self.assertRaisesRegex(ValueError, 'Double-counted'):
            analysis.analyze(data, grades)


PACKET_SPEC = importlib.util.spec_from_file_location('source_packet', Path(__file__).with_name('source_packet.py'))
packet = importlib.util.module_from_spec(PACKET_SPEC)
PACKET_SPEC.loader.exec_module(packet)


class PacketTests(unittest.TestCase):
    def test_exact_source_and_companion_in_one_packet(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'apps/api').mkdir(parents=True)
            (root / 'apps/api/thing.ts').write_text('export const value = 3;\n')
            (root / 'apps/api/thing.test.ts').write_text('expect(value).toBe(3);\n')
            result, stats = packet.collect(root, ['apps/api/thing.ts'])
            self.assertEqual(stats['files'], 2)
            self.assertIn('1: export const value = 3;', result)
            self.assertIn('application/apps/api/thing.test.ts', result)

    def test_omission_is_explicit_and_never_silent_truncation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'large.ts').write_text('one\ntwo\nthree\n')
            result, stats = packet.collect(root, ['large.ts'], line_budget=2)
            self.assertEqual(stats['files'], 0)
            self.assertEqual(stats['omitted'], 1)
            self.assertIn('3 complete lines exceeds remaining', result)
            self.assertNotIn('1: one', result)

    def test_known_entry_priority_preserves_dependencies_and_excludes_builds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'main.ts').write_text('export const main = 1;\n')
            (root / 'main.test.ts').write_text('import { helper } from "./deep.js";\n')
            (root / 'deep.ts').write_text('export const helper = 2;\n')
            (root / 'dist').mkdir()
            (root / 'dist/main.ts').write_text('STALE BUILD')
            result, _ = packet.collect(root, ['main.ts', 'main.test.ts'])
            self.assertIn('application/deep.ts', result)
            self.assertNotIn('STALE BUILD', result)

    def test_escape_and_external_symlink_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'source'
            root.mkdir()
            outside = Path(temp) / 'private.ts'
            outside.write_text('private-data')
            (root / 'linked.ts').symlink_to(outside)
            for entry in ('../private.ts', 'linked.ts'):
                with self.assertRaises(ValueError):
                    packet.collect(root, [entry])

    def test_known_shorthand_and_generic_migration_not_all_migrations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'apps/api').mkdir(parents=True)
            (root / 'apps/api/other.repository.ts').write_text('export const x = 1;')
            entries = packet.entries_for(root, 'Start apps/api/main.ts and other.repository.ts.')
            self.assertIn('apps/api/other.repository.ts', entries)
            (root / 'prisma/one').mkdir(parents=True)
            (root / 'prisma/two').mkdir(parents=True)
            (root / 'prisma/one/migration.sql').write_text('SELECT 1;')
            (root / 'prisma/two/migration.sql').write_text('SELECT 2;')
            result, stats = packet.collect(root, ['prisma/one/migration.sql'])
            self.assertEqual(stats['files'], 1)
            self.assertNotIn('SELECT 2', result)

if __name__ == '__main__':
    unittest.main()
