"""Close out the latest pipeline run in audit.pipeline_runs with dbt and dashboard results."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from src.db import fetch_row


def close_run(database: Path, run_results: Path, evidence: Path) -> dict[str, object]:
    results = json.loads(run_results.read_text())["results"]
    ok_dbt = {"pass", "success"}
    dbt_total = len(results)
    dbt_passed = sum(1 for r in results if r["status"] in ok_dbt)
    with evidence.open(newline="", encoding="utf-8") as handle:
        checks = list(csv.DictReader(handle))
    passed = sum(1 for row in checks if row["status"] == "pass")
    status = "passed" if dbt_passed == dbt_total and passed == len(checks) else "failed"
    with duckdb.connect(str(database)) as con:
        run_id = str(fetch_row(con, "select run_id from audit.pipeline_runs order by started_at desc limit 1")[0])
        con.execute(
            """update audit.pipeline_runs set finished_at = ?, status = ?, dbt_resources_passed = ?,
               dbt_resources_total = ?, dashboard_measures_passed = ?, dashboard_measures_total = ?
               where run_id = ?""",
            [datetime.now(UTC).replace(tzinfo=None), status,
             dbt_passed, dbt_total, passed, len(checks), run_id],
        )
    return {"run_id": run_id, "status": status, "dbt": f"{dbt_passed}/{dbt_total}",
            "dashboard": f"{passed}/{len(checks)}"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/warehouse/subscription.duckdb"))
    parser.add_argument("--run-results", type=Path, default=Path("dbt/target/run_results.json"))
    parser.add_argument("--evidence", type=Path, default=Path("dashboard/validation_evidence.csv"))
    args = parser.parse_args()
    summary = close_run(args.database, args.run_results, args.evidence)
    print(summary)
    raise SystemExit(0 if summary["status"] == "passed" else 1)
