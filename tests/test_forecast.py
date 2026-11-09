import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forecast import (category_accuracy, detect_bias_outliers,  # noqa: E402
                      forecast_at_week, funnel_comparison, funnel_cohort,
                      funnel_snapshot_method, quarter_actual, rep_bias,
                      slippage)
from generator import generate_dataset  # noqa: E402
from helpers import tiny_dataset  # noqa: E402


class TestHandComputed(unittest.TestCase):
    def setUp(self):
        self.d = tiny_dataset()

    def test_forecast_at_week_4(self):
        f = forecast_at_week(self.d, 4)
        self.assertEqual(f["open_by_category"],
                         {"commit": 30000, "best_case": 30000,
                          "pipeline": 0.0})
        self.assertEqual(f["weighted_forecast"], 45000)
        self.assertEqual(f["call"], 60000)
        self.assertEqual(f["closed_won_to_date"], 0.0)

    def test_forecast_at_week_5_counts_close(self):
        f = forecast_at_week(self.d, 5)
        self.assertEqual(f["closed_won_to_date"], 10000)
        self.assertEqual(f["weighted_forecast"], 35000)

    def test_category_accuracy_week4(self):
        acc = category_accuracy(self.d, week=4)
        self.assertEqual(acc["commit"]["forecast"], 30000)
        self.assertEqual(acc["commit"]["hit_rate"], 0.3333)
        self.assertEqual(acc["best_case"]["hit_rate"], 0.0)
        self.assertEqual(acc["pipeline"]["pipeline_discount"], 1.0)

    def test_rep_bias_week4(self):
        rb = rep_bias(self.d, week=4)
        self.assertEqual(rb["R01"]["weighted_forecast"], 30000)
        self.assertEqual(rb["R01"]["actual"], 10000)
        self.assertEqual(rb["R01"]["bias"], 20000)
        self.assertEqual(rb["R01"]["bias_share"], 0.6667)
        self.assertEqual(rb["R02"]["bias_pct"], 100.0)  # zero-actual branch

    def test_slippage_tiny(self):
        s = slippage(self.d)
        self.assertEqual(s["slipped_count"], 1)
        self.assertEqual(s["slipped_amount"], 20000)
        self.assertEqual(s["slipped_deals"][0]["opp_id"], "B")
        self.assertEqual(s["stage_regression_count"], 1)
        self.assertEqual(s["stage_regressions"][0]["week"], 5)

    def test_funnel_tiny(self):
        coh = funnel_cohort(self.d)
        self.assertEqual(coh["overall_conversion"], 0.3333)
        by_week = {c["created_week"]: c for c in coh["cohorts"]}
        self.assertEqual(by_week[0]["conversion"], 0.5)
        self.assertEqual(by_week[1]["conversion"], 0.0)
        snap = funnel_snapshot_method(self.d, week=6)
        self.assertEqual(snap["snapshot_win_rate"], 0.5)

    def test_quarter_actual_tiny(self):
        self.assertEqual(quarter_actual(self.d), 10000)


class TestSeededBook(unittest.TestCase):
    def setUp(self):
        self.d = generate_dataset()

    def test_leakage_poison(self):
        base = forecast_at_week(self.d, 8)
        poisoned = copy.deepcopy(self.d)
        for s in poisoned["snapshots"]:
            if s["snapshot_week"] > 8:
                s["amount"] *= 100
        for oc in poisoned["outcomes"].values():
            if oc["actual_close_week"] is not None \
                    and oc["actual_close_week"] > 8:
                oc["closed_amount"] *= 100
        self.assertEqual(forecast_at_week(poisoned, 8), base)

    def test_detector_finds_exactly_planted(self):
        det = detect_bias_outliers(self.d)
        self.assertEqual(det["sandbaggers"], ["R07"])
        self.assertEqual(det["happy_ears"], ["R19"])

    def test_planted_bias_shares(self):
        rb = rep_bias(self.d)
        self.assertEqual(rb["R07"]["bias_share"], -0.3661)
        self.assertEqual(rb["R19"]["bias_share"], 0.6229)
        self.assertLess(rb["R07"]["bias"], 0)   # under-forecast
        self.assertGreater(rb["R19"]["bias"], 0)  # over-forecast

    def test_category_accuracy_seeded(self):
        acc = category_accuracy(self.d)
        self.assertEqual(acc["commit"]["hit_rate"], 0.8022)
        self.assertEqual(acc["best_case"]["best_case_conversion"], 0.3322)
        self.assertEqual(acc["pipeline"]["pipeline_discount"], 0.7418)

    def test_slippage_seeded(self):
        s = slippage(self.d)
        self.assertEqual(s["slipped_count"], 46)
        self.assertEqual(s["slipped_amount"], 2205200)
        self.assertEqual(s["stage_regression_count"], 46)
        self.assertEqual([x["opp_id"] for x in s["slipped_deals"]],
                         self.d["planted"]["slipped_opp_ids"])

    def test_funnel_gap_seeded(self):
        fun = funnel_comparison(self.d)
        self.assertEqual(fun["cohort_overall_conversion"], 0.5602)
        self.assertEqual(fun["snapshot_win_rate"], 0.7416)
        self.assertEqual(fun["gap_points"], 0.1814)


if __name__ == "__main__":
    unittest.main()
