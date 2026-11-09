"""Shared builders for the test suite (not a test module).

A hand-built 3-deal book where every forecast, hit rate, bias,
slippage count and funnel number is computable by hand:
  A (R01, $10k) — won at week 5.
  B (R01, $20k) — slips out of the quarter (final close 13),
    with one stage regression at week 5.
  C (R02, $30k) — lost at week 6.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _snap(w, oid, rid, stage, cat, amount, close):
    return {"snapshot_week": w, "opp_id": oid, "rep_id": rid,
            "stage": stage, "forecast_category": cat,
            "amount": amount, "close_week": close}


def tiny_dataset():
    reps = [
        {"rep_id": "R01", "rep_name": "Test One", "team": "Enterprise",
         "territory": "AMER-East", "quarter_quota": 100000},
        {"rep_id": "R02", "rep_name": "Test Two", "team": "Commercial",
         "territory": "EMEA", "quarter_quota": 100000},
    ]
    accounts = [{"account_id": "ACC001", "account_name": "Test Co 01",
                 "segment": "Enterprise"}]
    opps = [
        {"opp_id": "A", "account_id": "ACC001", "rep_id": "R01",
         "amount": 10000, "created_week": 0, "initial_close_week": 5},
        {"opp_id": "B", "account_id": "ACC001", "rep_id": "R01",
         "amount": 20000, "created_week": 0, "initial_close_week": 6},
        {"opp_id": "C", "account_id": "ACC001", "rep_id": "R02",
         "amount": 30000, "created_week": 1, "initial_close_week": 6},
    ]
    snaps = []
    a_stages = ["Prospecting", "Qualification", "Discovery",
                "Evaluation", "Negotiation", "Closed Won"]
    a_cats = ["pipeline", "pipeline", "pipeline", "best_case",
              "commit", "commit"]
    for w in range(6):
        snaps.append(_snap(w, "A", "R01", a_stages[w], a_cats[w], 10000, 5))
    b_stages = ["Prospecting", "Qualification", "Discovery",
                "Evaluation", "Negotiation", "Evaluation",
                "Evaluation", "Evaluation", "Evaluation",
                "Evaluation", "Evaluation", "Evaluation"]
    b_cats = ["pipeline", "pipeline", "pipeline", "best_case",
              "commit", "best_case", "best_case", "best_case",
              "best_case", "best_case", "best_case", "best_case"]
    b_close = [6, 6, 6, 6, 6, 7, 8, 9, 10, 11, 12, 13]
    for w in range(12):
        snaps.append(_snap(w, "B", "R01", b_stages[w], b_cats[w],
                           20000, b_close[w]))
    c_stages = ["Prospecting", "Qualification", "Discovery",
                "Evaluation", "Evaluation", "Closed Lost"]
    c_cats = ["pipeline", "pipeline", "pipeline", "best_case",
              "best_case", "commit"]
    for i, w in enumerate(range(1, 7)):
        snaps.append(_snap(w, "C", "R02", c_stages[i], c_cats[i], 30000, 6))
    outcomes = {
        "A": {"opp_id": "A", "final_stage": "Closed Won",
              "actual_close_week": 5, "closed_amount": 10000,
              "fate": "won", "final_close_week": 5},
        "B": {"opp_id": "B", "final_stage": "Open",
              "actual_close_week": None, "closed_amount": 0,
              "fate": "slipped_out", "final_close_week": 13},
        "C": {"opp_id": "C", "final_stage": "Closed Lost",
              "actual_close_week": 6, "closed_amount": 0,
              "fate": "lost", "final_close_week": 6},
    }
    return {"seed": 0, "weeks": 12, "quarter": "Q (weeks 0-11)",
            "reps": reps, "accounts": accounts, "opportunities": opps,
            "snapshots": snaps, "outcomes": outcomes,
            "planted": {"sandbagger": None, "happy_ears": None,
                        "slipped_opp_ids": ["B"]}}
