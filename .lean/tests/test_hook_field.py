"""gate_evidence.py hook-field answers a non-object JSON payload with a message, not a Python error."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / ".lean/scripts/gate_evidence.py"
MESSAGE = "payload must be a JSON object"


def hook_field(payload, field="session_id"):
    return subprocess.run([sys.executable, str(HELPER), "--root", str(ROOT), "hook-field", "--field", field],
                          input=payload, text=True, capture_output=True, timeout=30)


class HookFieldTests(unittest.TestCase):
    def test_array_and_scalar_payloads_are_refused_with_a_message(self):
        for payload in ("[1]", "[]", "3", '"s"', "null", "true"):
            with self.subTest(payload=payload):
                result = hook_field(payload)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(MESSAGE, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_object_payload_still_answers_the_field(self):
        result = hook_field('{"session_id": "abc"}')
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "abc"), result.stderr)
        self.assertEqual(hook_field("{}", "session_id").stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
