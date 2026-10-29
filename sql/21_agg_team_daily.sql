-- agg_team_daily: one row for each day and team.
-- It reads fact_query (one row per query), so a query that reads many tables is counted only once.

DELETE FROM agg_team_daily
WHERE query_date BETWEEN DATE '{start_date}' AND DATE '{end_date}';

INSERT INTO agg_team_daily
SELECT
    query_date,
    team_name,
    COUNT(*)                                                       AS query_count,
    SUM(CASE WHEN query_state = 'FAILED' THEN 1 ELSE 0 END)        AS failed_count,
    -- distinct users: we only count users who had a finished query
    COUNT(DISTINCT CASE WHEN query_state = 'FINISHED' THEN user_name END) AS distinct_users,
    SUM(cpu_time_ms)                                               AS cpu_time_ms,
    SUM(memory_gb_seconds)                                         AS memory_gb_seconds,
    SUM(input_bytes)                                               AS input_bytes,
    SUM(written_bytes)                                             AS written_bytes
FROM fact_query
WHERE query_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
GROUP BY query_date, team_name;
