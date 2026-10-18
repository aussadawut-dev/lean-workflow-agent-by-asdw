"""model_drift.py reports only real drift between the catalog, Codex's live list and AGENTS.md."""
import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".lean/scripts"))
import model_drift  # noqa: E402

EFFORTS = ["low", "medium", "high"]


def iso(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago, seconds=5)).isoformat().replace("+00:00", "Z")


def entry(slug, days_ago=0, efforts=EFFORTS):
    return {"provider": "codex", "id": slug, "runtime": "codex-cli", "runtime_version": "1.0.0", "lifecycle": "active",
            "availability": "available", "supported_efforts": efforts,
            "sources": [{"url": "https://learn.chatgpt.com/docs/models", "checked_at": iso(days_ago)}],
            "runtime_observation": {"evidence": "fixture cache", "checked_at": iso(days_ago)}}


def live(slug, priority, visibility="list", efforts=EFFORTS):
    return {"slug": slug, "priority": priority, "visibility": visibility,
            "supported_reasoning_levels": [{"effort": e} for e in efforts]}


class ModelDriftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="model drift ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".lean/scripts").mkdir(parents=True)
        shutil.copy2(ROOT / ".lean/scripts/model_catalog.py", self.root / ".lean/scripts/model_catalog.py")
        self.cache = self.root / "models_cache.json"
        self.write(models=[entry("gpt-a"), entry("gpt-b")], live_models=[live("gpt-a", 1), live("gpt-b", 2)],
                   agents="Use `gpt-a` for work and `gpt-b` for small tasks.\n")

    def write(self, models, live_models, agents="", fetched=None):
        (self.root / ".lean/model-catalog.json").write_text(json.dumps({"version": 1, "models": models}))
        self.cache.write_text(json.dumps({"fetched_at": fetched or iso(), "models": live_models}))
        (self.root / "AGENTS.md").write_text(agents)

    def run_check(self):
        return model_drift.check(self.root, self.cache)

    def test_matching_catalog_cache_and_agents_has_no_drift(self):
        self.assertEqual(self.run_check(), ([], []))

    def test_catalogued_model_that_disappears_or_is_hidden_is_drift(self):
        self.write([entry("gpt-a"), entry("gpt-b")], [live("gpt-a", 1), live("gpt-b", 2, visibility="hide")])
        drift, _ = self.run_check()
        self.assertEqual(len(drift), 1)
        self.assertIn("gpt-b is no longer listed", drift[0])
        self.write([entry("gpt-a"), entry("gpt-b")], [live("gpt-a", 1)])
        self.assertIn("gpt-b is no longer listed", self.run_check()[0][0])

    def test_different_efforts_are_drift(self):
        self.write([entry("gpt-a"), entry("gpt-b")], [live("gpt-a", 1, efforts=EFFORTS + ["max"]), live("gpt-b", 2)])
        drift, _ = self.run_check()
        self.assertEqual(len(drift), 1)
        self.assertIn("gpt-a efforts differ", drift[0])

    def test_empty_cached_reasoning_levels_are_reported_as_a_change(self):
        self.write([entry('gpt-a')], [live('gpt-a', 1, efforts=[])])
        drift, notes = self.run_check()
        self.assertEqual(len(drift), 1)
        self.assertIn('efforts differ', drift[0])
        self.assertEqual(notes, [])

    def test_new_model_ranked_above_the_catalogue_is_drift_but_a_lower_one_is_not(self):
        models = [entry("gpt-a"), entry("gpt-b")]
        self.write(models, [live("gpt-a", 2), live("gpt-b", 3), live("gpt-new", 1)])
        drift, _ = self.run_check()
        self.assertEqual(len(drift), 1)
        self.assertIn("gpt-new ranked above", drift[0])
        self.write(models, [live("gpt-a", 1), live("gpt-b", 2), live("gpt-old", 9), live("gpt-secret", 0, visibility="hide")])
        self.assertEqual(self.run_check(), ([], []))

    def test_agents_naming_an_unlisted_model_is_drift(self):
        self.write([entry("gpt-a"), entry("gpt-b")], [live("gpt-a", 1), live("gpt-b", 2)], agents="Use `gpt-gone` for review.\n")
        drift, _ = self.run_check()
        self.assertEqual(drift, ["AGENTS.md names gpt-gone, which Codex does not list"])

    def test_evidence_older_than_thirty_days_is_drift(self):
        self.write([entry("gpt-a", days_ago=40), entry("gpt-b")], [live("gpt-a", 1), live("gpt-b", 2)])
        drift, _ = self.run_check()
        self.assertEqual(len(drift), 1)
        self.assertIn("older than 30 days: codex/gpt-a", drift[0])

    def test_missing_catalog_or_cache_is_a_note_not_drift(self):
        self.cache.unlink()
        drift, notes = self.run_check()
        self.assertEqual(drift, [])
        self.assertIn("cache not found", notes[0])
        (self.root / ".lean/model-catalog.json").unlink()
        self.assertEqual(self.run_check(), ([], ["no .lean/model-catalog.json; nothing to compare"]))

    def test_old_cache_is_a_note(self):
        self.write([entry("gpt-a"), entry("gpt-b")], [live("gpt-a", 1), live("gpt-b", 2)], fetched=iso(20))
        drift, notes = self.run_check()
        self.assertEqual(drift, [])
        self.assertIn("days old", notes[0])

    def test_exit_codes(self):
        args = ["--root", str(self.root), "--codex-cache", str(self.cache)]
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(model_drift.main(args), 0)
            self.write([entry("gpt-a"), entry("gpt-b")], [live("gpt-a", 1)])
            self.assertEqual(model_drift.main(args), 1)
            self.cache.write_text("{not json")
            self.assertEqual(model_drift.main(args), 2)
        self.assertIn("1 issue(s)", out.getvalue())

    def test_cli_cache_does_not_compare_desktop_or_claude_availability(self):
        desktop = dict(entry('desktop-only'), runtime='codex-desktop')
        claude = dict(entry('sonnet'), provider='claude', runtime='claude-code',
                      sources=[{'url': 'https://code.claude.com/docs/en/models', 'checked_at': iso()}])
        self.write([entry('gpt-a'), desktop, claude], [live('gpt-a', 1)])
        self.assertEqual(self.run_check(), ([], []))

    def test_runtime_variants_are_not_silently_overwritten(self):
        older = dict(entry('gpt-a', efforts=['low']), runtime_version='0.9.0')
        self.write([older, entry('gpt-a')], [live('gpt-a', 1)])
        self.assertIn('efforts differ', self.run_check()[0][0])

    def test_invalid_cache_metadata_returns_input_error(self):
        args = ['--root', str(self.root), '--codex-cache', str(self.cache)]
        for value in ([], {}, {'models': {}}, {'models': [None]},
                      {'models': [{'slug': 'gpt-a'}]},
                      {'models': [live('gpt-a', 'first')]},
                      {'models': [live('gpt-a', 1), live('gpt-a', 2)]}):
            self.cache.write_text(json.dumps(value))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(model_drift.main(args), 2)

    def test_default_root_uses_selected_target_and_writes_nothing(self):
        import submodule
        before = {str(p.relative_to(self.root)): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        with patch.object(submodule, 'context', return_value={'record_root': str(self.root)}) as selected:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(model_drift.main(['--codex-cache', str(self.cache)]), 0)
        selected.assert_called_once()
        self.assertIn('no drift', output.getvalue())
        after = {str(p.relative_to(self.root)): p.read_bytes()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
