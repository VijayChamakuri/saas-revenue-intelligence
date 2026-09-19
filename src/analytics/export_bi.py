from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from src.db import fetch_row

TABLES = {
    "mrr_movement": "analytics_revenue.fct_mrr_movement",
    "mrr_bridge": "analytics_revenue.mart_mrr_bridge",
    "revenue_kpis": "analytics_revenue.mart_revenue_kpis",
    "billing_reconciliation": "analytics_finance.fct_billing_reconciliation",
    "finance_exceptions": "analytics_finance.mart_finance_exceptions",
    "channel_efficiency": "analytics_growth.mart_channel_efficiency",
    "customer_monthly_health": "analytics_growth.mart_customer_monthly_health",
}


def export(database: Path, output: Path) -> dict[str, int]:
    output.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with duckdb.connect(str(database), read_only=True) as con:
        for name, relation in TABLES.items():
            path = output / f"{name}.csv"
            con.execute(
                f"copy (select * from {relation}) to ? (header, delimiter ',')", [str(path)]
            )
            counts[name] = int(fetch_row(con, f"select count(*) from {relation}")[0])
        forecast_sql = """
            select k.month_start as month, k.closing_mrr as mrr, b.churned_mrr,
                   b.expansion_mrr, sum(r.net_collected_cash) as cash_collected,
                   sum(r.failed_payment_exposure) as failed_payment_exposure,
                   coalesce(ms.marketing_spend, 0) as marketing_spend
            from analytics_revenue.mart_revenue_kpis k
            join analytics_revenue.mart_mrr_bridge b using(month_start)
            left join analytics_finance.fct_billing_reconciliation r
              on date_trunc('month', r.invoice_date) = k.month_start
            left join (
              select date_trunc('month', spend_date) month_start, sum(amount) marketing_spend
              from analytics_staging.stg_marketing_spend group by 1
            ) ms using(month_start)
            group by 1,2,3,4,7 order by 1
        """
        forecast_path = output / "forecast_input.csv"
        con.execute(
            "copy (" + forecast_sql + ") to ? (header, delimiter ',')",
            [str(forecast_path)],
        )
        counts["forecast_input"] = int(
            fetch_row(con, "select count(*) from (" + forecast_sql + ")")[0]
        )
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path("data/warehouse/subscription.duckdb"))
    parser.add_argument("--output", type=Path, default=Path("data/exports"))
    args = parser.parse_args()
    print(export(args.database, args.output))
