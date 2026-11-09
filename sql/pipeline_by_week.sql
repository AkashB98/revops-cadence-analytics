-- Weekly cadence: open pipeline by snapshot week and category.
-- Mirrors forecast.forecast_at_week open_by_category; tests pin it.
SELECT snapshot_week AS week,
       forecast_category AS category,
       COUNT(*) AS deals,
       ROUND(SUM(amount), 2) AS amount
FROM snapshots
WHERE stage NOT IN ('Closed Won', 'Closed Lost')
GROUP BY snapshot_week, forecast_category
ORDER BY snapshot_week, forecast_category;
