-- fact_table_access: one row for each query, table and access type.
-- Run it after 10_fact_query.sql, because user, team and cpu are taken from fact_query.

DELETE FROM fact_table_access
WHERE query_date BETWEEN DATE '{start_date}' AND DATE '{end_date}';

INSERT INTO fact_table_access
WITH latest AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY query_id ORDER BY end_time DESC) AS rn
    FROM raw_query_events
    WHERE CAST(end_time AS DATE) BETWEEN DATE '{start_date}' AND DATE '{end_date}'
),
unnested AS (
    -- one row for every table that the query read
    SELECT query_id, UNNEST(inputs) AS input
    FROM latest
    WHERE rn = 1
),
reads AS (
    -- Group by table, because a query can read the same table twice.
    SELECT
        query_id,
        input.catalog || '.' || input.schema_name || '.' || input.table_name AS table_fqn,
        SUM(input.input_bytes) AS input_bytes
    FROM unnested
    GROUP BY query_id, table_fqn
),
weighted AS (
    SELECT
        query_id,
        table_fqn,
        input_bytes,
        -- the table's share of the bytes; if the query read 0 bytes, we split the CPU equally
        CASE
            WHEN SUM(input_bytes) OVER (PARTITION BY query_id) > 0
                THEN input_bytes * 1.0 / SUM(input_bytes) OVER (PARTITION BY query_id)
            ELSE 1.0 / COUNT(*) OVER (PARTITION BY query_id)
        END AS cpu_weight
    FROM reads
),
writes AS (
    SELECT
        query_id,
        "output".catalog || '.' || "output".schema_name || '.' || "output".table_name AS table_fqn
    FROM latest
    WHERE rn = 1 AND "output" IS NOT NULL
),
all_access AS (
    SELECT query_id, table_fqn, 'read' AS access_type, input_bytes, cpu_weight
    FROM weighted
    UNION ALL
    -- Writes get no CPU, otherwise the query's CPU would be counted twice.
    SELECT query_id, table_fqn, 'write' AS access_type, 0 AS input_bytes, 0.0 AS cpu_weight
    FROM writes
)
SELECT
    a.query_id,
    a.table_fqn,
    a.access_type,
    q.query_date,
    q.user_name,
    q.team_name,
    q.query_state,
    a.input_bytes,
    a.cpu_weight,
    q.cpu_time_ms * a.cpu_weight AS cpu_time_ms_alloc
FROM all_access a
JOIN fact_query q ON q.query_id = a.query_id;
