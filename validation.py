"""Data-quality gate. Reports issues, never raises on bad data, so
the CLI ``check`` gate maps data problems to exit code 2, distinctly
from a forecast-quality breach (exit 1)."""

from __future__ import annotations

from typing import Dict, List

from generator import CATEGORIES, STAGES, WEEKS

SNAPSHOT_FIELDS = ["snapshot_week", "opp_id", "rep_id", "stage",
                   "forecast_category", "amount", "close_week"]
OPP_FIELDS = ["opp_id", "account_id", "rep_id", "amount",
              "created_week", "initial_close_week"]


def validate_dataset(dataset: Dict) -> List[str]:
    issues: List[str] = []
    if not isinstance(dataset, dict):
        return ["dataset must be a JSON object"]
    reps = dataset.get("reps")
    if not isinstance(reps, list) or not reps:
        return ["dataset.reps missing or empty"]
    opps = dataset.get("opportunities")
    if not isinstance(opps, list) or not opps:
        return ["dataset.opportunities missing or empty"]
    snaps = dataset.get("snapshots")
    if not isinstance(snaps, list) or not snaps:
        return ["dataset.snapshots missing or empty"]
    outcomes = dataset.get("outcomes")
    if not isinstance(outcomes, dict) or not outcomes:
        return ["dataset.outcomes missing or empty"]
    rep_ids = {r.get("rep_id") for r in reps if isinstance(r, dict)}
    opp_ids = set()
    for o in opps:
        if not isinstance(o, dict):
            issues.append("opportunity row is not an object")
            continue
        for f in OPP_FIELDS:
            if f not in o:
                issues.append(f"opportunity missing field {f}: {o!r:.60}")
        oid = o.get("opp_id")
        if oid in opp_ids:
            issues.append(f"duplicate opp_id: {oid}")
        opp_ids.add(oid)
        if o.get("rep_id") not in rep_ids:
            issues.append(f"{oid}: unknown rep_id {o.get('rep_id')}")
        amt = o.get("amount")
        if not isinstance(amt, (int, float)) or isinstance(amt, bool) \
                or amt <= 0:
            issues.append(f"{oid}: amount must be positive, got {amt!r}")
        cw, iw = o.get("created_week"), o.get("initial_close_week")
        if not isinstance(cw, int) or not (0 <= cw < WEEKS):
            issues.append(f"{oid}: created_week out of range: {cw!r}")
        if not isinstance(iw, int) or not (0 <= iw < WEEKS):
            issues.append(f"{oid}: initial_close_week out of range: {iw!r}")
        if oid not in outcomes:
            issues.append(f"{oid}: missing outcome row")
    seen = set()
    for s in snaps:
        if not isinstance(s, dict):
            issues.append("snapshot row is not an object")
            continue
        for f in SNAPSHOT_FIELDS:
            if f not in s:
                issues.append(f"snapshot missing field {f}: {s!r:.60}")
        key = (s.get("opp_id"), s.get("snapshot_week"))
        if key in seen:
            issues.append(f"duplicate snapshot: {key}")
        seen.add(key)
        if s.get("opp_id") not in opp_ids:
            issues.append(f"snapshot for unknown opp: {s.get('opp_id')}")
        if s.get("stage") not in STAGES:
            issues.append(f"snapshot bad stage: {s.get('stage')!r}")
        if s.get("forecast_category") not in CATEGORIES:
            issues.append(
                f"snapshot bad category: {s.get('forecast_category')!r}")
        w = s.get("snapshot_week")
        if not isinstance(w, int) or not (0 <= w < WEEKS):
            issues.append(f"snapshot week out of range: {w!r}")
    return issues
