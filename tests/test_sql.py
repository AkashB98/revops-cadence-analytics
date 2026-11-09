import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forecast import (category_accuracy, forecast_at_week, funnel_cohort,  # noqa: E402
                      rep_bias)
from generator import generate_dataset  # noqa: E402
from metrics_sql import (category_accuracy_sql, cohort_sql,  # noqa: E402
                         pipeline_by_week_sql, rep_bias_sql)


class TestSqlMatchesPython(unittest.TestCase):
    def setUp(self):
        self.d = generate_dataset()

    def test_category_accuracy(self):
        py = category_accuracy(self.d)
        sql = category_accuracy_sql(self.d, week=8)
        for cat in ("commit", "best_case", "pipeline"):
            self.assertEqual(sql[cat]["deals"], py[cat]["deals"])
            self.assertEqual(sql[cat]["forecast"], py[cat]["forecast"])
            self.assertEqual(sql[cat]["actual_won"],
                             py[cat]["actual_won"])

    def test_rep_bias(self):
        py = rep_bias(self.d)
        sql = rep_bias_sql(self.d, week=8)
        self.assertEqual(set(sql), set(py))
        for rid in py:
            self.assertEqual(sql[rid]["weighted_forecast"],
                             py[rid]["weighted_forecast"])
            self.assertEqual(sql[rid]["actual"], py[rid]["actual"])
            self.assertEqual(sql[rid]["bias_share"],
                             py[rid]["bias_share"])

    def test_cohort(self):
        py = funnel_cohort(self.d)["cohorts"]
        sql = cohort_sql(self.d)
        self.assertEqual(len(sql), len(py))
        for a, b in zip(py, sql):
            self.assertEqual(a["created_week"], b["created_week"])
            self.assertEqual(a["deals"], b["deals"])
            self.assertEqual(a["won"], b["won"])
            self.assertEqual(a["won_amount"], b["won_amount"])

    def test_pipeline_by_week(self):
        sql = pipeline_by_week_sql(self.d)
        for week in (0, 4, 8, 11):
            f = forecast_at_week(self.d, week)
            for cat in ("commit", "best_case", "pipeline"):
                # an absent SQL group means zero deals / zero amount
                got = sql.get(week, {}).get(cat, {"amount": 0.0})["amount"]
                self.assertEqual(got, f["open_by_category"][cat])


if __name__ == "__main__":
    unittest.main()
