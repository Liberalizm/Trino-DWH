"""Creates fake Trino QueryCompletedEvent data. It writes one JSONL file for each day.

Example:
    python src/generate_events.py --days 30
"""
import argparse
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The 12 guest users are not in user_team.csv, so their queries go to team 'unknown'.
USERS = (
    ["alice", "bob", "carol", "dave", "erin", "frank", "grace", "heidi", "ivan",
     "judy", "karl", "laura", "mike", "nina", "oscar", "peggy", "quinn", "rita",
     "sam", "tina", "uma", "victor", "wendy", "xavier", "yara", "zed",
     "svc_etl", "svc_bi"]
    + ["guest%02d" % i for i in range(1, 13)]
)

# Service accounts run many more queries than real people.
USER_WEIGHTS = [10 if name.startswith("svc_") else 2 for name in USERS]

# 25 tables. The ones at the start of the list are used the most.
TABLES = [
    "iceberg.sales.orders", "iceberg.sales.customers", "iceberg.sales.products",
    "iceberg.sales.order_items", "iceberg.marketing.campaigns",
    "iceberg.marketing.clicks", "iceberg.marketing.emails", "iceberg.finance.invoices",
    "iceberg.finance.payments", "iceberg.finance.budget", "iceberg.ml.features",
    "iceberg.ml.predictions", "iceberg.ml.labels", "iceberg.web.sessions",
    "iceberg.web.pageviews", "iceberg.web.events", "iceberg.hr.employees",
    "iceberg.hr.departments", "iceberg.ops.logs", "iceberg.ops.alerts",
    "iceberg.ops.deployments", "iceberg.crm.leads", "iceberg.crm.contacts",
    "iceberg.crm.deals", "iceberg.ref.countries",
]
TABLE_WEIGHTS = [1.0 / (i + 1) for i in range(len(TABLES))]

# Tables that the CTAS queries write into.
OUTPUT_TABLES = [
    "iceberg.tmp.orders_daily", "iceberg.tmp.user_summary",
    "iceberg.tmp.campaign_report", "iceberg.tmp.ml_training_set",
]

QUERIES_PER_DAY = 500
FAILED_RATE = 0.03
CTAS_RATE = 0.05
DUPLICATE_RATE = 0.01
LATE_RATE = 0.005


def split_name(fqn):
    catalog, schema_name, table_name = fqn.split(".")
    return {"catalog": catalog, "schema_name": schema_name, "table_name": table_name}


def pick_tables(rng, count):
    """Pick `count` different tables. Popular tables are picked more often."""
    chosen = []
    while len(chosen) < count:
        table = rng.choices(TABLES, weights=TABLE_WEIGHTS)[0]
        if table not in chosen:
            chosen.append(table)
    return chosen


def make_event(rng, day, number):
    user = rng.choices(USERS, weights=USER_WEIGHTS)[0]
    end_time = datetime(day.year, day.month, day.day) + timedelta(seconds=rng.randint(0, 86399))

    inputs = []
    for table in pick_tables(rng, rng.randint(1, 4)):
        item = split_name(table)
        item["input_bytes"] = int(rng.lognormvariate(18, 2))
        inputs.append(item)

    cpu_time_ms = int(rng.lognormvariate(10, 1.5))
    wall_time_ms = int(cpu_time_ms * rng.uniform(0.3, 3) + 100)
    peak_memory_bytes = int(rng.lognormvariate(19, 1.5))

    output = None
    written_bytes = 0
    if rng.random() < CTAS_RATE:
        output = split_name(rng.choice(OUTPUT_TABLES))
        written_bytes = int(rng.lognormvariate(16, 1.5))

    if rng.random() < FAILED_RATE:
        state = "FAILED"
    else:
        state = "FINISHED"

    return {
        "query_id": "%s_%05d" % (day.strftime("%Y%m%d"), number),
        "user": user,
        "query_state": state,
        "end_time": end_time.isoformat(),
        "cpu_time_ms": cpu_time_ms,
        "wall_time_ms": wall_time_ms,
        "peak_memory_bytes": peak_memory_bytes,
        # in byte-seconds
        "cumulative_memory": int(peak_memory_bytes * (wall_time_ms / 1000) * rng.uniform(0.2, 0.8)),
        "physical_input_bytes": sum(i["input_bytes"] for i in inputs),
        "written_bytes": written_bytes,
        "inputs": inputs,
        "output": output,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate fake Trino query events")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--start", default="2026-09-01", help="first day, YYYY-MM-DD")
    parser.add_argument("--out", default=str(ROOT / "data" / "events"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    first_day = date.fromisoformat(args.start)
    last_day = first_day + timedelta(days=args.days - 1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Delete the old files, so the folder only has the new data.
    for old_file in out_dir.glob("*.jsonl"):
        old_file.unlink()

    # maps the day of a file to the events we will write in it
    files = {}
    for i in range(args.days):
        files[first_day + timedelta(days=i)] = []

    total = 0
    duplicates = 0
    late = 0
    for i in range(args.days):
        day = first_day + timedelta(days=i)
        for number in range(QUERIES_PER_DAY):
            event = make_event(rng, day, number)
            file_day = day

            # A few events arrive 1 or 2 days late (only if there is a file for that day).
            if rng.random() < LATE_RATE:
                later_day = day + timedelta(days=rng.randint(1, 2))
                if later_day <= last_day:
                    file_day = later_day
                    late += 1

            files[file_day].append(event)
            total += 1

            # Some events are sent twice.
            if rng.random() < DUPLICATE_RATE:
                files[file_day].append(event)
                duplicates += 1

    for day, events in files.items():
        path = out_dir / ("%s.jsonl" % day.isoformat())
        with open(path, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

    print("wrote %d days to %s" % (args.days, out_dir))
    print("%d events, %d duplicates, %d late" % (total, duplicates, late))


if __name__ == "__main__":
    main()
