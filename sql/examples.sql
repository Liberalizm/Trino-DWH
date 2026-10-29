-- Q1. Distinct users of table X in a period
SELECT COUNT(DISTINCT user_name) AS distinct_users
FROM agg_table_user_daily
WHERE table_fqn = 'iceberg.sales.orders'
  AND query_date BETWEEN DATE '2026-09-01' AND DATE '2026-09-30';

-- Q2. Resources consumed by team Y in a period
SELECT team_name,
       SUM(query_count)                          AS queries,
       ROUND(SUM(cpu_time_ms) / 3.6e6, 1)        AS cpu_hours,
       ROUND(SUM(memory_gb_seconds) / 3600, 1)   AS memory_gb_hours,
       ROUND(SUM(input_bytes) / 1e12, 3)         AS tb_read
FROM agg_team_daily
WHERE team_name = 'data-platform'
  AND query_date BETWEEN DATE '2026-09-01' AND DATE '2026-09-30'
GROUP BY team_name;

-- Q3a. Trend: weekly distinct users of table X
SELECT date_trunc('week', query_date) AS week,
       COUNT(DISTINCT user_name)       AS distinct_users
FROM agg_table_user_daily
WHERE table_fqn = 'iceberg.sales.orders'
GROUP BY 1 ORDER BY 1;

-- Q3b. Trend: weekly CPU of team Y
SELECT date_trunc('week', query_date) AS week,
       SUM(cpu_time_ms) / 3.6e6        AS cpu_hours
FROM agg_team_daily
WHERE team_name = 'data-platform'
GROUP BY 1 ORDER BY 1;
