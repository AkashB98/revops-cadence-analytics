"""CLI: generate | cadence | forecast | capacity | report |
check | demo | serve.

SYNTHETIC DATA ONLY — every rep, account and deal is fictional.

Exit codes:
  check : 0 = pass, 1 = forecast-quality breach (commit hit rate
          below --min-commit-hit or final-week APE above --max-ape),
          2 = usage / IO / data-quality error
  others: 0 = success, 2 = usage / IO error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capacity import capacity_plan, quota_attainment, sensitivity_table  # noqa: E402
from forecast import (cadence_payload, category_accuracy,  # noqa: E402
                      detect_bias_outliers, forecast_accuracy,
                      forecast_at_week, funnel_comparison, rep_bias)
from generator import generate_dataset, dataset_to_json  # noqa: E402
from report import build_forecast_call_md, report_payload  # noqa: E402
from validation import validate_dataset  # noqa: E402

EXIT_OK, EXIT_FAIL, EXIT_ERROR = 0, 1, 2
DEFAULT_MIN_COMMIT_HIT = 0.5
DEFAULT_MAX_APE = 35.0


def canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True)


def load_dataset(path: str) -> Dict:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("dataset file must contain a JSON object")
    return data


def _load_or_error(path: str) -> Optional[Dict]:
    try:
        return load_dataset(path)
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
    except (ValueError, OSError) as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
    return None


def _validated(args):
    data = _load_or_error(args.input)
    if data is None:
        return None, EXIT_ERROR
    issues = validate_dataset(data)
    if issues:
        for issue in issues[:20]:
            print(f"data-quality: {issue}", file=sys.stderr)
        return None, EXIT_ERROR
    return data, EXIT_OK


def _write_out(args, text: str, summary: str) -> int:
    if getattr(args, "out", None):
        try:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            print(f"error: cannot write {args.out}: {exc}", file=sys.stderr)
            return EXIT_ERROR
        print(summary)
    else:
        print(text, end="")
    return EXIT_OK


def cmd_generate(args) -> int:
    data = generate_dataset(seed=args.seed)
    return _write_out(args, dataset_to_json(data),
                      f"generated synthetic sales book: 24 reps x 9 deals, "
                      f"12 weekly snapshots (seed={args.seed}) "
                      f"-> {args.out}")


def cmd_cadence(args) -> int:
    data, code = _validated(args)
    if data is None:
        return code
    return _write_out(args, canonical(cadence_payload(data)) + "\n",
                      f"cadence -> {args.out}")


def cmd_forecast(args) -> int:
    data, code = _validated(args)
    if data is None:
        return code
    if args.week is not None:
        payload = forecast_at_week(data, args.week)
    else:
        payload = {"accuracy": forecast_accuracy(data),
                   "category_accuracy": category_accuracy(data),
                   "rep_bias": rep_bias(data),
                   "bias_outliers": detect_bias_outliers(data),
                   "funnel": funnel_comparison(data)}
    return _write_out(args, canonical(payload) + "\n",
                      f"forecast -> {args.out}")


def cmd_capacity(args) -> int:
    data, code = _validated(args)
    if data is None:
        return code
    plan = capacity_plan(data, win_rate=args.win_rate,
                         productivity=args.productivity)
    payload = {"plan": plan,
               "sensitivity": sensitivity_table(plan["quota_gap"]),
               "attainment": quota_attainment(data)}
    return _write_out(args, canonical(payload) + "\n",
                      f"capacity -> {args.out}")


def cmd_report(args) -> int:
    data, code = _validated(args)
    if data is None:
        return code
    return _write_out(args, build_forecast_call_md(data),
                      f"report -> {args.out}")


def cmd_check(args) -> int:
    data = _load_or_error(args.input)
    if data is None:
        return EXIT_ERROR
    issues = validate_dataset(data)
    if issues:
        for issue in issues[:20]:
            print(f"data-quality: {issue}")
        print(f"check FAIL (data quality): {len(issues)} issue(s)")
        return EXIT_ERROR
    acc = category_accuracy(data)
    fa = forecast_accuracy(data)
    hit = acc["commit"]["hit_rate"]
    ape = fa["final_ape_pct"]
    print(f"reps=24 deals={len(data['opportunities'])} "
          f"commit_hit={hit} final_ape={ape} "
          f"min_commit_hit={args.min_commit_hit} max_ape={args.max_ape}")
    if hit < args.min_commit_hit or (ape is not None and ape > args.max_ape):
        print(f"check FAIL: forecast quality below floor "
              f"(commit hit {hit} / final APE {ape})")
        return EXIT_FAIL
    print("check PASS")
    return EXIT_OK


def cmd_demo(args) -> int:
    import demo as demo_mod
    try:
        demo_mod.main()
    except AssertionError as exc:
        print(f"demo FAILED: {exc}", file=sys.stderr)
        return EXIT_FAIL
    return EXIT_OK


# ------------------------------------------------------------------- serve

class _State:
    def __init__(self):
        self.data: Dict = generate_dataset()


_STATE = _State()


def get_state() -> _State:
    return _STATE


def reset_state(data: Optional[Dict] = None) -> None:
    _STATE.data = data if data is not None else generate_dataset()


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, payload: Any) -> None:
        self._send(code, (canonical(payload) + "\n").encode(),
                   "application/json")

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            return self._send_json(200, {"status": "ok"})
        if self.path == "/report":
            return self._send(200, build_forecast_call_md(
                _STATE.data).encode(), "text/markdown; charset=utf-8")
        return self._send_json(404, {"error": "unknown endpoint"})

    def do_POST(self):  # noqa: N802
        if self.path != "/forecast":
            return self._send_json(404, {"error": "unknown endpoint"})
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            raw = self.rfile.read(length) if length else b""
            body = json.loads(raw) if raw.strip() else {}
            if not isinstance(body, dict):
                raise ValueError("body must be a JSON object")
            data = _STATE.data
            if "dataset" in body:
                candidate = body["dataset"]
                issues = validate_dataset(candidate)
                if issues:
                    return self._send_json(
                        400, {"error": f"data quality: {issues[0]}"})
                data = candidate
                _STATE.data = candidate
            week = int(body.get("week", 8))
            if not (0 <= week < 12):
                raise ValueError("week must be 0..11")
            return self._send_json(200, forecast_at_week(data, week))
        except (ValueError, TypeError, KeyError) as exc:
            return self._send_json(400, {"error": f"bad request: {exc}"})

    def log_message(self, *a: Any) -> None:
        pass


def make_server(port: int) -> HTTPServer:
    return HTTPServer(("127.0.0.1", port), _Handler)


def cmd_serve(args) -> int:
    if args.input:
        data = _load_or_error(args.input)
        if data is None:
            return EXIT_ERROR
        reset_state(data)
    server = make_server(args.port)
    print(f"serving on http://127.0.0.1:{args.port}  "
          f"(POST /forecast, GET /report, GET /health)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="revops-cadence-analytics",
        description="RevOps weekly forecast cadence: point-in-time "
                    "snapshots, category accuracy, rep bias, slippage, "
                    "cohort funnel, capacity.")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate the synthetic sales book")
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--out", default=None)
    g.set_defaults(func=cmd_generate)

    for name, func, helptext in [
            ("cadence", cmd_cadence, "weekly snapshot cadence + slippage"),
            ("forecast", cmd_forecast, "forecast accuracy + bias + funnel"),
            ("capacity", cmd_capacity, "capacity plan + sensitivity"),
            ("report", cmd_report, "weekly_forecast_call.md memo")]:
        s = sub.add_parser(name, help=helptext)
        s.add_argument("--input", required=True)
        s.add_argument("--out", default=None)
        if name == "forecast":
            s.add_argument("--week", type=int, default=None)
        if name == "capacity":
            s.add_argument("--win-rate", type=float, default=0.30)
            s.add_argument("--productivity", type=float, default=600000.0)
        s.set_defaults(func=func)

    c = sub.add_parser("check", help="CI gate: exit 0 pass / 1 breach / 2 error")
    c.add_argument("--input", required=True)
    c.add_argument("--min-commit-hit", type=float,
                   default=DEFAULT_MIN_COMMIT_HIT)
    c.add_argument("--max-ape", type=float, default=DEFAULT_MAX_APE)
    c.set_defaults(func=cmd_check)

    sub.add_parser("demo", help="run the end-to-end demo").set_defaults(func=cmd_demo)

    s = sub.add_parser("serve", help="localhost JSON/markdown API")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--input", default=None)
    s.set_defaults(func=cmd_serve)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
