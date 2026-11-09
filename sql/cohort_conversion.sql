-- Cohort funnel: deals grouped by created week, conversion measured
-- on the whole cohort. Mirrors forecast.funnel_cohort; tests pin it.
SELECT o.created_week AS created_week,
       COUNT(*) AS deals,
       ROUND(SUM(o.amount), 2) AS amount,
       SUM(CASE WHEN outc.final_stage = 'Closed Won' THEN 1 ELSE 0 END) AS won,
       ROUND(SUM(outc.closed_amount), 2) AS won_amount
FROM opportunities o
JOIN outcomes outc ON outc.opp_id = o.opp_id
GROUP BY o.created_week
ORDER BY o.created_week;
