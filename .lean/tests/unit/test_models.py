"""The per-provider model list: validation, sizing, provider detection and live checks."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support import ROOT  # noqa: E402
from lean import models  # noqa: E402
from lean.util import LeanError  # noqa: E402

SHIPPED = json.loads((ROOT / ".lean/models.json").read_text())


class ModelListTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / ".lean").mkdir()

    def write(self, data):
        (self.root / ".lean/models.json").write_text(json.dumps(data))

    def test_shipped_list_covers_every_provider_and_size_with_one_agent_by_default(self):
        self.assertEqual(models.validate(SHIPPED), [])
        self.assertEqual(set(SHIPPED["providers"]), set(models.PROVIDERS))
        self.assertEqual(SHIPPED["max_agents"], 1)
        for provider in models.PROVIDERS:
            self.assertEqual(set(SHIPPED["providers"][provider]["tiers"]), set(models.TIERS))

    def test_invalid_lists_name_the_problem(self):
        cases = {
            "max_agents": lambda d: d.update(max_agents=0),
            "default_provider": lambda d: d.update(default_provider="gemini"),
            "unknown provider": lambda d: d["providers"].update(gemini=d["providers"]["agy"]),
            "tiers": lambda d: d["providers"]["claude"]["tiers"].pop("XL"),
            "{prompt}": lambda d: d["providers"]["codex"].update(args=["exec", "-m", "{model}"]),
            "needs a model": lambda d: d["providers"]["agy"]["tiers"]["S"].update(model=""),
        }
        for expected, change in cases.items():
            with self.subTest(expected=expected):
                data = copy.deepcopy(SHIPPED)
                change(data)
                problems = models.validate(data)
                self.assertTrue(any(expected in problem for problem in problems), problems)
                self.write(data)
                with self.assertRaises(LeanError):
                    models.load(self.root)

    def test_resolve_maps_sizes_and_refuses_unknown_ones(self):
        self.write(SHIPPED)
        data = models.load(self.root)
        self.assertEqual(models.resolve(data, "claude", "M"), (SHIPPED["providers"]["claude"]["tiers"]["M"]["model"],
                                                               "medium"))
        self.assertEqual(models.resolve(data, "agy", "XL")[1], None)
        for provider, tier in (("gemini", "S"), ("claude", "XXL")):
            with self.assertRaises(LeanError):
                models.resolve(data, provider, tier)

    def test_eight_sizes_in_order_and_a_four_size_list_still_works(self):
        self.assertEqual(models.TIERS, ("3S", "2S", "S", "M", "L", "XL", "2XL", "3XL"))
        # A project list from 5.0 defines only S/M/L/XL: still valid, and the new sizes are refused, not substituted.
        old = copy.deepcopy(SHIPPED)
        for provider in old["providers"].values():
            provider["tiers"] = {tier: provider["tiers"][tier] for tier in models.REQUIRED_TIERS}
        self.assertEqual(models.validate(old), [])
        self.write(old)
        data = models.load(self.root)
        self.assertEqual(models.resolve(data, "codex", "S")[0], old["providers"]["codex"]["tiers"]["S"]["model"])
        with self.assertRaises(LeanError) as raised:
            models.resolve(data, "codex", "2XL")
        self.assertIn("size 2XL is not defined for codex", str(raised.exception))
        self.assertIn("S, M, L, XL", str(raised.exception))
        self.assertNotIn("2XL", models.table(data))
        # A size outside the eight is a problem; so is a missing required one.
        bad = copy.deepcopy(SHIPPED)
        bad["providers"]["claude"]["tiers"]["4XL"] = bad["providers"]["claude"]["tiers"]["XL"]
        self.assertTrue(any("may add 3S, 2S, 2XL, 3XL" in problem for problem in models.validate(bad)))
        # The shipped table lists every size, smallest first.
        rows = [line.split()[0] for line in models.table(SHIPPED).splitlines()
                if line.startswith("  ")][:8]
        self.assertEqual(rows, list(models.TIERS))

    def test_detect_provider_from_the_runtime_environment(self):
        self.assertEqual(models.detect_provider(SHIPPED, {"CLAUDECODE": "1"}), "claude")
        self.assertEqual(models.detect_provider(SHIPPED, {"CODEX_THREAD_ID": "x"}), "codex")
        self.assertEqual(models.detect_provider(SHIPPED, {"ANTIGRAVITY_AGENT": "1"}), "agy")
        self.assertEqual(models.detect_provider(SHIPPED, {}), SHIPPED["default_provider"])

    def test_live_check_reports_missing_models_without_substituting(self):
        self.write(SHIPPED)
        codex = {tier["model"] for tier in SHIPPED["providers"]["codex"]["tiers"].values()}
        agy = {tier["model"] for tier in SHIPPED["providers"]["agy"]["tiers"].values()} - {"gemini-4-argon-high"}

        def fake(name, provider, timeout=30):
            return {"codex": (codex, ""), "agy": (agy, "")}.get(name, (None, "no listing"))
        with mock.patch.object(models, "available", fake):
            ok, lines = models.check(self.root, live=True)
        self.assertFalse(ok)
        self.assertTrue(any("agy.XL: gemini-4-argon-high is not available" in line for line in lines), lines)
        self.assertTrue(any(line.startswith("claude: no listing") for line in lines), lines)
        self.assertEqual(json.loads((self.root / ".lean/models.json").read_text()), SHIPPED)
        ok, lines = models.check(self.root)  # Offline: the schema only, no provider CLI.
        self.assertTrue(ok, lines)

    def test_codex_cache_and_agy_listing_are_parsed(self):
        cache = self.root / "models_cache.json"
        cache.write_text(json.dumps({"fetched_at": "2000-01-01T00:00:00Z", "models": [{"slug": "gpt-a"}, {"slug": "gpt-b"}]}))
        with mock.patch.object(models, "CODEX_CACHE", cache):
            found, note = models.available("codex", {"command": "codex"})
        self.assertEqual(found, {"gpt-a", "gpt-b"})
        self.assertIn("days old", note)
        listing = mock.Mock(returncode=0, stdout="Fetching available models...\ngem-a\tGem A\ngem-b\tGem B\n", stderr="")
        with mock.patch.object(models.subprocess, "run", return_value=listing):
            found, note = models.available("agy", {"command": "agy"})
        self.assertEqual((found, note), ({"gem-a", "gem-b"}, ""))
        self.assertIsNone(models.available("claude", {"command": "claude"})[0])


if __name__ == "__main__":
    unittest.main()
