-- fact_query: one row for each query.
-- pipeline.py puts the real dates in place of {start_date} and {end_date}.

-- We delete the window first, so running the script twice gives the same result.
DELETE FROM fact_query
WHERE query_date BETWEEN DATE '{start_date}' AND DATE '{end_date}';

INSERT INTO fact_query
WITH latest AS (
    -- The same event can arrive twice, so we keep only the newest one for each query_id.
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY query_id ORDER BY end_time DESC) AS rn
    FROM raw_query_events
    WHERE CAST(end_time AS DATE) BETWEEN DATE '{start_date}' AND DATE '{end_date}'
)
SELECT
    e.query_id,
    CAST(e.end_time AS DATE)                      AS query_date,
    e."user"                                      AS user_name,
    COALESCE(t.team_name, 'unknown')              AS team_name,
    e.query_state,
    COALESCE(len(e.inputs), 0)                    AS table_count,
    e.cpu_time_ms,
    e.wall_time_ms,
    e.peak_memory_bytes,
    e.cumulative_memory / 1e9                     AS memory_gb_seconds,
    e.physical_input_bytes                        AS input_bytes,
    e.written_bytes
FROM latest e
-- We want the team the user had on the query date, not the team they have today.
LEFT JOIN ref_user_team t
       ON t.user_name = e."user"
      AND CAST(e.end_time AS DATE) BETWEEN t.valid_from AND t.valid_to
WHERE e.rn = 1;
