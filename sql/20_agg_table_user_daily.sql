-- agg_table_user_daily: one row for each day, table and user.
-- Only reads from finished queries, so failed queries don't make someone a "user" of a table.

DELETE FROM agg_table_user_daily
WHERE query_date BETWEEN DATE '{start_date}' AND DATE '{end_date}';

INSERT INTO agg_table_user_daily
SELECT
    query_date,
    table_fqn,
    user_name,
    team_name,
    COUNT(*)                AS query_count,
    SUM(input_bytes)        AS input_bytes,
    SUM(cpu_time_ms_alloc)  AS cpu_time_ms_alloc
FROM fact_table_access
WHERE access_type = 'read'
  AND query_state = 'FINISHED'
  AND query_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
GROUP BY query_date, table_fqn, user_name, team_name;
