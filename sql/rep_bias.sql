-- Per-rep bias at the forecast week (:week binds from Python):
-- weighted forecast = closed-won to date + category-weighted open
-- pipeline at :week (commit x1.0, best_case x0.5, pipeline x0.2),
-- graded against the rep's full-quarter actual.
-- Mirrors forecast.rep_bias; tests pin equality.
WITH call_at AS (
  SELECT rep_id,
         SUM(CASE forecast_category
               WHEN 'commit' THEN amount
               WHEN 'best_case' THEN amount * 0.5
               ELSE amount * 0.2 END) AS open_weighted
  FROM snapshots
  WHERE snapshot_week = :week
    AND stage NOT IN ('Closed Won', 'Closed Lost')
  GROUP BY rep_id
),
closed_to_date AS (
  SELECT o.rep_id AS rep_id, SUM(outc.closed_amount) AS closed_won
  FROM outcomes outc
  JOIN opportunities o ON o.opp_id = outc.opp_id
  WHERE outc.final_stage = 'Closed Won'
    AND outc.actual_close_week IS NOT NULL
    AND outc.actual_close_week <= :week
  GROUP BY o.rep_id
),
actual AS (
  SELECT o.rep_id AS rep_id, SUM(outc.closed_amount) AS actual_won
  FROM outcomes outc
  JOIN opportunities o ON o.opp_id = outc.opp_id
  WHERE outc.final_stage = 'Closed Won'
  GROUP BY o.rep_id
)
SELECT r.rep_id AS rep_id,
       ROUND(COALESCE(c.closed_won, 0) + COALESCE(ca.open_weighted, 0), 2) AS weighted_forecast,
       ROUND(COALESCE(a.actual_won, 0), 2) AS actual
FROM reps r
LEFT JOIN call_at ca ON ca.rep_id = r.rep_id
LEFT JOIN closed_to_date c ON c.rep_id = r.rep_id
LEFT JOIN actual a ON a.rep_id = r.rep_id
ORDER BY r.rep_id;
