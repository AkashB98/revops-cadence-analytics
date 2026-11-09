"""Golden evals for revops-cadence-analytics.

SYNTHETIC DATA ONLY (fictional reps and deals). Every eval is
deterministic: run_evals.py writes eval_report.json and the file
must be byte-identical across runs. No timestamps, ports, or temp
paths enter the report — only names, booleans, pinned counts and
values.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import sys
import threading
import urllib.request
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capacity import capacity_plan, quota_attainment  # noqa: E402
from cli import (EXIT_ERROR, EXIT_FAIL, EXIT_OK, load_dataset,  # noqa: E402
                 main as cli_main, make_server, reset_state)
from forecast import (category_accuracy, detect_bias_outliers,  # noqa: E402
                      forecast_at_week, funnel_comparison, rep_bias,
                      slippage)
from generator import dataset_to_json, generate_dataset  # noqa: E402
from metrics_sql import (category_accuracy_sql, cohort_sql,  # noqa: E402
                         pipeline_by_week_sql, rep_bias_sql)
from report import build_forecast_call_md  # noqa: E402
from validation import validate_dataset  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURE = os.path.join(ROOT, "fixtures", "sample_book.json")
RESULTS = []


def check(name, passed, detail=""):
    RESULTS.append({"name": name, "passed": bool(passed), "detail": detail})
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return passed


def _run_cli(argv):
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return cli_main(argv)


def main():
    print("== golden evals: revops-cadence-analytics ==")
    data = generate_dataset()

    # E1: generator determinism (bytes pinned)
    text1 = dataset_to_json(generate_dataset())
    text2 = dataset_to_json(generate_dataset())
    md5 = hashlib.md5(text1.encode()).hexdigest()
    check("E1 generator determinism (seed=42, 24 reps x 9 deals)",
          text1 == text2 and len(data["snapshots"]) == 1647
          and md5 == "a4e29535872814bada5cc252bda68116",
          f"dataset_md5={md5}")

    # E2: validation clean on the seeded book; a tampered row trips it.
    tampered = copy.deepcopy(data)
    tampered["snapshots"][10]["forecast_category"] = "sure_thing"
    check("E2 validation clean (tampered category trips it)",
          validate_dataset(data) == []
          and len(validate_dataset(tampered)) > 0)

    # E3: leakage guard — poisoning every later week changes the
    # week-8 point-in-time forecast by nothing.
    base = forecast_at_week(data, 8)
    poisoned = copy.deepcopy(data)
    for s in poisoned["snapshots"]:
        if s["snapshot_week"] > 8:
            s["amount"] *= 100
            s["forecast_category"] = "commit"
    for oc in poisoned["outcomes"].values():
        if oc["actual_close_week"] is not None \
                and oc["actual_close_week"] > 8:
            oc["closed_amount"] *= 100
    check("E3 leakage guard (week-8 forecast poison-proof)",
          forecast_at_week(poisoned, 8) == base
          and base["weighted_forecast"] == 6802180.0,
          f"week8_weighted={base['weighted_forecast']}")

    # E4: category accuracy pinned (week-8 snapshot grading).
    acc = category_accuracy(data)
    check("E4 category accuracy pinned (commit 0.8022, best 0.3322, "
          "pipeline discount 0.7418)",
          acc["commit"]["hit_rate"] == 0.8022
          and acc["commit"]["forecast"] == 1621000
          and acc["best_case"]["best_case_conversion"] == 0.3322
          and acc["pipeline"]["pipeline_discount"] == 0.7418,
          f"commit_hit={acc['commit']['hit_rate']}")

    # E5: bias detector finds EXACTLY the planted reps, shares pinned.
    det = detect_bias_outliers(data)
    rb = rep_bias(data)
    check("E5 detector finds exactly R07 + R19 (shares -0.3661/+0.6229)",
          det["sandbaggers"] == ["R07"] and det["happy_ears"] == ["R19"]
          and rb["R07"]["bias_share"] == -0.3661
          and rb["R19"]["bias_share"] == 0.6229,
          f"sand={det['sandbaggers']} happy={det['happy_ears']}")

    # E6: slippage pinned — 46 deals out of quarter, one planted
    # stage regression per slipped deal.
    slip = slippage(data)
    check("E6 slippage pinned (46 deals, $2,205,200, 46 regressions)",
          slip["slipped_count"] == 46
          and slip["slipped_amount"] == 2205200
          and slip["stage_regression_count"] == 46
          and [s["opp_id"] for s in slip["slipped_deals"]]
          == data["planted"]["slipped_opp_ids"],
          f"slipped={slip['slipped_count']}")

    # E7: funnel gap pinned — snapshot method overstates conversion.
    fun = funnel_comparison(data)
    check("E7 funnel gap pinned (cohort 0.5602 vs snapshot 0.7416)",
          fun["cohort_overall_conversion"] == 0.5602
          and fun["snapshot_win_rate"] == 0.7416
          and fun["gap_points"] == 0.1814,
          f"gap={fun['gap_points']}")

    # E8: SQL == Python on all four shared metrics.
    cas = category_accuracy_sql(data, week=8)
    rbs = rep_bias_sql(data, week=8)
    coh_py = funnel_comparison(data)["cohort"]["cohorts"]
    coh_sql = cohort_sql(data)
    pw = pipeline_by_week_sql(data)
    sql_ok = all(cas[c]["forecast"] == acc[c]["forecast"]
                 and cas[c]["actual_won"] == acc[c]["actual_won"]
                 for c in ("commit", "best_case", "pipeline")) \
        and all(rbs[r]["bias_share"] == rb[r]["bias_share"] for r in rb) \
        and all(a["won"] == b["won"] and a["won_amount"] == b["won_amount"]
                for a, b in zip(coh_py, coh_sql)) \
        and pw[8]["commit"]["amount"] == acc["commit"]["forecast"]
    check("E8 SQL metrics == Python (category, rep bias, cohort, "
          "pipeline-by-week)", sql_ok)

    # E9: capacity + attainment pinned.
    plan = capacity_plan(data)
    att = quota_attainment(data)
    check("E9 capacity pinned (gap $298,400, 2 reps) + attainment",
          plan["quota_total"] == 6340000 and plan["quota_gap"] == 298400
          and plan["reps_needed"] == 2
          and att["buckets"] == {"<50%": 4, "50-80%": 6, "80-100%": 6,
                                 "100-120%": 4, ">120%": 4},
          f"reps_needed={plan['reps_needed']}")

    # E10: CLI check exit codes 0 / 1 / 2.
    import tempfile
    tmp = tempfile.mkdtemp(prefix="revops-evals-")
    good_path = os.path.join(tmp, "book.json")
    with open(good_path, "w", encoding="utf-8") as fh:
        fh.write(dataset_to_json(data))
    codes = (_run_cli(["check", "--input", good_path]),
             _run_cli(["check", "--input", good_path,
                       "--min-commit-hit", "0.999"]),
             _run_cli(["check", "--input", "/tmp/no-such-book-xyz.json"]))
    check("E10 CLI check exit codes 0/1/2",
          codes == (EXIT_OK, EXIT_FAIL, EXIT_ERROR), f"codes={codes}")

    # E11: serve round-trip matches local computation.
    reset_state(data)
    server = make_server(0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health",
                                    timeout=10) as resp:
            health = json.loads(resp.read())
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/forecast",
            data=json.dumps({"week": 8}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            served_fc = json.loads(resp.read())
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/report",
                                    timeout=10) as resp:
            served_report = resp.read().decode()
        serve_ok = health == {"status": "ok"} \
            and served_fc == base \
            and served_report == build_forecast_call_md(data)
    finally:
        server.shutdown()
        server.server_close()
        reset_state()
    check("E11 serve round-trip matches local forecast + memo", serve_ok)

    # E12: fixture pinned + memo determinism.
    fixture = load_dataset(FIXTURE)
    md1 = build_forecast_call_md(data)
    md2 = build_forecast_call_md(generate_dataset())
    check("E12 fixture pinned (216 deals, validates clean) + memo "
          "determinism",
          fixture == data and len(fixture["opportunities"]) == 216
          and validate_dataset(fixture) == [] and md1 == md2,
          f"memo_md5={hashlib.md5(md1.encode()).hexdigest()}")

    passed = sum(1 for r in RESULTS if r["passed"])
    total_count = len(RESULTS)
    summary_doc = {"passed": passed, "total": total_count,
                   "all_passed": passed == total_count, "evals": RESULTS}
    with open(os.path.join(HERE, "eval_report.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(summary_doc, sort_keys=True) + "\n")
    print(f"\n{passed}/{total_count} evals passed -> evals/eval_report.json")
    return 0 if passed == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
