"""End-to-end demo: generate -> validate -> cadence -> forecast
(point-in-time, leakage-poisoned) -> category accuracy -> rep-bias
detection -> slippage -> cohort funnel -> capacity -> forecast-call
memo -> check -> serve.

SYNTHETIC DATA ONLY (fictional reps and deals). Runs fully offline;
the serve round-trip is loopback-only on an ephemeral port.
Every stage asserts.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import threading
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capacity import capacity_plan, quota_attainment  # noqa: E402
from cli import EXIT_FAIL, EXIT_OK, main as cli_main, make_server, reset_state  # noqa: E402
from forecast import (category_accuracy, detect_bias_outliers,  # noqa: E402
                      forecast_at_week, funnel_comparison, quarter_actual,
                      slippage)
from generator import dataset_to_json, generate_dataset  # noqa: E402
from report import build_forecast_call_md  # noqa: E402
from validation import validate_dataset  # noqa: E402


def _request(port: int, path: str, payload=None, method: str = "GET"):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read()


def main() -> None:
    print("== 1. generate synthetic sales book (seed=42, 24 reps x 9) ==")
    data = generate_dataset()
    assert data == generate_dataset(), "generator must be deterministic"
    assert len(data["reps"]) == 24 and len(data["opportunities"]) == 216
    assert validate_dataset(data) == [], validate_dataset(data)[:3]
    print(f"   216 deals, {len(data['snapshots'])} weekly snapshots, "
          "validation clean")

    print("\n== 2. point-in-time forecast + leakage poison test ==")
    f8 = forecast_at_week(data, 8)
    poisoned = copy.deepcopy(data)
    for s in poisoned["snapshots"]:
        if s["snapshot_week"] > 8:
            s["amount"] *= 100
            s["forecast_category"] = "commit"
    for oid, oc in poisoned["outcomes"].items():
        if oc["actual_close_week"] is not None and oc["actual_close_week"] > 8:
            oc["closed_amount"] *= 100
    assert forecast_at_week(poisoned, 8) == f8, \
        "later-week data leaked into the week-8 forecast"
    print(f"   week-8 weighted forecast ${f8['weighted_forecast']:,.2f}; "
          "poisoning weeks 9-11 changed nothing")

    print("\n== 3. category accuracy + rep-bias detection (planted) ==")
    acc = category_accuracy(data)
    det = detect_bias_outliers(data)
    print(f"   commit hit {acc['commit']['hit_rate']} · best-case "
          f"conversion {acc['best_case']['hit_rate']} · pipeline "
          f"discount {acc['pipeline']['pipeline_discount']}")
    print(f"   SANDBAGGER detected: {det['sandbaggers']} · "
          f"HAPPY-EARS detected: {det['happy_ears']}")
    assert det["sandbaggers"] == ["R07"], det
    assert det["happy_ears"] == ["R19"], det

    print("\n== 4. slippage + funnel (cohort vs snapshot) ==")
    slip = slippage(data)
    fun = funnel_comparison(data)
    print(f"   slipped out of quarter: {slip['slipped_count']} deals "
          f"(${slip['slipped_amount']:,.2f}); stage regressions: "
          f"{slip['stage_regression_count']}")
    print(f"   cohort conversion {fun['cohort_overall_conversion']} vs "
          f"snapshot method {fun['snapshot_win_rate']} "
          f"(gap {fun['gap_points']:+.4f})")
    assert slip["slipped_count"] == len(data["planted"]["slipped_opp_ids"])

    print("\n== 5. capacity (one formula) + attainment ==")
    plan = capacity_plan(data)
    att = quota_attainment(data)
    print(f"   quota ${plan['quota_total']:,.2f} · gap "
          f"${plan['quota_gap']:,.2f} · reps needed "
          f"{plan['reps_needed']} · attainment buckets {att['buckets']}")

    print("\n== 6. weekly forecast call memo ==")
    md = build_forecast_call_md(data)
    assert md == build_forecast_call_md(generate_dataset())
    assert "Weekly forecast call" in md and "R07" in md
    print("   " + md.splitlines()[2])

    print("\n== 7. CLI check gate exit codes ==")
    import tempfile
    tmp = tempfile.mkdtemp(prefix="revops-demo-")
    good_path = os.path.join(tmp, "book.json")
    with open(good_path, "w", encoding="utf-8") as fh:
        fh.write(dataset_to_json(data))
    code_ok = cli_main(["check", "--input", good_path])
    code_breach = cli_main(["check", "--input", good_path,
                            "--min-commit-hit", "0.999"])
    code_err = cli_main(["check", "--input", "/tmp/no-such-book-xyz.json"])
    print(f"   normal={code_ok} impossible-floor={code_breach} "
          f"missing-file={code_err}")
    assert code_ok == EXIT_OK and code_breach == EXIT_FAIL and code_err == 2

    print("\n== 8. live localhost serve round-trip ==")
    reset_state(data)
    server = make_server(0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _request(port, "/health")
        assert status == 200 and json.loads(body) == {"status": "ok"}
        status, body = _request(port, "/forecast",
                                payload={"week": 8}, method="POST")
        assert status == 200 and json.loads(body) == f8
        status, body = _request(port, "/report")
        assert status == 200 and body.decode() == md
        print("   POST /forecast matches local computation; "
              "GET /report matches the local memo")
    finally:
        server.shutdown()
        server.server_close()
        reset_state()

    print(f"\nDemo OK: quarter actual ${quarter_actual(data):,.2f}; "
          "generate, leakage guard, accuracy, bias detection, "
          "slippage, funnel, capacity, memo, check and serve verified.")


if __name__ == "__main__":
    main()
