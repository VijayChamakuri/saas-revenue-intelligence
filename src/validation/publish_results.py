from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

from src.db import fetch_row


def publish(database: Path, manifest: Path, output: Path) -> dict[str, object]:
    generated = json.loads(manifest.read_text())
    with duckdb.connect(str(database), read_only=True) as con:
        bridge = fetch_row(
            con,
            "select max(abs(reconciliation_difference)) from analytics_revenue.mart_mrr_bridge",
        )[0]
        exceptions = dict(
            con.execute(
                "select exception_type, count(*) from analytics_finance.mart_finance_exceptions group by 1"
            ).fetchall()
        )
        latest = fetch_row(
            con,
            "select month_start, closing_mrr, arr, net_new_mrr, gross_revenue_retention, "
            "net_revenue_retention from analytics_revenue.mart_revenue_kpis "
            "order by month_start desc limit 1",
        )
    result = {
        "synthetic_data": True,
        "seed": generated["seed"],
        "total_source_rows": sum(generated["counts"].values()),
        "source_counts": generated["counts"],
        "max_mrr_bridge_difference": float(bridge or 0),
        "finance_exception_counts": exceptions,
        "latest_synthetic_month": {
            "month": str(latest[0]),
            "closing_mrr": float(latest[1]),
            "arr": float(latest[2]),
            "net_new_mrr": float(latest[3]),
            "grr": float(latest[4]),
            "nrr": float(latest[5]),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path("data/warehouse/subscription.duckdb"))
    parser.add_argument("--manifest", type=Path, default=Path("data/raw/generation_manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/verification_summary.json"))
    args = parser.parse_args()
    print(json.dumps(publish(args.database, args.manifest, args.output), indent=2))
