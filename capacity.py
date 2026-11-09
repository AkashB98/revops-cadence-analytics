"""Capacity model — ONE formula only (deliberate scope cut; routing
and territory balance live in gtm-engineering-automation-kit, not
here):

    pipeline_needed = quota_gap / win_rate
    reps_needed     = ceil(pipeline_needed / ramped_rep_productivity)

i.e. reps_needed = ceil(quota_gap / win_rate / productivity), where
productivity is the pipeline a fully ramped rep can work in a
quarter. Plus a sensitivity table over win rate x productivity,
and the quota attainment distribution (kept because it is cheap:
it is a sort of numbers the forecast already produced).
"""

from __future__ import annotations

import math
from typing import Dict

from forecast import quarter_actual


def reps_needed(quota_gap: float, win_rate: float,
                productivity: float) -> int:
    if quota_gap <= 0:
        return 0
    if win_rate <= 0 or productivity <= 0:
        raise ValueError("win_rate and productivity must be positive")
    return math.ceil(quota_gap / win_rate / productivity)


def capacity_plan(dataset: Dict, win_rate: float = 0.30,
                  productivity: float = 600000.0) -> Dict:
    quota_total = sum(r["quarter_quota"] for r in dataset["reps"])
    forecast_total = quarter_actual(dataset)
    gap = round(quota_total - forecast_total, 2)
    pipeline_needed = (round(gap / win_rate, 2) if gap > 0 and win_rate > 0
                       else 0.0)
    return {
        "quota_total": round(quota_total, 2),
        "forecast_actual_basis": forecast_total,
        "quota_gap": gap,
        "win_rate": win_rate,
        "ramped_rep_productivity": productivity,
        "pipeline_needed": pipeline_needed,
        "reps_needed": reps_needed(gap, win_rate, productivity),
        "formula": "reps_needed = ceil(quota_gap / win_rate / "
                   "ramped_rep_productivity)",
    }


def sensitivity_table(quota_gap: float,
                      win_rates=(0.20, 0.25, 0.30, 0.35, 0.40),
                      productivities=(400000, 500000, 600000, 750000)):
    rows = []
    for wr in win_rates:
        row = {"win_rate": wr}
        for p in productivities:
            row[str(p)] = reps_needed(quota_gap, wr, float(p))
        rows.append(row)
    return rows


def quota_attainment(dataset: Dict) -> Dict:
    opp_rep = {o["opp_id"]: o for o in dataset["opportunities"]}
    won_by_rep = {r["rep_id"]: 0.0 for r in dataset["reps"]}
    for oid, oc in dataset["outcomes"].items():
        if oc["final_stage"] == "Closed Won":
            won_by_rep[opp_rep[oid]["rep_id"]] += oc["closed_amount"]
    rows = []
    for rep in sorted(dataset["reps"], key=lambda r: r["rep_id"]):
        won = round(won_by_rep[rep["rep_id"]], 2)
        rows.append({"rep_id": rep["rep_id"], "team": rep["team"],
                     "quota": rep["quarter_quota"], "won": won,
                     "attainment": round(won / rep["quarter_quota"], 4)
                     if rep["quarter_quota"] else 0.0})
    buckets = {"<50%": 0, "50-80%": 0, "80-100%": 0, "100-120%": 0,
               ">120%": 0}
    for r in rows:
        a = r["attainment"]
        if a < 0.5:
            buckets["<50%"] += 1
        elif a < 0.8:
            buckets["50-80%"] += 1
        elif a < 1.0:
            buckets["80-100%"] += 1
        elif a < 1.2:
            buckets["100-120%"] += 1
        else:
            buckets[">120%"] += 1
    return {"rows": rows, "buckets": buckets}
