from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

SCHEMAS = {
    "dim_geography": ("geography_id", "country", "region", "currency"),
    "dim_marketing_channel": ("marketing_channel_id", "channel_name"),
    "dim_product": ("product_id", "product_name"),
    "dim_plan": (
        "plan_id",
        "plan_name",
        "monthly_price_per_seat",
        "minimum_seats",
        "gross_margin_rate",
    ),
    "dim_sales_rep": ("sales_rep_id", "sales_rep_name", "region"),
    "dim_customer_success_manager": ("csm_id", "csm_name"),
    "dim_account": (
        "account_id",
        "account_name",
        "segment",
        "employee_band",
        "geography_id",
        "marketing_channel_id",
        "sales_rep_id",
        "csm_id",
        "created_date",
        "initial_use_case",
    ),
    "dim_customer": ("customer_id", "account_id", "customer_status", "customer_since"),
    "fact_subscriptions": (
        "subscription_id",
        "account_id",
        "plan_id",
        "product_id",
        "trial_start_date",
        "start_date",
        "end_date",
        "status",
        "contract_type",
        "seats",
        "discount_rate",
        "currency",
        "initial_mrr",
    ),
    "fact_subscription_events": (
        "subscription_event_id",
        "subscription_id",
        "event_timestamp",
        "event_type",
        "mrr_before",
        "mrr_after",
        "seats",
    ),
    "fact_invoices": (
        "invoice_id",
        "account_id",
        "subscription_id",
        "invoice_date",
        "due_date",
        "amount",
        "currency",
        "status",
    ),
    "fact_invoice_lines": (
        "invoice_line_id",
        "invoice_id",
        "line_type",
        "unit_amount",
        "quantity",
        "line_amount",
    ),
    "fact_payments": ("payment_id", "invoice_id", "payment_date", "amount", "currency", "status"),
    "fact_refunds": ("refund_id", "payment_id", "refund_date", "amount", "currency", "reason"),
    "fact_support_tickets": (
        "ticket_id",
        "account_id",
        "created_at",
        "priority",
        "resolution_hours",
        "escalated",
    ),
    "fact_marketing_spend": ("marketing_spend_id", "marketing_channel_id", "month", "spend_usd"),
    "fact_leads": ("lead_id", "marketing_channel_id", "created_date", "is_qualified"),
    "fact_opportunities": (
        "opportunity_id",
        "lead_id",
        "account_id",
        "created_date",
        "close_date",
        "stage",
        "amount_usd",
    ),
    "fact_contracts": (
        "contract_id",
        "subscription_id",
        "account_id",
        "start_date",
        "end_date",
        "contract_type",
        "currency",
    ),
    "fact_customer_health": (
        "health_id",
        "account_id",
        "snapshot_date",
        "health_score",
        "days_since_last_activity",
        "feature_adoption_rate",
    ),
    "fact_revenue_recognition": (
        "recognition_id",
        "invoice_id",
        "account_id",
        "recognition_date",
        "recognized_amount",
        "currency",
    ),
    "model_churn_snapshots": (
        "account_id",
        "as_of_date",
        "usage_change_30d",
        "feature_adoption_rate",
        "support_tickets_90d",
        "failed_payments_90d",
        "contract_age_months",
        "seats",
        "engagement_recency_days",
        "prior_downgrades",
        "mrr",
        "plan_type",
        "customer_size",
        "churned_within_90d",
    ),
    "product_usage_events": (
        "usage_event_id",
        "account_id",
        "event_timestamp",
        "feature",
        "event_name",
        "session_minutes",
    ),
}

PRIMARY_KEYS = {
    table: columns[0] for table, columns in SCHEMAS.items() if table != "model_churn_snapshots"
}

DATE_COLUMNS = {
    "dim_account": ("created_date",),
    "dim_customer": ("customer_since",),
    "fact_subscriptions": ("trial_start_date", "start_date", "end_date"),
    "fact_subscription_events": ("event_timestamp",),
    "fact_invoices": ("invoice_date", "due_date"),
    "fact_payments": ("payment_date",),
    "fact_refunds": ("refund_date",),
    "fact_support_tickets": ("created_at",),
    "fact_marketing_spend": ("month",),
    "fact_leads": ("created_date",),
    "fact_opportunities": ("created_date", "close_date"),
    "fact_contracts": ("start_date", "end_date"),
    "fact_customer_health": ("snapshot_date",),
    "fact_revenue_recognition": ("recognition_date",),
    "model_churn_snapshots": ("as_of_date",),
}

REFERENCES = (
    ("dim_account", "geography_id", "dim_geography", "geography_id"),
    ("dim_account", "marketing_channel_id", "dim_marketing_channel", "marketing_channel_id"),
    ("dim_account", "sales_rep_id", "dim_sales_rep", "sales_rep_id"),
    ("dim_account", "csm_id", "dim_customer_success_manager", "csm_id"),
    ("dim_customer", "account_id", "dim_account", "account_id"),
    ("fact_subscriptions", "account_id", "dim_account", "account_id"),
    ("fact_subscriptions", "plan_id", "dim_plan", "plan_id"),
    ("fact_subscriptions", "product_id", "dim_product", "product_id"),
    ("fact_subscription_events", "subscription_id", "fact_subscriptions", "subscription_id"),
    ("fact_invoices", "account_id", "dim_account", "account_id"),
    ("fact_invoices", "subscription_id", "fact_subscriptions", "subscription_id"),
    ("fact_invoice_lines", "invoice_id", "fact_invoices", "invoice_id"),
    ("fact_payments", "invoice_id", "fact_invoices", "invoice_id"),
    ("fact_refunds", "payment_id", "fact_payments", "payment_id"),
    ("fact_support_tickets", "account_id", "dim_account", "account_id"),
    (
        "fact_marketing_spend",
        "marketing_channel_id",
        "dim_marketing_channel",
        "marketing_channel_id",
    ),
    ("fact_leads", "marketing_channel_id", "dim_marketing_channel", "marketing_channel_id"),
    ("fact_opportunities", "lead_id", "fact_leads", "lead_id"),
    ("fact_opportunities", "account_id", "dim_account", "account_id"),
    ("fact_contracts", "subscription_id", "fact_subscriptions", "subscription_id"),
    ("fact_contracts", "account_id", "dim_account", "account_id"),
    ("fact_customer_health", "account_id", "dim_account", "account_id"),
    ("fact_revenue_recognition", "invoice_id", "fact_invoices", "invoice_id"),
    ("fact_revenue_recognition", "account_id", "dim_account", "account_id"),
    ("model_churn_snapshots", "account_id", "dim_account", "account_id"),
)

RANGES = {
    "dim_plan": (
        ("monthly_price_per_seat", 0, None),
        ("minimum_seats", 1, None),
        ("gross_margin_rate", 0, 1),
    ),
    "fact_subscriptions": (("seats", 1, None), ("discount_rate", 0, 0.5), ("initial_mrr", 0, None)),
    "fact_subscription_events": (
        ("mrr_before", 0, None),
        ("mrr_after", 0, None),
        ("seats", 1, None),
    ),
    "fact_invoices": (("amount", 0, None),),
    "fact_invoice_lines": (
        ("unit_amount", 0, None),
        ("quantity", 1, None),
        ("line_amount", 0, None),
    ),
    "fact_payments": (("amount", 0, None),),
    "fact_refunds": (("amount", 0, None),),
    "fact_support_tickets": (("resolution_hours", 0, None),),
    "fact_marketing_spend": (("spend_usd", 0, None),),
    "fact_opportunities": (("amount_usd", 0, None),),
    "fact_customer_health": (
        ("health_score", 0, 100),
        ("days_since_last_activity", 0, None),
        ("feature_adoption_rate", 0, 1),
    ),
    "fact_revenue_recognition": (("recognized_amount", 0, None),),
    "model_churn_snapshots": (
        ("feature_adoption_rate", 0, 1),
        ("support_tickets_90d", 0, None),
        ("failed_payments_90d", 0, None),
        ("contract_age_months", 0, None),
        ("seats", 1, None),
        ("engagement_recency_days", 0, None),
        ("prior_downgrades", 0, None),
        ("mrr", 0, None),
        ("churned_within_90d", 0, 1),
    ),
}


def _usage(path: Path, account_ids: set[object], errors: list[str]) -> None:
    seen: set[str] = set()
    for chunk in pd.read_csv(path, chunksize=100_000):
        missing = sorted(set(SCHEMAS["product_usage_events"]) - set(chunk.columns))
        if missing:
            errors.append(f"product_usage_events missing columns: {missing}")
            return
        ids = chunk.usage_event_id
        text_ids = set(ids.dropna().astype(str))
        if ids.isna().any() or ids.duplicated().any() or bool(text_ids & seen):
            errors.append("product_usage_events.usage_event_id must be unique and non-null")
        seen.update(text_ids)
        unknown = set(chunk.account_id.dropna()) - account_ids
        if unknown:
            errors.append(
                f"product_usage_events.account_id references {len(unknown)} unknown dim_account keys"
            )
        dates = pd.to_datetime(chunk.event_timestamp, format="ISO8601", errors="coerce")
        if dates.isna().any():
            errors.append("product_usage_events.event_timestamp contains invalid dates")
        minutes = pd.to_numeric(chunk.session_minutes, errors="coerce")
        if minutes.isna().any() or (minutes < 0).any():
            errors.append("product_usage_events.session_minutes outside [0, infinity]")


def _business_rules(frames: dict[str, pd.DataFrame], errors: list[str]) -> None:
    """Cross-table rules that column-level schema checks cannot express."""
    if {"fact_refunds", "fact_payments"} <= frames.keys():
        paid = frames["fact_payments"].set_index("payment_id")["amount"]
        refunded = frames["fact_refunds"].groupby("payment_id")["amount"].sum()
        over = refunded[refunded > paid.reindex(refunded.index).fillna(0) + 0.005]
        if not over.empty:
            errors.append(f"fact_refunds exceed the original payment for {len(over)} payments")
    if {"fact_invoices", "fact_subscriptions"} <= frames.keys():
        joined = frames["fact_invoices"].merge(
            frames["fact_subscriptions"][["subscription_id", "currency"]],
            on="subscription_id",
            suffixes=("", "_subscription"),
        )
        mismatched = joined[joined.currency != joined.currency_subscription]
        if not mismatched.empty:
            errors.append(f"fact_invoices currency differs from its subscription: {len(mismatched)} rows")
    if {"fact_payments", "fact_invoices"} <= frames.keys():
        joined = frames["fact_payments"].merge(
            frames["fact_invoices"][["invoice_id", "invoice_date"]], on="invoice_id"
        )
        paid_on = pd.to_datetime(joined.payment_date, format="ISO8601", errors="coerce")
        billed_on = pd.to_datetime(joined.invoice_date, format="ISO8601", errors="coerce")
        early = paid_on < billed_on
        if early.any():
            errors.append(f"fact_payments dated before their invoice: {int(early.sum())} rows")
    if "fact_contracts" in frames:
        contracts = frames["fact_contracts"].dropna(subset=["start_date"]).copy()
        contracts["start"] = pd.to_datetime(contracts.start_date, format="ISO8601", errors="coerce")
        # An empty end date means the contract is open ended.
        contracts["end"] = pd.to_datetime(contracts.end_date, format="ISO8601", errors="coerce").fillna(pd.Timestamp.max)
        overlaps = 0
        for _, group in contracts.sort_values("start").groupby("subscription_id"):
            running_end = group.end.cummax().iloc[:-1].to_numpy()
            overlaps += int((group.start.iloc[1:].to_numpy() < running_end).sum())
        if overlaps:
            errors.append(f"fact_contracts overlap within a subscription: {overlaps} pairs")


def validate(data_dir: Path) -> dict[str, object]:
    errors: list[str] = []
    frames: dict[str, pd.DataFrame] = {}
    for table, columns in SCHEMAS.items():
        path = data_dir / f"{table}.csv"
        if not path.exists():
            errors.append(f"missing source: {path}")
            continue
        if table == "product_usage_events":
            continue
        try:
            frame = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            errors.append(f"{table} has no header")
            continue
        frames[table] = frame
        missing = sorted(set(columns) - set(frame.columns))
        if missing:
            errors.append(f"{table} missing columns: {missing}")
            continue
        if table in PRIMARY_KEYS:
            key = frame[PRIMARY_KEYS[table]]
            if key.isna().any() or key.duplicated().any():
                errors.append(f"{table}.{PRIMARY_KEYS[table]} must be unique and non-null")
        for column in DATE_COLUMNS.get(table, ()):
            populated = frame[column].notna()
            if pd.to_datetime(frame.loc[populated, column], format="ISO8601", errors="coerce").isna().any():
                errors.append(f"{table}.{column} contains invalid dates")

    if "model_churn_snapshots" in frames:
        snapshots = frames["model_churn_snapshots"]
        if (
            snapshots[["account_id", "as_of_date"]].isna().any().any()
            or snapshots.duplicated(["account_id", "as_of_date"]).any()
        ):
            errors.append("model_churn_snapshots account_id/as_of_date must be unique and non-null")

    for table, rules in RANGES.items():
        if table not in frames:
            continue
        for column, lower, upper in rules:
            values = pd.to_numeric(frames[table][column], errors="coerce")
            # Modeling features may be absent to represent delayed source events.
            # Range checks apply to observed values, while operational facts remain required.
            invalid = (
                values.isna()
                if table != "model_churn_snapshots"
                else pd.Series(False, index=values.index)
            ) | (values < lower)
            if upper is not None:
                invalid |= values > upper
            if invalid.any():
                limit = upper if upper is not None else "infinity"
                errors.append(f"{table}.{column} outside [{lower}, {limit}]")

    for child, child_col, parent, parent_col in REFERENCES:
        if (
            child in frames
            and parent in frames
            and child_col in frames[child]
            and parent_col in frames[parent]
        ):
            unknown = set(frames[child][child_col].dropna()) - set(
                frames[parent][parent_col].dropna()
            )
            if unknown:
                errors.append(
                    f"{child}.{child_col} references {len(unknown)} unknown {parent} keys"
                )

    if "fact_subscriptions" in frames:
        subs = frames["fact_subscriptions"]
        dated = subs.dropna(subset=["start_date", "end_date"])
        ends = pd.to_datetime(dated.end_date, format="ISO8601", errors="coerce")
        if (ends < pd.to_datetime(dated.start_date, format="ISO8601", errors="coerce")).any():
            errors.append("fact_subscriptions end_date precedes start_date")
    for table, earlier, later in (
        ("fact_invoices", "invoice_date", "due_date"),
        ("fact_opportunities", "created_date", "close_date"),
        ("fact_contracts", "start_date", "end_date"),
    ):
        if table in frames:
            dated = frames[table].dropna(subset=[earlier, later])
            later_dates = pd.to_datetime(dated[later], format="ISO8601", errors="coerce")
            if (later_dates < pd.to_datetime(dated[earlier], format="ISO8601", errors="coerce")).any():
                errors.append(f"{table}.{later} precedes {earlier}")

    _business_rules(frames, errors)

    usage_path = data_dir / "product_usage_events.csv"
    if usage_path.exists() and "dim_account" in frames:
        _usage(usage_path, set(frames["dim_account"].account_id), errors)

    result: dict[str, object] = {
        "status": "failed" if errors else "passed",
        "errors": errors,
        "tables_checked": sum((data_dir / f"{table}.csv").exists() for table in SCHEMAS),
    }
    if errors:
        raise ValueError(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    print(json.dumps(validate(args.data_dir), indent=2))
