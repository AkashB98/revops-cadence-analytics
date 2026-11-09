"""Deterministic synthetic SaaS sales book — fictional reps/accounts.

SYNTHETIC DATA ONLY. No real company, rep, account, or pipeline data
is ever used. Every row is fabricated from a seeded PRNG so the same
seed always yields the same book, byte-for-byte.

Shape: 24 reps x 9 opportunities = 216 opportunities, 90 accounts,
and POINT-IN-TIME weekly pipeline snapshots over a 12-week quarter
(weeks 0..11). One snapshot row per opportunity per week from its
created week until it closes (or quarter end if it slips):

  snapshot_week, opp_id, rep_id, stage, forecast_category,
  amount, close_week (as believed that week)

Outcomes (quarter-end truth, used only to GRADE forecasts):
  opp_id -> final_stage, actual_close_week, closed_amount, fate

Planted patterns (pinned by tests and golden evals):
  * SANDBAGGER (R07) — downgrades every forecast category one level
    (Negotiation deals sit in best_case, Evaluation in pipeline) but
    every deal closes won: his week-8 forecast call badly
    UNDER-states what he delivers.
  * HAPPY EARS (R19) — upgrades every category one level so almost
    everything reads commit, but only 2 of his 9 deals close won:
    his week-8 call badly OVER-states delivery.
  * SLIPPED DEALS — deals whose believed close week pushes, week by
    week, out of the quarter (final close week >= 12), with a stage
    regression on the way out.
"""

from __future__ import annotations

import random
from typing import Dict, List

DEFAULT_SEED = 42
WEEKS = 12
REPS = 24
OPPS_PER_REP = 9

STAGES = ["Prospecting", "Qualification", "Discovery", "Evaluation",
          "Negotiation", "Closed Won", "Closed Lost"]
OPEN_STAGES = STAGES[:5]
STAGE_ORDER = {s: i for i, s in enumerate(OPEN_STAGES)}

CATEGORIES = ["commit", "best_case", "pipeline"]
CATEGORY_RANK = {"pipeline": 0, "best_case": 1, "commit": 2}
CATEGORY_WEIGHTS = {"commit": 1.0, "best_case": 0.5, "pipeline": 0.2}

SANDBAGGER_ID = "R07"
HAPPY_ID = "R19"
FORECAST_WEEK = 8  # week at which the per-rep bias "call" is taken

TEAMS = ["Enterprise", "Mid-Market", "Commercial"]
TERRITORIES = ["AMER-East", "AMER-Central", "AMER-West", "EMEA"]
TEAM_QUOTA = {"Enterprise": 320000, "Mid-Market": 260000,
              "Commercial": 190000}
TEAM_DEAL = {"Enterprise": (40000, 120000), "Mid-Market": (25000, 70000),
             "Commercial": (12000, 40000)}

_FIRST = ["Alex", "Priya", "Marcus", "Sofia", "James", "Anita", "David",
          "Lena", "Omar", "Grace", "Tom", "Nadia", "Chris", "Mei",
          "Raj", "Elena", "Sam", "Ivy", "Ben", "Kara", "Leo", "Maya",
          "Noah", "Tara"]
_LAST = ["Sharma", "Lee", "Garcia", "Kim", "Patel", "Novak", "Brooks",
         "Singh", "Ali", "Chen", "Murphy", "Ross", "Frost", "Diaz",
         "Park", "Reyes", "Holt", "Bose", "Ward", "Nair", "Fox",
         "Lind", "Ortiz", "Vale"]
_CO_A = ["NorthPeak", "BlueHarbor", "CedarWorks", "Silverline",
         "RedCanyon", "GoldenArc", "IronGate", "PalmLabs",
         "StoneBridge", "ClearSignal"]
_CO_B = ["Systems", "Health", "Foods Group", "Mobility", "Cloud",
         "Retail Co", "Energy", "Logistics", "Finance", "Media"]


def rep_rows() -> List[Dict]:
    rows = []
    for i in range(REPS):
        team = TEAMS[i % 3]
        rows.append({
            "rep_id": f"R{i + 1:02d}",
            "rep_name": f"{_FIRST[i]} {_LAST[i]}",
            "team": team,
            "territory": TERRITORIES[i % 4],
            "quarter_quota": TEAM_QUOTA[team] + (i % 4) * 5000,
        })
    return rows


def account_rows() -> List[Dict]:
    rows = []
    for i in range(90):
        rows.append({
            "account_id": f"ACC{i + 1:03d}",
            "account_name": (f"{_CO_A[i % 10]} {_CO_B[(i // 10) % 10]} "
                             f"{i + 1:02d}"),
            "segment": TEAMS[i % 3],
        })
    return rows


def _base_category(stage: str) -> str:
    if stage == "Negotiation":
        return "commit"
    if stage == "Evaluation":
        return "best_case"
    return "pipeline"


def _shift_category(cat: str, rep_id: str) -> str:
    if rep_id == SANDBAGGER_ID:
        return {"commit": "best_case", "best_case": "pipeline",
                "pipeline": "pipeline"}[cat]
    if rep_id == HAPPY_ID:
        return {"pipeline": "best_case", "best_case": "commit",
                "commit": "commit"}[cat]
    return cat


def _stage_at(fate: str, w: int, created: int, initial_close: int) -> str:
    """Open stage for snapshot week w (strictly before close)."""
    span = max(initial_close - created, 1)
    frac = (w - created) / span
    if fate == "won":
        idx = min(int(frac * 5), 4)
    elif fate == "lost":
        idx = min(int(frac * 3.2), 3)
    else:  # slipped_out: climbs fast to Negotiation by initial_close-3,
        # then REGRESSES one stage when the close week first pushes
        # (initial_close-2) and stalls there — exactly one planted
        # regression per slipped deal.
        if w >= initial_close - 2:
            idx = 3
        else:
            span2 = max(initial_close - 3 - created, 1)
            idx = min(int((w - created) / span2 * 5), 4)
    return OPEN_STAGES[idx]


def generate_dataset(seed: int = DEFAULT_SEED) -> Dict:
    rng = random.Random(seed)
    reps = rep_rows()
    accounts = account_rows()
    rep_team = {r["rep_id"]: r["team"] for r in reps}
    opps, snapshots, outcomes = [], [], {}
    slipped_ids: List[str] = []
    n = 0
    for rep in reps:
        rid = rep["rep_id"]
        lo, hi = TEAM_DEAL[rep_team[rid]]
        for j in range(OPPS_PER_REP):
            n += 1
            oid = f"OPP{n:03d}"
            amount = round(rng.uniform(lo, hi) / 100.0) * 100
            created = rng.randint(0, 4)
            initial_close = max(min(created + rng.randint(5, 7), 11),
                                created + 4)
            if rid == SANDBAGGER_ID:
                fate, final_close = "won", initial_close
            elif rid == HAPPY_ID:
                fate = ["lost", "slipped_out", "lost", "won",
                        "slipped_out", "lost", "slipped_out", "lost",
                        "won"][j]
                final_close = (initial_close if fate in ("lost", "won")
                               else 12 + (j % 3))
            else:
                roll = rng.random()
                if roll < 0.58:
                    fate, final_close = "won", initial_close
                elif roll < 0.83:
                    fate, final_close = "lost", initial_close
                else:
                    fate = "slipped_out"
                    final_close = 12 + rng.randint(0, 3)
            if fate == "slipped_out":
                slipped_ids.append(oid)
            account = accounts[rng.randrange(len(accounts))]
            opps.append({
                "opp_id": oid, "account_id": account["account_id"],
                "rep_id": rid, "amount": amount,
                "created_week": created,
                "initial_close_week": initial_close,
            })
            outcomes[oid] = {
                "opp_id": oid,
                "final_stage": ("Closed Won" if fate == "won" else
                                "Closed Lost" if fate == "lost" else "Open"),
                "actual_close_week": (final_close if fate != "slipped_out"
                                      else None),
                "closed_amount": amount if fate == "won" else 0,
                "fate": fate,
                "final_close_week": final_close,
            }
            last_week = 11 if fate == "slipped_out" else final_close
            for w in range(created, last_week + 1):
                if fate in ("won", "lost") and w == final_close:
                    stage = ("Closed Won" if fate == "won"
                             else "Closed Lost")
                    cat = _shift_category(_base_category("Negotiation"), rid)
                    close_believed = initial_close
                else:
                    stage = _stage_at(fate, w, created, initial_close)
                    cat = _shift_category(_base_category(stage), rid)
                    if fate == "slipped_out" and w > initial_close - 2:
                        close_believed = min(
                            initial_close + (w - (initial_close - 2)),
                            final_close)
                    else:
                        close_believed = initial_close
                snapshots.append({
                    "snapshot_week": w, "opp_id": oid, "rep_id": rid,
                    "stage": stage, "forecast_category": cat,
                    "amount": amount, "close_week": close_believed,
                })
    return {
        "seed": seed, "weeks": WEEKS, "quarter": "Q (weeks 0-11)",
        "reps": reps, "accounts": accounts, "opportunities": opps,
        "snapshots": snapshots, "outcomes": outcomes,
        "planted": {"sandbagger": SANDBAGGER_ID, "happy_ears": HAPPY_ID,
                    "slipped_opp_ids": sorted(slipped_ids)},
    }


def dataset_to_json(dataset: Dict) -> str:
    import json
    return json.dumps(dataset, sort_keys=True) + "\n"
