import sys
from datetime import date
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pipeline  # noqa: E402

GOLDEN = str(ROOT / "tests" / "golden_events.jsonl")
USERS = ROOT / "data" / "user_team.csv"
TABLES = [
    "fact_query",
    "fact_table_access",
    "agg_table_user_daily",
    "agg_team_daily",
]


@pytest.fixture
def con(tmp_path):
    """A new temporary database with the golden events loaded, after running the pipeline for 2026-09-12."""
    connection = duckdb.connect(str(tmp_path / "test.duckdb"))
    pipeline.create_schema(connection)
    pipeline.load_ref(connection, USERS)
    pipeline.load_raw(connection, GOLDEN)
    pipeline.run_window(connection, date(2026, 9, 12))
    yield connection
    connection.close()


def test_dedup_keeps_one_row_per_query(con):
    raw_rows = con.execute("SELECT COUNT(*) FROM raw_query_events").fetchone()[0]
    fact_rows = con.execute("SELECT COUNT(*) FROM fact_query").fetchone()[0]
    q1_rows = con.execute("SELECT COUNT(*) FROM fact_query WHERE query_id = 'q1'").fetchone()[0]

    assert raw_rows == 10  # q1 is in the file twice
    assert fact_rows == 9
    assert q1_rows == 1


def test_allocated_cpu_sums_to_query_cpu(con):
    # for each query that has reads: compare the allocated CPU with the real CPU
    rows = con.execute(
        """
        SELECT q.query_id, q.cpu_time_ms, SUM(a.cpu_time_ms_alloc)
        FROM fact_query q
        JOIN fact_table_access a ON a.query_id = q.query_id
        WHERE a.access_type = 'read'
        GROUP BY q.query_id, q.cpu_time_ms
        """
    ).fetchall()
    assert len(rows) == 9
    for query_id, cpu, allocated in rows:
        assert allocated == pytest.approx(cpu), query_id

    # q2: its three tables have 60%, 30% and 10% of the bytes
    orders_cpu = con.execute(
        "SELECT cpu_time_ms_alloc FROM fact_table_access "
        "WHERE query_id = 'q2' AND table_fqn = 'iceberg.sales.orders'"
    ).fetchone()[0]
    assert orders_cpu == pytest.approx(6000)

    # q8 read 0 bytes, so the CPU is split equally: 2000 for each table
    q8_cpu = con.execute(
        "SELECT cpu_time_ms_alloc FROM fact_table_access WHERE query_id = 'q8'"
    ).fetchall()
    assert [row[0] for row in q8_cpu] == [pytest.approx(2000), pytest.approx(2000)]


def test_team_change_uses_team_on_query_date(con):
    teams = dict(con.execute("SELECT query_id, team_name FROM fact_query").fetchall())

    assert teams["q6"] == "marketing"  # zed on 2026-09-10, before they moved
    assert teams["q7"] == "finance"    # zed on 2026-09-11, after they moved
    assert teams["q5"] == "data-platform"  # service account
    assert teams["q9"] == "unknown"    # this user is not in user_team.csv


def test_write_and_failed_query(con):
    write_rows = con.execute(
        "SELECT table_fqn, input_bytes, cpu_time_ms_alloc FROM fact_table_access "
        "WHERE access_type = 'write'"
    ).fetchall()
    assert write_rows == [("iceberg.tmp.orders_copy", 0, 0.0)]

    # q4 failed: it is counted in failed_count, but dave is not a user of the table
    failed = con.execute("SELECT SUM(failed_count) FROM agg_team_daily").fetchone()[0]
    assert failed == 1
    dave_rows = con.execute(
        "SELECT COUNT(*) FROM agg_table_user_daily WHERE user_name = 'dave'"
    ).fetchone()[0]
    assert dave_rows == 0


def test_running_same_day_twice_changes_nothing(con):
    def snapshot():
        result = {}
        for table in TABLES:
            result[table] = con.execute("SELECT * FROM " + table + " ORDER BY ALL").fetchall()
        return result

    before = snapshot()
    pipeline.run_window(con, date(2026, 9, 12))
    after = snapshot()

    assert before == after
