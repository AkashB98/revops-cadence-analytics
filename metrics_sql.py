"""Core metrics recomputed in SQL via stdlib sqlite3.

Sales-ops roles screen on SQL, so the headline numbers exist as
.sql files under sql/, not only as Python. The dataset is loaded
into an in-memory sqlite database; tests and evals pin SQL results
equal to the Python implementations on every shared metric.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Dict

SQL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sql")


def _load(name: str) -> str:
    with open(os.path.join(SQL_DIR, name), encoding="utf-8") as fh:
        return fh.read()


def connect(dataset: Dict) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE reps (rep_id TEXT, rep_name TEXT, "
                "team TEXT, territory TEXT, quarter_quota REAL)")
    con.execute("CREATE TABLE accounts (account_id TEXT, "
                "account_name TEXT, segment TEXT)")
    con.execute("CREATE TABLE opportunities (opp_id TEXT, "
                "account_id TEXT, rep_id TEXT, amount REAL, "
                "created_week INT, initial_close_week INT)")
    con.execute("CREATE TABLE snapshots (snapshot_week INT, "
                "opp_id TEXT, rep_id TEXT, stage TEXT, "
                "forecast_category TEXT, amount REAL, close_week INT)")
    con.execute("CREATE TABLE outcomes (opp_id TEXT, final_stage TEXT, "
                "actual_close_week INT, closed_amount REAL, fate TEXT, "
                "final_close_week INT)")
    con.executemany("INSERT INTO reps VALUES (?,?,?,?,?)",
                    [(r["rep_id"], r["rep_name"], r["team"],
                      r["territory"], r["quarter_quota"])
                     for r in dataset["reps"]])
    con.executemany("INSERT INTO accounts VALUES (?,?,?)",
                    [(a["account_id"], a["account_name"], a["segment"])
                     for a in dataset["accounts"]])
    con.executemany("INSERT INTO opportunities VALUES (?,?,?,?,?,?)",
                    [(o["opp_id"], o["account_id"], o["rep_id"],
                      o["amount"], o["created_week"],
                      o["initial_close_week"])
                     for o in dataset["opportunities"]])
    con.executemany("INSERT INTO snapshots VALUES (?,?,?,?,?,?,?)",
                    [(s["snapshot_week"], s["opp_id"], s["rep_id"],
                      s["stage"], s["forecast_category"], s["amount"],
                      s["close_week"]) for s in dataset["snapshots"]])
    con.executemany("INSERT INTO outcomes VALUES (?,?,?,?,?,?)",
                    [(oc["opp_id"], oc["final_stage"],
                      oc["actual_close_week"], oc["closed_amount"],
                      oc["fate"], oc["final_close_week"])
                     for oc in dataset["outcomes"].values()])
    return con


def category_accuracy_sql(dataset: Dict, week: int = 8) -> Dict:
    con = connect(dataset)
    try:
        rows = con.execute(_load("category_accuracy.sql"),
                           {"week": week}).fetchall()
    finally:
        con.close()
    return {r[0]: {"deals": r[1], "forecast": r[2], "actual_won": r[3]}
            for r in rows}


def rep_bias_sql(dataset: Dict, week: int) -> Dict:
    con = connect(dataset)
    try:
        rows = con.execute(_load("rep_bias.sql"),
                           {"week": week}).fetchall()
    finally:
        con.close()
    out = {}
    for rid, fc, actual in rows:
        bias = round(fc - actual, 2)
        bias_pct = (round(100.0 * bias / actual, 4) if actual
                    else (100.0 if fc else 0.0))
        denom = max(fc, actual)
        out[rid] = {"rep_id": rid, "weighted_forecast": fc,
                    "actual": actual, "bias": bias, "bias_pct": bias_pct,
                    "bias_share": round(bias / denom, 4) if denom else 0.0}
    return out


def cohort_sql(dataset: Dict):
    con = connect(dataset)
    try:
        rows = con.execute(_load("cohort_conversion.sql")).fetchall()
    finally:
        con.close()
    return [{"created_week": r[0], "deals": r[1], "amount": r[2],
             "won": r[3], "won_amount": r[4]} for r in rows]


def pipeline_by_week_sql(dataset: Dict) -> Dict:
    con = connect(dataset)
    try:
        rows = con.execute(_load("pipeline_by_week.sql")).fetchall()
    finally:
        con.close()
    out: Dict = {}
    for week, cat, deals, amount in rows:
        out.setdefault(week, {})[cat] = {"deals": deals, "amount": amount}
    return out
