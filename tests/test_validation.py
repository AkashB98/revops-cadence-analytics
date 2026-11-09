import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator import generate_dataset  # noqa: E402
from validation import validate_dataset  # noqa: E402
from helpers import tiny_dataset  # noqa: E402


class TestValidation(unittest.TestCase):
    def test_seeded_and_tiny_clean(self):
        self.assertEqual(validate_dataset(generate_dataset()), [])
        self.assertEqual(validate_dataset(tiny_dataset()), [])

    def test_bad_category(self):
        d = copy.deepcopy(tiny_dataset())
        d["snapshots"][0]["forecast_category"] = "sure_thing"
        issues = validate_dataset(d)
        self.assertTrue(any("category" in i for i in issues))

    def test_bad_stage(self):
        d = copy.deepcopy(tiny_dataset())
        d["snapshots"][0]["stage"] = "Vibes"
        self.assertTrue(any("stage" in i
                            for i in validate_dataset(d)))

    def test_duplicate_snapshot(self):
        d = copy.deepcopy(tiny_dataset())
        d["snapshots"].append(dict(d["snapshots"][0]))
        self.assertTrue(any("duplicate snapshot" in i
                            for i in validate_dataset(d)))

    def test_unknown_rep(self):
        d = copy.deepcopy(tiny_dataset())
        d["opportunities"][0]["rep_id"] = "R99"
        self.assertTrue(any("unknown rep" in i
                            for i in validate_dataset(d)))

    def test_nonpositive_amount(self):
        d = copy.deepcopy(tiny_dataset())
        d["opportunities"][0]["amount"] = 0
        self.assertTrue(any("positive" in i
                            for i in validate_dataset(d)))

    def test_missing_outcome(self):
        d = copy.deepcopy(tiny_dataset())
        del d["outcomes"]["A"]
        self.assertTrue(any("missing outcome" in i
                            for i in validate_dataset(d)))

    def test_not_a_dataset(self):
        self.assertEqual(validate_dataset([1, 2]),
                         ["dataset must be a JSON object"])
        self.assertTrue(validate_dataset({}))


if __name__ == "__main__":
    unittest.main()
