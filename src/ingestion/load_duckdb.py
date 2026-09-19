from __future__ import annotations

import argparse
import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from src.db import fetch_row


def load(data_dir: Path, database: Path) -> int:
    database.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(data_dir.glob("*.csv"))
    started = datetime.now(UTC).replace(tzinfo=None)
    run_id = uuid.uuid4().hex[:12]
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    loaded_tables: list[str] = []
    with duckdb.connect(str(database)) as con:
        con.execute("create schema if not exists raw")
        con.execute("create schema if not exists audit")
        for path in files:
            if path.name == "product_usage_events.csv":
                continue
            table = path.stem
            loaded_tables.append(table)
            con.execute(
                f'create or replace table raw."{table}" as select * from read_csv_auto(?)',
                [str(path)],
            )
        loaded_tables.append("fact_product_usage")
        con.execute(
            "create or replace table raw.fact_product_usage as select * from read_csv_auto(?)",
            [str(data_dir / "product_usage_events.csv")],
        )
        # Stable analytics-contract views isolate dbt from source-system naming.
        views = {
            "accounts": "select account_id, account_name, 'active' account_status, case segment when 'SMB' then 50 when 'Mid-Market' then 400 else 2000 end employee_count, sales_rep_id, csm_id from raw.dim_account",
            "customers": "select c.customer_id, c.account_id, a.account_name customer_name, a.segment, a.initial_use_case, a.marketing_channel_id acquisition_channel_id, a.geography_id, cast(c.customer_since as timestamp) created_at, cast(c.customer_since as timestamp) + interval 14 day first_value_at from raw.dim_customer c join raw.dim_account a using(account_id)",
            "products": "select product_id, product_name, 'SaaS' product_family, 0.82 gross_margin_pct from raw.dim_product",
            "plans": "select plan_id, 'P01' product_id, plan_name, 'monthly' billing_frequency, monthly_price_per_seat list_price, minimum_seats included_seats from raw.dim_plan",
            "marketing_channels": "select marketing_channel_id channel_id, channel_name, channel_name channel_group from raw.dim_marketing_channel",
            "sales_reps": "select sales_rep_id, sales_rep_name, region team from raw.dim_sales_rep",
            "customer_success_managers": "select csm_id, csm_name, 'Customer Success' team from raw.dim_customer_success_manager",
            "geographies": "select * from raw.dim_geography",
            "subscriptions": "select s.subscription_id, c.customer_id, s.account_id, s.product_id, s.plan_id, ct.contract_id, s.status, s.start_date, s.end_date, s.trial_start_date, s.trial_start_date + interval 14 day trial_end_date, s.seats quantity, p.monthly_price_per_seat unit_price, s.discount_rate discount_pct, s.currency, s.initial_mrr mrr, cast(s.end_date as timestamp) cancelled_at from raw.fact_subscriptions s join raw.dim_customer c using(account_id) left join raw.fact_contracts ct using(subscription_id, account_id) join raw.dim_plan p using(plan_id)",
            "subscription_events": "select e.subscription_event_id, e.subscription_id, c.customer_id, e.event_timestamp event_at, e.event_type, e.mrr_before, e.mrr_after, e.seats quantity_before, e.seats quantity_after from raw.fact_subscription_events e join raw.fact_subscriptions s using(subscription_id) join raw.dim_customer c using(account_id)",
            "invoices": "select i.invoice_id, i.subscription_id, c.customer_id, i.invoice_date, i.due_date, i.status, i.currency, i.amount subtotal, 0.0 discount_amount, 0.0 tax_amount, i.amount total_amount from raw.fact_invoices i join raw.dim_customer c using(account_id)",
            "invoice_lines": "select l.invoice_line_id, l.invoice_id, s.product_id, s.plan_id, i.invoice_date service_start_date, i.invoice_date + interval 1 month service_end_date, l.quantity, l.unit_amount unit_price, 0.0 discount_amount, l.line_amount from raw.fact_invoice_lines l join raw.fact_invoices i using(invoice_id) join raw.fact_subscriptions s using(subscription_id)",
            "payments": "select p.payment_id, p.invoice_id, c.customer_id, cast(p.payment_date as timestamp) payment_at, p.status, p.amount, p.currency, case when p.status='failed' then 'synthetic_decline' end failure_reason from raw.fact_payments p join raw.fact_invoices i using(invoice_id) join raw.dim_customer c using(account_id)",
            "refunds": "select r.refund_id, r.payment_id, p.invoice_id, cast(r.refund_date as timestamp) refund_at, r.amount, r.currency, r.reason from raw.fact_refunds r join raw.fact_payments p using(payment_id)",
            "product_usage": "select usage_event_id usage_id, c.customer_id, s.product_id, cast(u.event_timestamp as date) usage_date, 1 active_users, 1 events_count, 1 features_used, (u.feature='dashboard') core_feature_used from raw.fact_product_usage u join raw.dim_customer c using(account_id) left join raw.fact_subscriptions s using(account_id)",
            "support_tickets": "select t.ticket_id, c.customer_id, t.created_at, t.created_at + t.resolution_hours * interval 1 hour resolved_at, t.priority, 'resolved' status, null::double satisfaction_score, t.escalated from raw.fact_support_tickets t join raw.dim_customer c using(account_id)",
            "marketing_spend": "select marketing_spend_id spend_id, marketing_channel_id channel_id, month spend_date, spend_usd amount, 'USD' currency from raw.fact_marketing_spend",
            "leads": "select lead_id, marketing_channel_id channel_id, cast(created_date as timestamp) created_at, null::varchar converted_opportunity_id, case when is_qualified then 'qualified' else 'new' end status from raw.fact_leads",
            "opportunities": "select o.opportunity_id, c.customer_id, a.marketing_channel_id channel_id, a.sales_rep_id, cast(o.created_date as timestamp) created_at, cast(o.close_date as timestamp) closed_at, o.stage, o.amount_usd amount, 'USD' currency from raw.fact_opportunities o join raw.dim_customer c using(account_id) join raw.dim_account a using(account_id)",
            "contracts": "select ct.contract_id, c.customer_id, ct.start_date contract_start_date, ct.end_date contract_end_date, ct.currency, s.initial_mrr * case when ct.contract_type='annual' then 12 else 1 end contract_value, ct.contract_type from raw.fact_contracts ct join raw.dim_customer c using(account_id) join raw.fact_subscriptions s using(subscription_id)",
            "customer_health": "select h.health_id, c.customer_id, h.snapshot_date score_date, h.health_score, (100-h.health_score)/100.0 risk_probability, case when h.health_score<40 then 'high' when h.health_score<70 then 'medium' else 'low' end risk_tier, 'synthetic_rules_v1' model_version from raw.fact_customer_health h join raw.dim_customer c using(account_id)",
            "revenue_recognition": "select r.recognition_id, l.invoice_line_id, c.customer_id, r.recognition_date, r.recognized_amount, 0.0 deferred_amount, r.currency from raw.fact_revenue_recognition r join raw.fact_invoices i using(invoice_id) join raw.fact_invoice_lines l using(invoice_id) join raw.dim_customer c on r.account_id=c.account_id",
        }
        # Every contract view carries _loaded_at so dbt source freshness can run.
        con.execute("create or replace table raw._load_audit as select ? as run_id, ? as loaded_at", [run_id, started])
        for name, query in views.items():
            con.execute(
                f'create or replace view raw."{name}" as select q.*, a.loaded_at as _loaded_at '
                f"from ({query}) q cross join raw._load_audit a"
            )
        source_rows = sum(
            int(fetch_row(con, f'select count(*) from raw."{name}"')[0]) for name in loaded_tables
        )
        con.execute(
            """create table if not exists audit.pipeline_runs (
                 run_id varchar primary key, started_at timestamp, finished_at timestamp, status varchar,
                 source_files integer, source_rows bigint, source_sha256 varchar,
                 dbt_resources_passed integer, dbt_resources_total integer,
                 dashboard_measures_passed integer, dashboard_measures_total integer)"""
        )
        con.execute(
            "insert into audit.pipeline_runs values (?, ?, ?, 'loaded', ?, ?, ?, null, null, null, null)",
            [run_id, started, datetime.now(UTC).replace(tzinfo=None), len(files), source_rows, digest.hexdigest()],
        )
    return len(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--database", type=Path, default=Path("data/warehouse/subscription.duckdb"))
    args = parser.parse_args()
    print(f"loaded {load(args.data_dir, args.database)} source files")
