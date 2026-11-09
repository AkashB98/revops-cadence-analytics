"""The deliverable: weekly_forecast_call.md — the memo for the
Monday forecast call, copied deterministically from the computed
numbers (same dataset, same memo, word for word)."""

from __future__ import annotations

from typing import Dict

from capacity import capacity_plan, quota_attainment, sensitivity_table
from forecast import (category_accuracy, detect_bias_outliers,
                      forecast_accuracy, funnel_comparison,
                      quarter_actual, slippage)
from generator import FORECAST_WEEK as FW


def build_forecast_call_md(dataset: Dict) -> str:
    acc = category_accuracy(dataset)
    det = detect_bias_outliers(dataset)
    slip = slippage(dataset)
    att = quota_attainment(dataset)
    fun = funnel_comparison(dataset)
    fa = forecast_accuracy(dataset)
    plan = capacity_plan(dataset)
    sens = sensitivity_table(plan["quota_gap"])
    reps = {r["rep_id"]: r for r in dataset["reps"]}
    lines = [
        "# Weekly forecast call — RevOps cadence memo",
        "",
        f"Quarter actual (closed won): **${fa['actual']:,.2f}** · "
        f"Final-week weighted forecast bias: **{fa['final_bias_pct']:+.2f}%** "
        f"(APE {fa['final_ape_pct']:.2f}%).",
        "",
        "## Forecast accuracy by category (week-8 snapshot, deals open then)",
        "",
        "| Category | Deals | Forecast | Won | Hit rate | Bias |",
        "|---|---|---|---|---|---|",
    ]
    for cat in ("commit", "best_case", "pipeline"):
        a = acc[cat]
        lines.append(
            f"| {cat} | {a['deals']} | ${a['forecast']:,.2f} | "
            f"${a['actual_won']:,.2f} | {a['hit_rate']:.4f} | "
            f"${a['bias']:,.2f} |")
    lines += [
        "",
        f"Commit hit rate **{acc['commit']['hit_rate']:.4f}** · "
        f"best-case conversion **{acc['best_case']['hit_rate']:.4f}** · "
        f"pipeline discount **{acc['pipeline']['pipeline_discount']:.4f}** "
        "(share of raw pipeline that evaporates).",
        "",
        "## Rep bias flags (week-8 call vs quarter actual)",
        "",
    ]
    for rid in det["sandbaggers"]:
        lines.append(f"- **{rid}** ({reps[rid]['rep_name']}, "
                     f"{reps[rid]['team']}) — SANDBAGGING signal: "
                     "delivered far above the call; raise the commit.")
    for rid in det["happy_ears"]:
        lines.append(f"- **{rid}** ({reps[rid]['rep_name']}, "
                     f"{reps[rid]['team']}) — HAPPY-EARS signal: "
                     "called far above delivery; inspect deal by deal.")
    if not det["sandbaggers"] and not det["happy_ears"]:
        lines.append("- No bias outliers this week.")
    lines += [
        "",
        "## Slippage & stage regressions",
        "",
        f"{slip['slipped_count']} deals slipped out of the quarter "
        f"(${slip['slipped_amount']:,.2f}); "
        f"{slip['stage_regression_count']} stage regressions.",
        "",
        "| Deal | Rep | Amount | Close was | Slips to |",
        "|---|---|---|---|---|",
    ]
    for s in slip["slipped_deals"]:
        lines.append(f"| {s['opp_id']} | {s['rep_id']} | "
                     f"${s['amount']:,.2f} | week {s['initial_close_week']} "
                     f"| week {s['final_close_week']} |")
    lines += [
        "",
        "## Funnel: cohort vs snapshot method",
        "",
        f"Cohort conversion (by created week, whole cohorts): "
        f"**{fun['cohort_overall_conversion']:.4f}**. Snapshot method "
        f"(win rate among deals already closed by week {FW}): "
        f"**{fun['snapshot_win_rate']:.4f}**. The snapshot method is "
        f"**{fun['gap_points']:+.4f}** off — it cannot see open or "
        "slipped deals, so it flatters the funnel.",
        "",
        "## Capacity (one formula)",
        "",
        f"Quota total ${plan['quota_total']:,.2f} · gap "
        f"${plan['quota_gap']:,.2f} · win rate {plan['win_rate']} · "
        f"ramped-rep productivity ${plan['ramped_rep_productivity']:,.2f} "
        f"→ pipeline needed ${plan['pipeline_needed']:,.2f} → "
        f"**{plan['reps_needed']} reps needed** "
        f"(`{plan['formula']}`).",
        "",
        "| Win rate \\ Productivity | "
        + " | ".join(f"${p:,}" for p in (400000, 500000, 600000, 750000))
        + " |",
        "|---|---|---|---|---|",
    ]
    for row in sens:
        lines.append(f"| {row['win_rate']} | " + " | ".join(
            str(row[str(p)]) for p in (400000, 500000, 600000, 750000))
            + " |")
    lines += [
        "",
        "## Quota attainment distribution",
        "",
        "| Bucket | Reps |",
        "|---|---|",
    ]
    for b, n in att["buckets"].items():
        lines.append(f"| {b} | {n} |")
    lines.append("")
    return "\n".join(lines)


def report_payload(dataset: Dict) -> Dict:
    return {
        "category_accuracy": category_accuracy(dataset),
        "forecast_accuracy": forecast_accuracy(dataset),
        "bias_outliers": detect_bias_outliers(dataset),
        "slippage": slippage(dataset),
        "funnel": funnel_comparison(dataset),
        "capacity": capacity_plan(dataset),
        "attainment_buckets": quota_attainment(dataset)["buckets"],
        "quarter_actual": quarter_actual(dataset),
    }
