import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capacity import capacity_plan, quota_attainment, reps_needed, sensitivity_table  # noqa: E402
from generator import generate_dataset  # noqa: E402
from helpers import tiny_dataset  # noqa: E402


class TestCapacityFormula(unittest.TestCase):
    def test_hand_cases(self):
        # ceil(300000 / 0.30 / 600000) = ceil(1.666..) = 2
        self.assertEqual(reps_needed(300000, 0.30, 600000), 2)
        # exact division does not round up
        self.assertEqual(reps_needed(360000, 0.30, 600000), 2)
        self.assertEqual(reps_needed(360001, 0.30, 600000), 3)

    def test_no_gap_no_reps(self):
        self.assertEqual(reps_needed(0, 0.30, 600000), 0)
        self.assertEqual(reps_needed(-5000, 0.30, 600000), 0)

    def test_invalid_inputs_raise(self):
        with self.assertRaises(ValueError):
            reps_needed(1000, 0.0, 600000)
        with self.assertRaises(ValueError):
            reps_needed(1000, 0.30, 0)

    def test_sensitivity_monotone(self):
        table = sensitivity_table(298400)
        # higher win rate never needs more reps at fixed productivity
        for key in ("400000", "600000"):
            vals = [row[key] for row in table]
            self.assertEqual(vals, sorted(vals, reverse=True))

    def test_plan_tiny(self):
        plan = capacity_plan(tiny_dataset())
        self.assertEqual(plan["quota_total"], 200000)
        self.assertEqual(plan["quota_gap"], 190000)
        self.assertEqual(plan["reps_needed"], 2)

    def test_plan_seeded(self):
        plan = capacity_plan(generate_dataset())
        self.assertEqual(plan["quota_total"], 6340000)
        self.assertEqual(plan["quota_gap"], 298400)
        self.assertEqual(plan["pipeline_needed"], 994666.67)
        self.assertEqual(plan["reps_needed"], 2)


class TestAttainment(unittest.TestCase):
    def test_tiny_buckets(self):
        att = quota_attainment(tiny_dataset())
        self.assertEqual(att["buckets"]["<50%"], 2)
        rows = {r["rep_id"]: r for r in att["rows"]}
        self.assertEqual(rows["R01"]["attainment"], 0.1)
        self.assertEqual(rows["R02"]["attainment"], 0.0)

    def test_seeded_buckets(self):
        att = quota_attainment(generate_dataset())
        self.assertEqual(att["buckets"], {"<50%": 4, "50-80%": 6,
                                          "80-100%": 6, "100-120%": 4,
                                          ">120%": 4})
        self.assertEqual(sum(att["buckets"].values()), 24)


if __name__ == "__main__":
    unittest.main()
