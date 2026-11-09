import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator import (HAPPY_ID, SANDBAGGER_ID, generate_dataset)  # noqa: E402


class TestGenerator(unittest.TestCase):
    def setUp(self):
        self.d = generate_dataset()

    def test_deterministic(self):
        self.assertEqual(generate_dataset(), self.d)

    def test_shape(self):
        self.assertEqual(len(self.d["reps"]), 24)
        self.assertEqual(len(self.d["accounts"]), 90)
        self.assertEqual(len(self.d["opportunities"]), 216)
        self.assertEqual(len(self.d["snapshots"]), 1647)

    def test_planted_ids(self):
        self.assertEqual(self.d["planted"]["sandbagger"], "R07")
        self.assertEqual(self.d["planted"]["happy_ears"], "R19")
        self.assertEqual(SANDBAGGER_ID, "R07")
        self.assertEqual(HAPPY_ID, "R19")

    def test_sandbagger_all_won_happy_mostly_not(self):
        out = self.d["outcomes"]
        sand = [o for o in self.d["opportunities"] if o["rep_id"] == "R07"]
        happy = [o for o in self.d["opportunities"] if o["rep_id"] == "R19"]
        self.assertTrue(all(out[o["opp_id"]]["fate"] == "won" for o in sand))
        won_happy = sum(1 for o in happy
                        if out[o["opp_id"]]["fate"] == "won")
        self.assertEqual(won_happy, 2)
        self.assertEqual(len(happy), 9)

    def test_slipped_deals_land_outside_quarter(self):
        for oid in self.d["planted"]["slipped_opp_ids"]:
            oc = self.d["outcomes"][oid]
            self.assertGreaterEqual(oc["final_close_week"], 12)
            self.assertEqual(oc["fate"], "slipped_out")

    def test_snapshots_point_in_time_bounds(self):
        opp = {o["opp_id"]: o for o in self.d["opportunities"]}
        for s in self.d["snapshots"]:
            self.assertGreaterEqual(s["snapshot_week"],
                                    opp[s["opp_id"]]["created_week"])
            self.assertLessEqual(s["snapshot_week"], 11)

    def test_quota_total(self):
        self.assertEqual(sum(r["quarter_quota"] for r in self.d["reps"]),
                         6340000)


if __name__ == "__main__":
    unittest.main()
