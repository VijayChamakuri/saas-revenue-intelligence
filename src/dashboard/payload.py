"""Extract the dashboard data payload from the certified warehouse marts.

Every number the dashboard shows is either read from a mart here or computed by the pure
functions in ``dashboard/measures.js`` from rows read here. Nothing is typed in by hand.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.db import fetch_row

WAREHOUSE = Path("data/warehouse/subscription.duckdb")
CHURN_SCORES = Path("artifacts/modeling/churn_scores.csv")
CHURN_METRICS = Path("artifacts/modeling/churn_metrics.json")
RISK_MODEL = "logistic_regression"

MOVEMENT_SQL = """
select strftime(m.month_start, '%Y-%m') as ym, m.customer_id,
       coalesce(c.segment, 'unknown') as segment,
       coalesce(pl.plan_name, 'unknown') as plan_name,
       coalesce(pr.product_name, 'unknown') as product_name,
       coalesce(c.region, 'unknown') as region, coalesce(c.customer_name, m.customer_id) as name,
       m.opening_mrr, m.closing_mrr, m.new_mrr, m.expansion_mrr, m.contraction_mrr,
       m.churned_mrr, m.reactivation_mrr
from analytics_revenue.fct_mrr_movement m
left join analytics_core.dim_customer c using (customer_id)
left join analytics_core.dim_plan pl using (plan_id)
left join analytics_core.dim_product pr on m.product_id = pr.product_id
order by m.month_start, m.customer_id
"""

KPI_SQL = """
select strftime(b.month_start, '%Y-%m') as ym, b.opening_mrr, b.new_mrr, b.expansion_mrr,
       b.contraction_mrr, b.churned_mrr, b.reactivation_mrr, b.net_new_mrr, b.closing_mrr,
       k.arr, k.gross_revenue_retention as grr, k.net_revenue_retention as nrr,
       b.reconciliation_difference
from analytics_revenue.mart_mrr_bridge b
join analytics_revenue.mart_revenue_kpis k using (month_start)
order by b.month_start
"""

CASH_SQL = """
select strftime(date_trunc('month', invoice_date), '%Y-%m') as ym,
       count(*) as invoices,
       sum(case when status <> 'paid' then 1 else 0 end) as open_invoices,
       sum(total_amount) as invoiced, sum(successful_payments) as successful_payments,
       sum(failed_payment_exposure) as failed_exposure, sum(refunded_amount) as refunded,
       sum(net_collected_cash) as net_cash, sum(recognized_amount) as recognized,
       sum(deferred_amount) as deferred, sum(payment_difference) as payment_difference
from analytics_finance.fct_billing_reconciliation
group by 1 order by 1
"""

EXCEPTION_SQL = """
select e.invoice_id, e.exception_type, e.severity, e.details,
       strftime(r.invoice_date, '%Y-%m-%d') as invoice_date, r.customer_id,
       coalesce(c.segment, 'unknown') as segment, r.status, r.currency,
       r.subtotal, r.discount_amount, r.tax_amount, r.total_amount, r.successful_payments,
       r.failed_payment_exposure, r.refunded_amount, r.recognized_amount, r.deferred_amount,
       strftime(k.contract_start_date, '%Y-%m-%d') as contract_start,
       strftime(k.contract_end_date, '%Y-%m-%d') as contract_end,
       r.subscription_id
from analytics_finance.mart_finance_exceptions e
left join analytics_finance.fct_billing_reconciliation r using (invoice_id)
left join analytics_core.dim_customer c on r.customer_id = c.customer_id
left join analytics_staging.stg_subscriptions s on r.subscription_id = s.subscription_id
left join analytics_staging.stg_contracts k on s.contract_id = k.contract_id
order by e.severity, r.invoice_date, e.invoice_id
"""

OPEN_SQL = """
select r.invoice_id, strftime(r.invoice_date, '%Y-%m-%d') as invoice_date, r.customer_id,
       coalesce(c.segment, 'unknown') as segment, r.total_amount, r.failed_payment_exposure
from analytics_finance.fct_billing_reconciliation r
left join analytics_core.dim_customer c using (customer_id)
where r.status <> 'paid'
order by r.failed_payment_exposure desc, r.invoice_id
"""

COHORT_SQL = """
select strftime(cohort_month, '%Y-%m') as cohort, months_since_start as age,
       cohort_customers as size, active_customers as active, logo_retention as logo,
       net_dollar_retention as ndr
from analytics_growth.mart_cohort_retention
order by cohort_month, months_since_start
"""

BOUNDARY_SQL = """
with cancels as (
  select end_date::date as end_date from raw.fact_subscriptions where status = 'canceled'
), latest as (select max(end_date) as last_day from cancels), monthly as (
  select date_trunc('month', end_date) as month_start, count(*) as n from cancels group by 1
)
select strftime((select last_day from latest), '%Y-%m-%d') as last_day,
       (select count(*) from cancels, latest
         where date_trunc('month', end_date) = date_trunc('month', last_day)) as month_cancellations,
       (select count(*) from cancels, latest where end_date = last_day) as last_day_cancellations,
       (select median(n) from monthly, latest
         where month_start < date_trunc('month', last_day)) as typical_month_cancellations
"""

SNAPSHOT_SQL = """
select account_id, as_of_date::varchar as as_of_date, usage_change_30d, feature_adoption_rate,
       support_tickets_90d, failed_payments_90d, engagement_recency_days, mrr, plan_type,
       customer_size
from raw.model_churn_snapshots
"""


def _records(frame: pd.DataFrame, columns: list[str] | None = None) -> list[list[Any]]:
    data = frame[columns] if columns else frame
    return json.loads(data.to_json(orient="values", double_precision=6))


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


def _dict_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.to_json(orient="records", double_precision=6))


def _encode(values: pd.Series) -> tuple[list[str], list[int]]:
    labels = sorted(values.unique().tolist())
    lookup = {label: index for index, label in enumerate(labels)}
    return labels, [lookup[value] for value in values]


def build_movement(frame: pd.DataFrame, months: list[str]) -> dict[str, Any]:
    month_index = {month: index for index, month in enumerate(months)}
    segments, seg = _encode(frame["segment"])
    plans, plan = _encode(frame["plan_name"])
    products, product = _encode(frame["product_name"])
    customers = (
        frame[["customer_id", "name", "segment", "region"]]
        .drop_duplicates("customer_id")
        .sort_values("customer_id")
        .reset_index(drop=True)
    )
    customer_index = {cid: i for i, cid in enumerate(customers["customer_id"])}
    rows = [
        [
            month_index[ym],
            seg[i],
            plan[i],
            product[i],
            customer_index[cid],
            *[round(float(v), 2) for v in values],
        ]
        for i, (ym, cid, *values) in enumerate(
            frame[
                [
                    "ym",
                    "customer_id",
                    "opening_mrr",
                    "closing_mrr",
                    "new_mrr",
                    "expansion_mrr",
                    "contraction_mrr",
                    "churned_mrr",
                    "reactivation_mrr",
                ]
            ].itertuples(index=False, name=None)
        )
    ]
    return {
        "segments": segments,
        "plans": plans,
        "products": products,
        "customers": _records(customers),
        "columns": [
            "month",
            "segment",
            "plan",
            "product",
            "customer",
            "opening",
            "closing",
            "new",
            "expansion",
            "contraction",
            "churned",
            "reactivation",
        ],
        "rows": rows,
    }


def build_risk(con: duckdb.DuckDBPyConnection, scores_path: Path) -> dict[str, Any]:
    scores = pd.read_csv(scores_path)
    snapshots = _rows(con, SNAPSHOT_SQL)
    merged = scores.merge(snapshots, on=["account_id", "as_of_date"], how="left", validate="1:1")
    if merged["mrr"].isna().any():
        raise ValueError("Scored snapshots without matching source features")
    columns = [
        "account_id",
        "as_of_date",
        f"{RISK_MODEL}_risk",
        "churned_within_90d",
        "mrr",
        "usage_change_30d",
        "feature_adoption_rate",
        "support_tickets_90d",
        "failed_payments_90d",
        "engagement_recency_days",
        "plan_type",
        "customer_size",
    ]
    return {
        "columns": [
            "account",
            "as_of",
            "risk",
            "churned",
            "mrr",
            "usage_change",
            "adoption",
            "tickets",
            "failed_payments",
            "recency_days",
            "plan_type",
            "size",
        ],
        "rows": _records(merged, columns),
    }


def build_payload(
    warehouse: Path = WAREHOUSE,
    scores_path: Path = CHURN_SCORES,
    metrics_path: Path = CHURN_METRICS,
) -> dict[str, Any]:
    metrics = json.loads(metrics_path.read_text())
    with duckdb.connect(str(warehouse), read_only=True) as con:
        kpis = _rows(con, KPI_SQL)
        months = kpis["ym"].tolist()
        movement = build_movement(_rows(con, MOVEMENT_SQL), months)
        cash = _rows(con, CASH_SQL)
        exceptions = _rows(con, EXCEPTION_SQL)
        open_invoices = _rows(con, OPEN_SQL)
        cohorts = _rows(con, COHORT_SQL)
        risk = build_risk(con, scores_path)
        source_rows = int(fetch_row(con, "select count(*) from raw.fact_invoices")[0])
        boundary = _dict_rows(_rows(con, BOUNDARY_SQL))[0]
    economics = metrics["split_metadata"]
    return {
        "meta": {
            "synthetic": True,
            "months": months,
            "latest_month": months[-1],
            "source_invoices": source_rows,
            "cancellation_boundary": boundary,
            "risk_model": RISK_MODEL,
            "risk_threshold": metrics[RISK_MODEL]["threshold"],
            "model_metrics": {
                k: metrics[RISK_MODEL][k] for k in ("roc_auc", "pr_auc", "brier_score")
            },
            "economics": {
                "contact_cost": economics["contact_cost"],
                "retained_margin": economics["retained_margin_if_successful"],
                "success_rate": economics["intervention_success_rate"],
            },
            "split": {
                key: economics[key]
                for key in ("train_end", "calibration_end", "test_rows", "calibration_rows")
            },
        },
        "kpi": _dict_rows(kpis),
        "movement": movement,
        "cash": _dict_rows(cash),
        "exceptions": _dict_rows(exceptions),
        "open_invoices": _dict_rows(open_invoices),
        "cohorts": _dict_rows(cohorts),
        "risk": risk,
    }
