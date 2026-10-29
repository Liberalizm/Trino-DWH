# Trino usage meta DWH

A small data warehouse that answers two questions from Trino query events:

1. How many distinct users used a table in a period?
2. How many resources did a team use in a period?

It runs on DuckDB, so there is nothing to install except Python packages. The design, assumptions and the production plan are in [DESIGN.md](DESIGN.md).

## How to run

```bash
pip install -r requirements.txt
python src/generate_events.py --days 30
python src/pipeline.py --from 2026-09-01 --to 2026-09-30
```

This makes the file `usage.duckdb`. Then run the queries from `sql/examples.sql` on it, for example with the DuckDB CLI or Python.

To run one day only (it rebuilds the last 3 days, because events can be late):

```bash
python src/pipeline.py --date 2026-09-30
```

Run the tests:

```bash
python -m pytest
```

## Files

- `src/generate_events.py` makes fake events (fixed seed, about 500 queries a day, some duplicates and late events).
- `src/pipeline.py` loads the data and runs the SQL files in order.
- `sql/` has the table definitions (`00_schema.sql`), the fact and mart scripts, and `examples.sql`.
- `data/user_team.csv` says which user is in which team, with dates.
- `tests/` has hand-written events and the tests.

## Example results

Data: 30 days from 2026-09-01 (15,000 queries). Queries are in [sql/examples.sql](sql/examples.sql).

**Q1. Distinct users of `iceberg.sales.orders`, September**

| distinct_users |
| --- |
| 40 |

(`orders` is the most popular table, so all 40 generated users touched it.)

**Q2. Resources of team `data-platform`, September**

| team_name | queries | cpu_hours | memory_gb_hours | tb_read |
| --- | --- | --- | --- | --- |
| data-platform | 3128 | 61.0 | 26.6 | 3.89 |

**Q3. Weekly trend (week starts on Monday)**

| week | distinct users of `orders` | CPU hours of `data-platform` |
| --- | --- | --- |
| 2026-08-31 | 40 | 12.6 |
| 2026-09-07 | 40 | 14.8 |
| 2026-09-14 | 40 | 14.0 |
| 2026-09-21 | 40 | 13.7 |
| 2026-09-28 | 40 | 5.8 |

The first and last week are not full weeks (the data is only September).
