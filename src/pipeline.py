"""Loads the raw events and rebuilds the tables for a window of 3 days (D-2 to D).

Examples:
    python src/pipeline.py --date 2026-09-30
    python src/pipeline.py --from 2026-09-01 --to 2026-09-30
"""
import argparse
import glob
from datetime import date, timedelta
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"

# Events can be up to 2 days late, so we always go 2 days back.
LATE_DAYS = 2

# Each step is an SQL file and the table it fills.
STEPS = [
    ("10_fact_query.sql", "fact_query"),
    ("11_fact_table_access.sql", "fact_table_access"),
    ("20_agg_table_user_daily.sql", "agg_table_user_daily"),
    ("21_agg_team_daily.sql", "agg_team_daily"),
]

RAW_SQL = """
CREATE OR REPLACE TABLE raw_query_events AS
SELECT * FROM read_json(
    'EVENTS_PATH',
    format = 'newline_delimited',
    columns = {
        'query_id': 'VARCHAR',
        'user': 'VARCHAR',
        'query_state': 'VARCHAR',
        'end_time': 'TIMESTAMP',
        'cpu_time_ms': 'BIGINT',
        'wall_time_ms': 'BIGINT',
        'peak_memory_bytes': 'BIGINT',
        'cumulative_memory': 'DOUBLE',
        'physical_input_bytes': 'BIGINT',
        'written_bytes': 'BIGINT',
        'inputs': 'STRUCT(catalog VARCHAR, schema_name VARCHAR, table_name VARCHAR, input_bytes BIGINT)[]',
        'output': 'STRUCT(catalog VARCHAR, schema_name VARCHAR, table_name VARCHAR)'
    }
)
"""


def load_raw(con, events_path):
    """Read the JSONL files into raw_query_events.

    events_path can be one file or a pattern like data/events/*.jsonl.
    """
    if not glob.glob(events_path):
        raise FileNotFoundError("no event files found for: " + events_path)
    path = events_path.replace("\\", "/")
    con.execute(RAW_SQL.replace("EVENTS_PATH", path))


def load_ref(con, csv_path):
    """Fill ref_user_team again from the csv file."""
    path = str(csv_path).replace("\\", "/")
    con.execute("DELETE FROM ref_user_team")
    # An empty valid_to means the row is still valid.
    con.execute(
        """
        INSERT INTO ref_user_team
        SELECT user_name, team_name, valid_from, COALESCE(valid_to, DATE '9999-12-31')
        FROM read_csv(?, header = true, types = {'valid_from': 'DATE', 'valid_to': 'DATE'})
        """,
        [path],
    )


def create_schema(con):
    con.execute((SQL_DIR / "00_schema.sql").read_text())


def run_window(con, day):
    """Rebuild the facts and marts for the window day-2 to day.

    Returns a list of (table, row count).
    """
    start_date = day - timedelta(days=LATE_DAYS)
    end_date = day
    results = []
    for file_name, table in STEPS:
        sql = (SQL_DIR / file_name).read_text()
        sql = sql.format(start_date=start_date.isoformat(), end_date=end_date.isoformat())
        con.execute(sql)
        count = con.execute(
            "SELECT COUNT(*) FROM " + table + " WHERE query_date BETWEEN ? AND ?",
            [start_date, end_date],
        ).fetchone()[0]
        results.append((table, count))
        print("  %s: %d rows (%s to %s)" % (table, count, start_date, end_date))
    return results


def main():
    parser = argparse.ArgumentParser(description="Trino usage DWH pipeline")
    parser.add_argument("--date", help="one day, YYYY-MM-DD")
    parser.add_argument("--from", dest="date_from", help="first day of a backfill")
    parser.add_argument("--to", dest="date_to", help="last day of a backfill")
    parser.add_argument("--db", default="usage.duckdb")
    parser.add_argument("--events", default=str(ROOT / "data" / "events" / "*.jsonl"))
    parser.add_argument("--users", default=str(ROOT / "data" / "user_team.csv"))
    args = parser.parse_args()

    if args.date:
        first_day = last_day = date.fromisoformat(args.date)
    elif args.date_from and args.date_to:
        first_day = date.fromisoformat(args.date_from)
        last_day = date.fromisoformat(args.date_to)
    else:
        parser.error("use --date, or --from and --to")

    con = duckdb.connect(args.db)
    create_schema(con)
    load_ref(con, args.users)
    load_raw(con, args.events)
    print("raw_query_events: %d rows" % con.execute("SELECT COUNT(*) FROM raw_query_events").fetchone()[0])

    day = first_day
    while day <= last_day:
        print(day)
        run_window(con, day)
        day = day + timedelta(days=1)

    con.close()


if __name__ == "__main__":
    main()
