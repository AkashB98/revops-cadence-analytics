-- Category accuracy at the forecast week (:week binds from Python):
-- deals OPEN in that week's snapshot, grouped by their category that
-- week, graded against resolved outcomes.
-- Mirrors forecast.category_accuracy; tests pin equality.
SELECT s.forecast_category AS category,
       COUNT(*) AS deals,
       ROUND(SUM(s.amount), 2) AS forecast,
       ROUND(SUM(outc.closed_amount), 2) AS actual_won
FROM snapshots s
JOIN outcomes outc ON outc.opp_id = s.opp_id
WHERE s.snapshot_week = :week
  AND s.stage NOT IN ('Closed Won', 'Closed Lost')
GROUP BY s.forecast_category
ORDER BY s.forecast_category;
