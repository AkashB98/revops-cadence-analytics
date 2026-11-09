"""Point-in-time forecasting, category accuracy, per-rep bias,
slippage tracking, and cohort funnel — the RevOps cadence core.

Metric definitions reuse forecast-accuracy-lab semantics:
  error = forecast - actual; bias = mean/sum signed error;
  bias_pct = 100 * (forecast - actual) / actual;
  accuracy-style percentage error = 100 * |forecast - actual| / actual
(the MAPE form applied to a single aggregate forecast).

POINT-IN-TIME RULE: forecast_at_week(dataset, w) reads ONLY snapshot
rows with snapshot_week == w plus outcomes whose actual close week
is <= w (knowable at w). Nothing from a later week can move it —
pinned by a poison test in tests and evals.
"""

from __future__ import annotations

from typing import Dict, List

from generator import (CATEGORY_WEIGHTS, FORECAST_WEEK, OPEN_STAGES,
                       STAGE_ORDER, WEEKS)

CLOSED = ("Closed Won", "Closed Lost")


def snapshots_at(dataset: Dict, week: int) -> List[Dict]:
    return [s for s in dataset["snapshots"] if s["snapshot_week"] == week]


def closed_won_to_date(dataset: Dict, week: int,
                       rep_id: str = None) -> float:
    total = 0.0
    opp_rep = {o["opp_id"]: o["rep_id"] for o in dataset["opportunities"]}
    for oid, oc in dataset["outcomes"].items():
        if oc["final_stage"] == "Closed Won" \
                and oc["actual_close_week"] is not None \
                and oc["actual_close_week"] <= week \
                and (rep_id is None or opp_rep[oid] == rep_id):
            total += oc["closed_amount"]
    return round(total, 2)


def quarter_actual(dataset: Dict) -> float:
    return round(sum(oc["closed_amount"]
                     for oc in dataset["outcomes"].values()
                     if oc["final_stage"] == "Closed Won"), 2)


def forecast_at_week(dataset: Dict, week: int) -> Dict:
    """The forecast call made at `week`, from that week's snapshot only.

    call = closed-won to date + commit + best_case (unweighted — the
    number a rep would say out loud on the forecast call);
    weighted = closed-won to date + category-weighted open pipeline.
    """
    rows = snapshots_at(dataset, week)
    open_rows = [s for s in rows if s["stage"] not in CLOSED]
    by_cat = {c: 0.0 for c in CATEGORY_WEIGHTS}
    for s in open_rows:
        by_cat[s["forecast_category"]] += s["amount"]
    closed = closed_won_to_date(dataset, week)
    weighted = closed + sum(by_cat[c] * CATEGORY_WEIGHTS[c]
                            for c in by_cat)
    call = closed + by_cat["commit"] + by_cat["best_case"]
    return {
        "week": week,
        "closed_won_to_date": closed,
        "open_by_category": {k: round(v, 2) for k, v in by_cat.items()},
        "open_pipeline": round(sum(by_cat.values()), 2),
        "call": round(call, 2),
        "weighted_forecast": round(weighted, 2),
        "open_deals": len(open_rows),
    }


def forecast_series(dataset: Dict) -> List[Dict]:
    return [forecast_at_week(dataset, w) for w in range(WEEKS)]


def forecast_accuracy(dataset: Dict) -> Dict:
    """Grade every week's call/weighted forecast vs quarter actual,
    using forecast-accuracy-lab error/bias definitions."""
    actual = quarter_actual(dataset)
    rows = []
    for f in forecast_series(dataset):
        err = round(f["weighted_forecast"] - actual, 2)
        pct = (round(100.0 * err / actual, 4) if actual else None)
        ape = (round(100.0 * abs(err) / actual, 4) if actual else None)
        rows.append({"week": f["week"],
                     "weighted_forecast": f["weighted_forecast"],
                     "call": f["call"], "actual": actual,
                     "bias": err, "bias_pct": pct, "ape_pct": ape})
    final = rows[-1]
    return {"actual": actual, "by_week": rows,
            "final_bias": final["bias"], "final_bias_pct": final["bias_pct"],
            "final_ape_pct": final["ape_pct"]}


def category_accuracy(dataset: Dict,
                      week: int = FORECAST_WEEK) -> Dict:
    """Accuracy BY forecast category, graded on the deals OPEN in
    the forecast week's snapshot, grouped by their category THAT
    week — the question the forecast call actually asks: "the deals
    you called commit in week 8: how much of that money landed?"

    commit hit rate = won amount / forecast amount in commit;
    best-case conversion = same ratio for best_case;
    pipeline discount = 1 - won/forecast for pipeline (how much of
    the raw pipeline number evaporates).
    """
    rows = [s for s in snapshots_at(dataset, week)
            if s["stage"] not in CLOSED]
    out = {}
    for cat in ("commit", "best_case", "pipeline"):
        ids = [s["opp_id"] for s in rows
               if s["forecast_category"] == cat]
        fc = sum(s["amount"] for s in rows
                 if s["forecast_category"] == cat)
        won_amt = sum(dataset["outcomes"][i]["closed_amount"] for i in ids)
        won_n = sum(1 for i in ids
                    if dataset["outcomes"][i]["final_stage"] == "Closed Won")
        hit = round(won_amt / fc, 4) if fc else 0.0
        entry = {"deals": len(ids), "forecast": round(fc, 2),
                 "actual_won": round(won_amt, 2),
                 "won_deals": won_n,
                 "hit_rate": hit, "bias": round(fc - won_amt, 2)}
        if cat == "commit":
            entry["commit_hit_rate"] = hit
        elif cat == "best_case":
            entry["best_case_conversion"] = hit
        else:
            entry["pipeline_discount"] = round(1.0 - hit, 4)
        out[cat] = entry
    return out


def rep_bias(dataset: Dict, week: int = FORECAST_WEEK) -> Dict:
    """Per-rep bias at the forecast week: the rep's WEIGHTED forecast
    (from that week's snapshot only) vs the rep's quarter actual.
      bias      = forecast - actual (forecast-accuracy-lab convention)
      bias_pct  = 100 * bias / actual
      bias_share = bias / max(forecast, actual) — bounded in (-1, 1),
                   so a rep with a tiny actual cannot explode the
                   ratio; the detector thresholds on this.
    bias < 0 = under-forecast (delivered more than forecast);
    bias > 0 = over-forecast."""
    opp_rep = {o["opp_id"]: o["rep_id"] for o in dataset["opportunities"]}
    rows = {}
    for rep in dataset["reps"]:
        rid = rep["rep_id"]
        snap = [s for s in snapshots_at(dataset, week)
                if s["rep_id"] == rid and s["stage"] not in CLOSED]
        by_cat = {c: 0.0 for c in CATEGORY_WEIGHTS}
        for s in snap:
            by_cat[s["forecast_category"]] += s["amount"]
        closed = closed_won_to_date(dataset, week, rep_id=rid)
        call = round(closed + by_cat["commit"] + by_cat["best_case"], 2)
        fc = round(closed + sum(by_cat[c] * CATEGORY_WEIGHTS[c]
                                for c in by_cat), 2)
        actual = round(sum(
            oc["closed_amount"] for oid, oc in dataset["outcomes"].items()
            if opp_rep[oid] == rid
            and oc["final_stage"] == "Closed Won"), 2)
        bias = round(fc - actual, 2)
        bias_pct = (round(100.0 * bias / actual, 4) if actual
                    else (100.0 if fc else 0.0))
        denom = max(fc, actual)
        bias_share = round(bias / denom, 4) if denom else 0.0
        rows[rid] = {"rep_id": rid, "call": call,
                     "weighted_forecast": fc, "actual": actual,
                     "bias": bias, "bias_pct": bias_pct,
                     "bias_share": bias_share,
                     "closed_won_to_date": closed,
                     "open_by_category": {k: round(v, 2)
                                          for k, v in by_cat.items()}}
    return rows


SANDBAG_THRESHOLD = -0.30   # bias_share at or below: sandbagging
HAPPY_THRESHOLD = 0.56      # bias_share at or above: happy ears
# On the seeded book the planted reps sit at -0.3661 / +0.6229 and
# the nearest normal reps at -0.1829 / +0.5168, so both thresholds
# sit inside genuine gaps, not on a knife edge (pinned by evals).


def detect_bias_outliers(dataset: Dict, week: int = FORECAST_WEEK) -> Dict:
    rows = rep_bias(dataset, week=week)
    sand = sorted(r for r, v in rows.items()
                  if v["bias_share"] <= SANDBAG_THRESHOLD)
    happy = sorted(r for r, v in rows.items()
                   if v["bias_share"] >= HAPPY_THRESHOLD)
    return {"sandbaggers": sand, "happy_ears": happy, "week": week,
            "thresholds": {"sandbag_max_bias_share": SANDBAG_THRESHOLD,
                           "happy_min_bias_share": HAPPY_THRESHOLD}}


def slippage(dataset: Dict) -> Dict:
    """Deals whose believed close week moved out of the quarter
    (final close week >= 12 while the initial close was in-quarter),
    plus stage regressions counted across consecutive snapshots."""
    opps = {o["opp_id"]: o for o in dataset["opportunities"]}
    slipped = []
    for o in dataset["opportunities"]:
        oc = dataset["outcomes"][o["opp_id"]]
        if oc["final_close_week"] >= WEEKS \
                and o["initial_close_week"] < WEEKS \
                and oc["fate"] == "slipped_out":
            slipped.append({"opp_id": o["opp_id"], "rep_id": o["rep_id"],
                            "amount": o["amount"],
                            "initial_close_week": o["initial_close_week"],
                            "final_close_week": oc["final_close_week"]})
    slipped.sort(key=lambda r: r["opp_id"])
    by_opp: Dict[str, List[Dict]] = {}
    for s in dataset["snapshots"]:
        by_opp.setdefault(s["opp_id"], []).append(s)
    regressions = []
    for oid, rows in sorted(by_opp.items()):
        rows = sorted(rows, key=lambda r: r["snapshot_week"])
        for a, b in zip(rows, rows[1:]):
            if a["stage"] in STAGE_ORDER and b["stage"] in STAGE_ORDER \
                    and STAGE_ORDER[b["stage"]] < STAGE_ORDER[a["stage"]]:
                regressions.append({"opp_id": oid, "week": b["snapshot_week"],
                                    "from_stage": a["stage"],
                                    "to_stage": b["stage"]})
    return {"slipped_deals": slipped,
            "slipped_count": len(slipped),
            "slipped_amount": round(sum(s["amount"] for s in slipped), 2),
            "stage_regressions": regressions,
            "stage_regression_count": len(regressions)}


def cadence_payload(dataset: Dict) -> Dict:
    """Weekly cadence view: one row per snapshot week."""
    slip = slippage(dataset)
    slipped_ids = {s["opp_id"] for s in slip["slipped_deals"]}
    rows = []
    for w in range(WEEKS):
        f = forecast_at_week(dataset, w)
        rows.append({
            "week": w, "open_deals": f["open_deals"],
            "open_pipeline": f["open_pipeline"],
            "commit": f["open_by_category"]["commit"],
            "best_case": f["open_by_category"]["best_case"],
            "pipeline": f["open_by_category"]["pipeline"],
            "closed_won_to_date": f["closed_won_to_date"],
            "weighted_forecast": f["weighted_forecast"],
            "slipped_open": sum(1 for s in snapshots_at(dataset, w)
                                if s["opp_id"] in slipped_ids
                                and s["stage"] not in CLOSED),
            "regressions_this_week": sum(
                1 for r in slip["stage_regressions"] if r["week"] == w),
        })
    return {"weeks": rows, "slippage": slip}


def funnel_cohort(dataset: Dict) -> Dict:
    """COHORT funnel: group deals by created week; conversion is
    measured on the whole cohort (won / created), never on the deals
    that merely happened to be visible in one snapshot."""
    cohorts = {}
    for o in dataset["opportunities"]:
        c = cohorts.setdefault(o["created_week"],
                               {"created_week": o["created_week"],
                                "deals": 0, "amount": 0.0, "won": 0,
                                "won_amount": 0.0, "lost": 0, "slipped": 0})
        oc = dataset["outcomes"][o["opp_id"]]
        c["deals"] += 1
        c["amount"] += o["amount"]
        if oc["final_stage"] == "Closed Won":
            c["won"] += 1
            c["won_amount"] += oc["closed_amount"]
        elif oc["final_stage"] == "Closed Lost":
            c["lost"] += 1
        else:
            c["slipped"] += 1
    rows = []
    for w in sorted(cohorts):
        c = cohorts[w]
        rows.append({**c, "amount": round(c["amount"], 2),
                     "won_amount": round(c["won_amount"], 2),
                     "conversion": round(c["won"] / c["deals"], 4)
                     if c["deals"] else 0.0,
                     "amount_conversion": round(c["won_amount"] / c["amount"], 4)
                     if c["amount"] else 0.0})
    total_deals = sum(r["deals"] for r in rows)
    total_won = sum(r["won"] for r in rows)
    return {"cohorts": rows,
            "overall_conversion": round(total_won / total_deals, 4)
            if total_deals else 0.0}


def funnel_snapshot_method(dataset: Dict, week: int = FORECAST_WEEK) -> Dict:
    """The snapshot shortcut: win rate estimated from deals ALREADY
    closed by `week` (closed won / all closed). Open and slipped
    deals are invisible to it, so it overstates conversion — the gap
    vs the cohort method is the survivorship error, computed not
    asserted."""
    won = lost = 0
    for oc in dataset["outcomes"].values():
        if oc["actual_close_week"] is not None \
                and oc["actual_close_week"] <= week:
            if oc["final_stage"] == "Closed Won":
                won += 1
            elif oc["final_stage"] == "Closed Lost":
                lost += 1
    closed = won + lost
    return {"week": week, "closed_won": won, "closed_lost": lost,
            "snapshot_win_rate": round(won / closed, 4) if closed else 0.0}


def funnel_comparison(dataset: Dict) -> Dict:
    cohort = funnel_cohort(dataset)
    snap = funnel_snapshot_method(dataset)
    gap = round(snap["snapshot_win_rate"] - cohort["overall_conversion"], 4)
    return {"cohort_overall_conversion": cohort["overall_conversion"],
            "snapshot_win_rate": snap["snapshot_win_rate"],
            "gap_points": gap,
            "snapshot_detail": snap, "cohort": cohort}
