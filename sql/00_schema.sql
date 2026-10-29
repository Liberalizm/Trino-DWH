-- Tables for the Trino usage DWH (DuckDB demo).
-- raw_query_events is missing on purpose: pipeline.py creates it when it reads the JSONL files.

-- One row = one user in one team for a period of time.
CREATE TABLE IF NOT EXISTS ref_user_team (
    user_name   VARCHAR NOT NULL,
    team_name   VARCHAR NOT NULL,
    valid_from  DATE    NOT NULL,
    valid_to    DATE    NOT NULL,   -- 9999-12-31 means the row is still valid
    PRIMARY KEY (user_name, valid_from)
);

-- One row = one query.
CREATE TABLE IF NOT EXISTS fact_query (
    query_id           VARCHAR NOT NULL PRIMARY KEY,
    query_date         DATE    NOT NULL,   -- the UTC date of end_time
    user_name          VARCHAR NOT NULL,
    team_name          VARCHAR NOT NULL,   -- the user's team on query_date ('unknown' if we don't know it)
    query_state        VARCHAR NOT NULL,   -- FINISHED or FAILED
    table_count        INTEGER NOT NULL,   -- how many tables the query read
    cpu_time_ms        BIGINT,
    wall_time_ms       BIGINT,
    peak_memory_bytes  BIGINT,
    memory_gb_seconds  DOUBLE,
    input_bytes        BIGINT,
    written_bytes      BIGINT
);

-- One row = one query, one table and one access type (read or write).
CREATE TABLE IF NOT EXISTS fact_table_access (
    query_id           VARCHAR NOT NULL,
    table_fqn          VARCHAR NOT NULL,   -- catalog.schema.table
    access_type        VARCHAR NOT NULL,   -- 'read' or 'write'
    query_date         DATE    NOT NULL,
    user_name          VARCHAR NOT NULL,
    team_name          VARCHAR NOT NULL,
    query_state        VARCHAR NOT NULL,
    input_bytes        BIGINT,
    cpu_weight         DOUBLE,             -- the part of the query's CPU that we give to this table
    cpu_time_ms_alloc  DOUBLE,             -- the query's cpu_time_ms times cpu_weight
    PRIMARY KEY (query_id, table_fqn, access_type)
);

-- One row = one user, one table and one day. Only reads from finished queries.
CREATE TABLE IF NOT EXISTS agg_table_user_daily (
    query_date         DATE    NOT NULL,
    table_fqn          VARCHAR NOT NULL,
    user_name          VARCHAR NOT NULL,
    team_name          VARCHAR NOT NULL,
    query_count        BIGINT,
    input_bytes        BIGINT,
    cpu_time_ms_alloc  DOUBLE,
    PRIMARY KEY (query_date, table_fqn, user_name)
);

-- One row = one team and one day.
CREATE TABLE IF NOT EXISTS agg_team_daily (
    query_date         DATE    NOT NULL,
    team_name          VARCHAR NOT NULL,
    query_count        BIGINT,
    failed_count       BIGINT,
    distinct_users     BIGINT,             -- we only count users who had a finished query
    cpu_time_ms        BIGINT,
    memory_gb_seconds  DOUBLE,
    input_bytes        BIGINT,
    written_bytes      BIGINT,
    PRIMARY KEY (query_date, team_name)
);
