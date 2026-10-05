"""Offline catalog behavior tests with synthetic models and fixed evidence dates."""
from datetime import datetime, timedelta, timezone
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/model_catalog.py'
spec = importlib.util.spec_from_file_location('model_catalog', SCRIPT)
models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models)
NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz else NOW.replace(tzinfo=None)


def entry(provider='codex', model_id='fixture-model'):
    return {'provider': provider, 'id': model_id, 'runtime': 'codex-cli' if provider == 'codex' else 'claude-code',
            'runtime_version': 'fixture-1', 'lifecycle': 'active', 'availability': 'unknown',
            'supported_efforts': ['low', 'medium'],
            'sources': [{'url': 'https://developers.openai.com/codex/models' if provider == 'codex'
                         else 'https://code.claude.com/docs/en/model-config', 'checked_at': NOW.isoformat()}]}


class ModelCatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / '.lean').mkdir()
        self.path = self.root / '.lean/model-catalog.json'
        self.candidate = self.root / 'candidate.json'
        self.proposal_path = self.root / 'proposal.json'
        self.clock = patch.object(models, 'datetime', Clock)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def candidate_for(self, *entries):
        self.candidate.write_text(json.dumps({'version': 1, 'models': list(entries or (entry(),))}))
        return self.candidate

    def plan(self, provider='codex'):
        report = models.preview(self.root, self.candidate, provider)
        self.proposal_path.write_text(json.dumps(report))
        return report

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_preview_and_missing_catalog_check_write_nothing(self):
        self.candidate_for()
        before = self.snapshot()
        report = models.preview(self.root, self.candidate, 'codex')
        self.assertIn('fixture-model', report['diff'])
        self.assertEqual(models.current(self.root), ({'version': 1, 'models': []}, None))
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / '.agent-runtime').exists())

    def test_apply_writes_only_catalog_and_is_idempotent(self):
        self.candidate_for()
        report = self.plan()
        config = self.root / '.lean/config.json'
        config.write_text('{"mode":"standard","execution":"direct"}')
        settings = self.root / '.claude/agents/reviewer.md'
        settings.parent.mkdir(parents=True)
        settings.write_text('model: inherit\n')
        before = self.snapshot()
        self.assertTrue(models.apply(self.root, self.proposal_path, report['sha256'])['applied'])
        for path, content in before.items():
            self.assertEqual((self.root / path).read_bytes(), content)
        self.assertEqual(set(self.snapshot()) - set(before),
                         {'.lean/model-catalog.json', '.agent-runtime/model-catalog.lock'})
        saved = self.path.read_bytes()
        self.assertTrue(models.apply(self.root, self.proposal_path, report['sha256'])['unchanged'])
        self.assertEqual(self.path.read_bytes(), saved)

    def test_partial_provider_update_preserves_other_provider_and_extensions(self):
        other = entry('claude')
        self.path.write_text(json.dumps({'version': 1, 'models': [other], 'custom': {'keep': True}}))
        self.candidate_for()
        report = self.plan()
        models.apply(self.root, self.proposal_path, report['sha256'])
        catalog, _ = models.current(self.root)
        self.assertIn(other, catalog['models'])
        self.assertEqual(catalog['custom'], {'keep': True})

    def test_all_provider_update_and_alias_resolution_are_explicit(self):
        claude = dict(entry('claude', 'fixture-alias'), alias_target='fixture-resolved')
        self.candidate_for(entry(), claude)
        report = self.plan('all')
        models.apply(self.root, self.proposal_path, report['sha256'])
        self.assertEqual(models.current(self.root)[0]['models'], [entry(), claude])

    def test_invalid_catalog_fields(self):
        cases = [('provider', 'invalid'), ('id', ''), ('runtime_version', ''), ('runtime', 'api-only'),
                 ('availability', 'yes'), ('lifecycle', 'deleted'), ('supported_efforts', ['impossible']),
                 ('supported_efforts', ['low', 'low']), ('sources', []), ('alias_target', '')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    models.validate({'version': 1, 'models': [dict(entry(), **{field: value})]})
        for version in (True, 2, '1'):
            with self.assertRaises(ValueError):
                models.validate({'version': version, 'models': []})

    def test_duplicate_models_and_cross_provider_runtime_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            models.validate({'version': 1, 'models': [entry(), entry()]})
        with self.assertRaisesRegex(ValueError, 'runtime'):
            models.validate({'version': 1, 'models': [dict(entry('claude'), runtime='codex-cli')]})

    def test_known_availability_needs_observed_runtime_evidence(self):
        for state in ('available', 'unavailable'):
            with self.assertRaisesRegex(ValueError, 'runtime observation'):
                models.validate({'version': 1, 'models': [dict(entry(), availability=state)]})
        observed = dict(entry(), availability='available', runtime_observation={
            'checked_at': NOW.isoformat(), 'evidence': 'fixture runtime reports this model'})
        self.assertEqual(models.validate({'version': 1, 'models': [observed]}), [])

    def test_official_urls_and_evidence_dates_are_required(self):
        for url in ('http://developers.openai.com/a', 'https://developers.openai.com.evil.test/a',
                    'https://user:secret@developers.openai.com/a', 'https://code.claude.com/a'):
            bad = entry()
            bad['sources'][0]['url'] = url
            with self.assertRaises(ValueError):
                models.validate({'version': 1, 'models': [bad]})
        for date in ('invalid', '2026-10-05', (NOW + timedelta(seconds=1)).isoformat()):
            bad = entry()
            bad['sources'][0]['checked_at'] = date
            with self.assertRaises(ValueError):
                models.validate({'version': 1, 'models': [bad]})

    def test_stale_preview_and_apply_do_not_replace_old_catalog(self):
        old = entry()
        old['sources'][0]['checked_at'] = (NOW - timedelta(days=31)).isoformat()
        self.candidate_for(old)
        self.assertTrue(models.validate({'version': 1, 'models': [old]}))
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.plan()
        self.candidate_for()
        report = self.plan()
        with patch.object(models, 'MAX_AGE_DAYS', -1):
            with self.assertRaisesRegex(ValueError, 'stale'):
                models.apply(self.root, self.proposal_path, report['sha256'])
        self.assertFalse(self.path.exists())

    def test_exact_age_boundary_and_stale_observation(self):
        model = entry()
        model['sources'][0]['checked_at'] = (NOW - timedelta(days=30)).isoformat()
        self.assertEqual(models.validate({'version': 1, 'models': [model]}), [])
        model['availability'] = 'available'
        model['runtime_observation'] = {
            'checked_at': (NOW - timedelta(days=30, seconds=1)).isoformat(), 'evidence': 'fixture observed'}
        self.assertTrue(models.validate({'version': 1, 'models': [model]}))

    def test_catalog_and_base_digest_come_from_the_same_read(self):
        original_catalog = {'version': 1, 'models': [entry()]}
        newer_catalog = {'version': 1, 'models': [entry(model_id='newer-fixture')]}
        self.path.write_bytes(models.encoded(original_catalog))
        original_read = Path.read_text
        original_bytes = Path.read_bytes
        def intervening_write(path, *args, **kwargs):
            content = original_read(path, *args, **kwargs)
            if path == self.path:
                path.write_bytes(models.encoded(newer_catalog))
            return content
        def intervening_bytes(path, *args, **kwargs):
            content = original_bytes(path, *args, **kwargs)
            if path == self.path:
                path.write_bytes(models.encoded(newer_catalog))
            return content
        with patch.object(Path, 'read_text', intervening_write), patch.object(Path, 'read_bytes', intervening_bytes):
            catalog, checksum = models.current(self.root)
        self.assertEqual(checksum, hashlib.sha256(models.encoded(catalog)).hexdigest())

    def test_two_proposals_from_same_base_cannot_overwrite_each_other(self):
        self.candidate_for()
        first = self.plan()
        self.candidate_for(entry(model_id='second-fixture'))
        second = models.preview(self.root, self.candidate, 'codex')
        models.apply(self.root, self.proposal_path, first['sha256'])
        self.proposal_path.write_text(json.dumps(second))
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'changed since preview'):
            models.apply(self.root, self.proposal_path, second['sha256'])
        self.assertEqual(before, self.path.read_bytes())

    def test_missing_authorization_and_invalid_provider_cli_are_refused(self):
        for args in (['apply', '--proposal', str(self.proposal_path)],
                     ['preview', '--provider', 'unknown', '--candidate', str(self.candidate)]):
            result = subprocess.run(['python3', str(SCRIPT), '--root', str(self.root), *args],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(self.path.exists())
            self.assertFalse((self.root / '.agent-runtime').exists())

    def test_stale_unselected_provider_can_be_retained(self):
        other = entry('claude')
        other['sources'][0]['checked_at'] = (NOW - timedelta(days=31)).isoformat()
        self.path.write_text(json.dumps({'version': 1, 'models': [other]}))
        self.candidate_for()
        report = self.plan()
        models.apply(self.root, self.proposal_path, report['sha256'])
        self.assertTrue(models.validate(models.current(self.root)[0]))

    def test_changed_catalog_refuses_apply_without_modifying_it(self):
        self.candidate_for()
        report = self.plan()
        self.path.write_text(json.dumps({'version': 1, 'models': [entry('claude')]}))
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'changed since preview'):
            models.apply(self.root, self.proposal_path, report['sha256'])
        self.assertEqual(before, self.path.read_bytes())
        self.assertTrue((self.root / '.agent-runtime/model-catalog.lock').is_file())

    def test_digest_mismatch_and_tampering_are_rejected(self):
        self.candidate_for()
        report = self.plan()
        with self.assertRaisesRegex(ValueError, 'digest'):
            models.apply(self.root, self.proposal_path, 'wrong')
        report['proposal']['catalog']['models'][0]['id'] = 'changed-model'
        self.proposal_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'digest'):
            models.apply(self.root, self.proposal_path, report['sha256'])
        self.assertFalse(self.path.exists())

    def test_rehashed_proposal_cannot_modify_unselected_provider(self):
        self.path.write_text(json.dumps({'version': 1, 'models': [entry('claude')]}))
        self.candidate_for()
        report = self.plan()
        report['proposal']['catalog']['models'][0]['id'] = 'other-changed'
        report['sha256'] = models.digest(report['proposal'])
        self.proposal_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'unselected'):
            models.apply(self.root, self.proposal_path, report['sha256'])

    def test_atomic_write_failure_preserves_original_and_removes_temporary(self):
        self.path.write_text(json.dumps({'version': 1, 'models': []}))
        self.candidate_for()
        report = self.plan()
        original = self.path.read_bytes()
        with patch.object(models.os, 'replace', side_effect=OSError('fixture disk failure')):
            with self.assertRaisesRegex(OSError, 'disk failure'):
                models.apply(self.root, self.proposal_path, report['sha256'])
        self.assertEqual(original, self.path.read_bytes())
        self.assertEqual(sorted(x.name for x in self.path.parent.iterdir()), ['model-catalog.json'])

    def test_candidate_provider_mismatch_and_empty_replacement_fail(self):
        self.candidate_for(entry('claude'))
        with self.assertRaisesRegex(ValueError, 'selected providers'):
            self.plan()
        self.candidate.write_text('{"version":1,"models":[]}')
        with self.assertRaises(ValueError):
            self.plan()

    def test_duplicate_json_keys_and_nonfinite_json_fail(self):
        for text in ('{"version":1,"version":1,"models":[]}', '{"version":NaN,"models":[]}'):
            self.candidate.write_text(text)
            with self.assertRaises(ValueError):
                models.load(self.candidate)

    def test_retired_model_and_unknown_efforts_are_information_not_auto_selection(self):
        retired = dict(entry(), lifecycle='retired', supported_efforts=[])
        self.candidate_for(retired)
        report = self.plan()
        self.assertEqual(report['proposal']['catalog']['models'][0], retired)
        self.assertFalse(self.path.exists())

    def test_cli_check_and_missing_input_fail_without_refresh_or_runtime_changes(self):
        def cli(*args):
            return subprocess.run(['python3', str(SCRIPT), '--root', str(self.root), *args], capture_output=True, text=True)
        before = self.snapshot()
        check = cli('check')
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertFalse(json.loads(check.stdout)['present'])
        failure = cli('preview', '--provider', 'codex', '--candidate', str(self.root / 'missing.json'))
        self.assertEqual(failure.returncode, 2)
        self.assertIn('model catalog error', failure.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_catalog_symlink_cannot_redirect_apply(self):
        outside = self.root / 'outside.json'
        outside.write_text('{"version":1,"models":[]}')
        self.path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            models.current(self.root)
        self.assertEqual(outside.read_text(), '{"version":1,"models":[]}')


if __name__ == '__main__':
    unittest.main()
