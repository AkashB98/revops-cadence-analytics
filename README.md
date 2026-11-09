# revops-cadence-analytics

**The weekly forecast cadence, done honestly: point-in-time pipeline snapshots over a 12-week quarter, forecast accuracy graded by category, per-rep bias detection that catches the sandbagger and the happy-ears rep by name, slippage tracking, a cohort funnel that shows how flattering the snapshot shortcut is, and a one-formula capacity model — delivered as the memo for the Monday forecast call.**

Every sales organisation runs the same ritual: a weekly forecast call where reps commit numbers, deals slip quietly out of the quarter, and nobody grades last month's calls against what actually landed. The craft of a sales strategy & operations analyst is the discipline around that ritual — **point-in-time snapshots** (a forecast for week N may only use what was knowable in week N; anything else is **leakage**, the quiet bug behind most too-good pipeline reports), **accuracy by forecast category** (commit, best case, pipeline — each deserves its own hit rate, not one blended number), **per-rep bias** (some reps systematically under-call, some over-call, and the pattern is the coaching signal), **slippage** (deals whose close date pushes out of the quarter, with stage regressions on the way), and a funnel measured on **cohorts** (deals grouped by the week they were created) rather than on whatever happens to be visible in one snapshot. This project builds that whole loop on a seeded synthetic SaaS sales book, with the headline metrics computed twice — once in Python, once in SQL via stdlib `sqlite3` — and pinned equal.

> **Synthetic data only.** Every rep, account, and deal is fictional, fabricated by a seeded generator. No real company, customer, or pipeline data is used anywhere in this project.

Stdlib-only Python. Zero network, zero API keys, zero external dependencies.

## How this differs from its sibling projects

> **forecast-accuracy-lab grades time-series models, exec-kpi-kit reports KPIs, gtm-engineering-automation-kit routes and balances territories — this one runs the sales forecast cadence.**

- **forecast-accuracy-lab** — classical time-series forecasting with a rolling-origin backtest. This repo deliberately builds **no time-series models**: it reuses that lab's metric definitions (signed **bias** — forecast minus actual — and MAPE-style percentage error) and applies them to rep-submitted categorical forecasts instead of model outputs.
- **exec-kpi-kit** — an executive KPI scorecard and narrative. Owned there, deliberately absent here: this repo's only narrative surface is the operational forecast-call memo, not an exec scorecard.
- **gtm-engineering-automation-kit** — GTM routing and territory balance. Owned there, deliberately absent here: no territory-balance feature; capacity here is a single headcount formula, nothing about who owns which account.

## Quickstart

```bash
# 1. Generate the synthetic sales book (24 reps x 9 deals, seed 42)
python3 cli.py generate --out book.json

# 2. Weekly cadence: open pipeline by week + slippage + regressions
python3 cli.py cadence --input book.json

# 3. Forecast grading: accuracy by week, category accuracy,
#    per-rep bias + outlier detection, cohort-vs-snapshot funnel
python3 cli.py forecast --input book.json
python3 cli.py forecast --input book.json --week 8   # one week's call

# 4. Capacity: one formula + sensitivity table + attainment buckets
python3 cli.py capacity --input book.json

# 5. The deliverable: the Monday forecast-call memo (markdown)
python3 cli.py report --input book.json --out weekly_forecast_call.md

# 6. CI gate: exit 0 = pass, 1 = forecast-quality breach (commit
#    hit rate below --min-commit-hit, or final-week APE above
#    --max-ape), 2 = data-quality / IO error
python3 cli.py check --input book.json

# 7. One-command end-to-end demo (incl. a live serve round-trip)
python3 demo.py

# 8. Tiny localhost API: POST /forecast, GET /report, GET /health
python3 cli.py serve --port 8765
```

## The seeded book at a glance (seed 42, 12-week quarter, weeks 0–11)

**24 reps** (Enterprise / Mid-Market / Commercial across AMER-East, AMER-Central, AMER-West, EMEA), **90 accounts**, **216 deals**, **1,647 point-in-time snapshots**. Quarter quota **$6,340,000**; quarter actual (closed won) **$6,041,600** — a **$298,400** gap. At week 11 the only deals still open are the 46 slipped ones, and the final weighted forecast still carries $1,179,750 of their phantom value: the final-week forecast **bias is +19.53%** (APE 19.53%), and the memo says exactly where it sits.

Forecast accuracy **by category** — deals open in the week-8 snapshot, graded against outcomes:

| Category | Deals | Forecast | Won | Hit rate |
|---|---|---|---|---|
| commit | 32 | $1,621,000 | $1,300,300 | **0.8022** |
| best_case | 63 | $3,144,400 | $1,044,600 | **0.3322** (conversion) |
| pipeline | 32 | $1,507,400 | $389,200 | 0.2582 → **discount 0.7418** |

Read the pipeline row the way a forecast call should: three quarters of the raw pipeline number evaporates. Any plan built on undiscounted pipeline is built on that evaporation.

**Per-rep bias — the planted patterns, caught.** Bias is measured per rep at week 8 (weighted forecast vs the rep's quarter actual) and summarised as **bias share** — bias divided by the larger of forecast and actual, bounded in (−1, 1) so a rep with a tiny actual cannot explode the ratio. The generator plants exactly two behavioural patterns, and the detector (share ≤ −0.30 / ≥ +0.56, both thresholds sitting inside genuine gaps in the seeded distribution) finds exactly them:

- **R07 — the sandbagger (share −0.3661).** He records every deal one category below its stage evidence (Negotiation deals sit in best_case) — and every one of his 9 deals closes won: forecast $439,610 vs actual $693,500.
- **R19 — happy ears (share +0.6229).** He records every deal one category *above* its stage evidence, so almost everything reads commit — and only 2 of his 9 deals close won: forecast $420,550 vs actual $158,600.

The nearest normal reps sit at −0.1829 and +0.5168, so neither flag is a knife-edge call. Both detections are pinned by golden eval E5.

**Slippage.** **46 deals ($2,205,200)** slip out of the quarter — their believed close week pushes, week by week, past week 11 — and the generator plants exactly one **stage regression** per slipped deal (Negotiation → Evaluation, when the push starts): **46 regressions**, each one listed in the cadence payload and the memo. A slipped deal is not a lost deal, but a forecast that keeps counting it at full weight is how a quarter gets missed "by surprise".

**Funnel: cohort vs snapshot.** Grouping deals by **created week** (the cohort method — every deal created that week is in the denominator, won or not) gives an overall conversion of **0.5602**. The common snapshot shortcut — win rate among deals *already closed* by week 8 — gives **0.7416**. The snapshot method is **+0.1814 (18 points) too flattering**, because open and slipped deals are invisible to it. That gap is computed from the same book both ways, not asserted.

**Capacity — one formula, on purpose.** `reps_needed = ceil(quota_gap / win_rate / ramped_rep_productivity)`. With a $298,400 gap, a 0.30 win rate, and $600,000 of workable pipeline per ramped rep: pipeline needed $994,666.67 → **2 reps**. The full sensitivity table (win rate × productivity) is in the memo; the model refuses to be more complicated than that (see Scope). **Quota attainment distribution** (kept because it is a sort of numbers the forecast already produced): <50% — 4 reps; 50–80% — 6; 80–100% — 6; 100–120% — 4; >120% — 4.

## The metrics also live in SQL

Sales-ops roles screen on SQL, so the headline numbers are not Python-only: `sql/` holds the same computations as queries, loaded into an in-memory `sqlite3` database by `metrics_sql.py`, and tests + eval E8 pin SQL == Python on every shared metric.

| File | Computes |
|---|---|
| `sql/category_accuracy.sql` | Category accuracy at the forecast week (open deals by that week's category vs outcomes) |
| `sql/rep_bias.sql` | Per-rep weighted forecast at week N vs quarter actual |
| `sql/cohort_conversion.sql` | Cohort funnel by created week |
| `sql/pipeline_by_week.sql` | Open pipeline by snapshot week and category |

## Architecture

| Module | Job |
|---|---|
| `generator.py` | Deterministic synthetic book: 24 reps, 90 accounts, 216 deals, 1,647 weekly snapshots; planted sandbagger (R07), happy-ears rep (R19), and slipped deals with stage regressions |
| `validation.py` | Data-quality gate: fields, stage/category vocabularies, duplicates, week ranges, outcome presence — reports issues, never raises on bad data |
| `forecast.py` | Point-in-time forecasts (week-N snapshot only), forecast accuracy, category accuracy, per-rep bias + outlier detector, slippage/regressions, cohort funnel vs snapshot method |
| `capacity.py` | The single capacity formula + sensitivity table + quota attainment distribution |
| `metrics_sql.py` | Loads the book into in-memory sqlite3 and runs the `sql/` queries |
| `sql/` | The four core metrics as SQL (see above) |
| `report.py` | `weekly_forecast_call.md` — the Monday forecast-call memo, copied deterministically from the computed numbers; also the JSON report payload |
| `cli.py` | `generate` / `cadence` / `forecast` / `capacity` / `report` / `check` (CI exit 0/1/2) / `demo` / `serve` (stdlib `http.server` on 127.0.0.1: `POST /forecast`, `GET /report`, `GET /health`) |
| `demo.py` | End-to-end narrative with asserts: determinism, leakage poison test, detector, slippage, funnel, capacity, check exit codes, live localhost serve round-trip |
| `fixtures/` | The full seeded book (`sample_book.json`) with pinned totals |

## Evals

`python3 evals/run_evals.py` → **12/12 golden evals**, report committed at `evals/eval_report.json` (md5 `5dc76b8c32849f4a408cdaaa39efe564`, byte-identical across 3 verified runs):

- **E1** generator determinism — seed 42 dataset bytes pinned by md5 (`a4e29535872814bada5cc252bda68116`)
- **E2** validation clean on the seeded book; a tampered category trips it
- **E3** leakage guard — poisoning every post-week-8 snapshot and outcome changes the week-8 forecast by nothing ($6,802,180)
- **E4** category accuracy pinned (commit 0.8022, best-case 0.3322, pipeline discount 0.7418)
- **E5** bias detector finds exactly R07 + R19 (bias shares −0.3661 / +0.6229 pinned)
- **E6** slippage pinned (46 deals, $2,205,200, 46 stage regressions, planted IDs matched)
- **E7** funnel gap pinned (cohort 0.5602 vs snapshot 0.7416, gap +0.1814)
- **E8** SQL == Python on all four shared metrics
- **E9** capacity pinned (gap $298,400 → 2 reps) + attainment buckets pinned
- **E10** CLI `check` exit codes 0 / 1 / 2
- **E11** serve round-trip matches local forecast + memo exactly
- **E12** bundled fixture pinned (216 deals, validates clean) + memo determinism (md5 `ef92c4e7cffb501938671d2a6c3fe858`)

Unit tests: `python3 -m unittest discover -s tests` → **47 hermetic tests**, including a no-network enforcement test (sockets stubbed), the leakage poison test, hand-computed forecast/bias/slippage/funnel cases on a 3-deal book, the capacity formula's ceil/zero-gap/invalid-input cases, SQL-vs-Python equality on all four queries, validation defects, CLI exit codes, and report content.

## Development loop — what the checks actually caught

1. **Real find: the first bias detector flagged 14 of 24 reps.** The first detector took each rep's week-8 commit + best-case call against their actual. With only 5 deals per rep, ordinary luck swamps the signal — reps whose pipeline deals happened to win late looked exactly like the planted sandbagger. The fix was not a cleverer threshold; it was more signal and a better statistic: 9 deals per rep, deals created early enough to be late-stage by week 8, the *weighted* forecast as the graded number, and **bias share** (bounded in (−1, 1)) instead of a raw percentage ratio, whose denominator explodes for reps with a small actual. After the fix the planted reps sit at −0.3661 / +0.6229 with the nearest normal reps at −0.1829 / +0.5168 — separation you can threshold inside, pinned by E5.
2. **Real bug: the planted stage regressions never happened.** The first slipped-deal stage path "regressed" from Negotiation to Negotiation — the climb and the one-step drop cancelled out arithmetically, so the regression counter read 0 on a book built to have dozens. Caught by the seeded slippage test expecting the planted pattern, not by inspection. The shipped path climbs to Negotiation, drops exactly one stage when the close week first pushes, and stalls: 46 slipped deals, 46 regressions, pinned by E6.
3. **Real find: category accuracy by peak category was a nonsense metric.** The first draft grouped deals by the *strongest* category they ever reached — and the pipeline group scored a 0.0000 hit rate, because any deal that ever wins necessarily progresses past pipeline stage before it closes. The metric was grading stage progression, not forecast quality. The shipped definition grades the deals open in the week-8 snapshot by the category they carried *that week* — the question the forecast call actually asks — and pipeline lands at the honest, damning discount of 0.7418.
4. **Design decision the numbers forced: quotas were cut by ~60%.** The first quota table put 21 of 24 reps below 50% attainment, which is not a distribution, it's a broken book. Quotas were rescaled so the seeded book's attainment actually spreads (4 / 6 / 6 / 4 / 4) and the capacity gap is a plannable $298,400, not a fantasy $10.3M.

## Scope and honest limits

- **One capacity formula, deliberately.** No territory balance, no routing, no ramp curves beyond the single ramped-productivity input, no hiring-plan timeline. The sensitivity table is the honesty mechanism: it shows exactly how much the answer moves when the two inputs move.
- **No time-series models.** Forecasts here are rep-submitted categorical calls graded with borrowed metric definitions (bias, MAPE-style error) — not statistical forecasts of the pipeline itself.
- **No exec scorecard or narrative commentary** beyond the operational memo. The memo copies its sentences from computed numbers; it does not editorialize about the business.
- **Bias is measured at one forecast week (8).** A production cadence would track each rep's bias *trajectory* across all 12 weeks and flag persistence, not one snapshot; the per-week series is computed and available, the detector's week-8 choice is the pinned simplification.
- **The API is a demo surface.** It binds 127.0.0.1 only, holds its book in memory, and resets on restart.

## Why this project

It takes the author's analytics craft — the weekly business review, KPI definitions, forecast-vs-actual retrospectives from marketing and portfolio analytics — and rebuilds it on the revenue side of the house: the forecast cadence a sales strategy & operations team runs every Monday. The same discipline a forward-deployed engineer brings to a customer problem: make the logic inspectable, make the outputs reproducible, make the leakage impossible, and make the failure modes exit codes.
