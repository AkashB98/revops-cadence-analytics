import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli import EXIT_ERROR, EXIT_FAIL, EXIT_OK, main as cli_main  # noqa: E402
from generator import dataset_to_json, generate_dataset  # noqa: E402


def _run(argv):
    with redirect_stdout(io.StringIO()) as out, \
            redirect_stderr(io.StringIO()):
        code = cli_main(argv)
    return code, out.getvalue()


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="revops-cli-")
        self.good = os.path.join(self.tmp, "book.json")
        with open(self.good, "w", encoding="utf-8") as fh:
            fh.write(dataset_to_json(generate_dataset()))

    def test_check_exit_codes(self):
        self.assertEqual(_run(["check", "--input", self.good])[0], EXIT_OK)
        self.assertEqual(_run(["check", "--input", self.good,
                               "--min-commit-hit", "0.999"])[0], EXIT_FAIL)
        self.assertEqual(_run(["check", "--input",
                               "/tmp/no-such-book-xyz.json"])[0], EXIT_ERROR)

    def test_generate_roundtrip(self):
        out = os.path.join(self.tmp, "gen.json")
        code, _ = _run(["generate", "--out", out])
        self.assertEqual(code, EXIT_OK)
        with open(out, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["opportunities"],
                             generate_dataset()["opportunities"])

    def test_forecast_week_and_full(self):
        code, text = _run(["forecast", "--input", self.good,
                           "--week", "8"])
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(text)
        self.assertEqual(payload["week"], 8)
        self.assertEqual(payload["weighted_forecast"], 6802180.0)
        code, text = _run(["forecast", "--input", self.good])
        payload = json.loads(text)
        self.assertEqual(payload["bias_outliers"]["sandbaggers"], ["R07"])
        self.assertEqual(payload["bias_outliers"]["happy_ears"], ["R19"])

    def test_cadence_and_capacity(self):
        code, text = _run(["cadence", "--input", self.good])
        self.assertEqual(code, EXIT_OK)
        cad = json.loads(text)
        self.assertEqual(len(cad["weeks"]), 12)
        self.assertEqual(cad["slippage"]["slipped_count"], 46)
        code, text = _run(["capacity", "--input", self.good])
        cap = json.loads(text)
        self.assertEqual(cap["plan"]["reps_needed"], 2)

    def test_report_is_forecast_call_memo(self):
        out = os.path.join(self.tmp, "weekly_forecast_call.md")
        code, _ = _run(["report", "--input", self.good, "--out", out])
        self.assertEqual(code, EXIT_OK)
        with open(out, encoding="utf-8") as fh:
            md = fh.read()
        self.assertIn("Weekly forecast call", md)
        self.assertIn("R07", md)
        self.assertIn("R19", md)
        self.assertIn("0.8022", md)


if __name__ == "__main__":
    unittest.main()
