from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


def _id(prefix: str, values: np.ndarray) -> list[str]:
    return [f"{prefix}{int(v):06d}" for v in values]


def generate(config_path: Path, output: Path) -> dict[str, int]:
    cfg = yaml.safe_load(config_path.read_text())
    rng = np.random.default_rng(cfg["seed"])
    output.mkdir(parents=True, exist_ok=True)
    n = int(cfg["accounts"])
    start, end = pd.Timestamp(cfg["start_date"]), pd.Timestamp(cfg["end_date"])
    months = pd.date_range(start, end, freq="MS")

    geo = pd.DataFrame(
        {
            "geography_id": ["G001", "G002", "G003", "G004", "G005"],
            "country": ["United States", "Canada", "United Kingdom", "Germany", "Australia"],
            "region": ["North America", "North America", "Europe", "Europe", "APAC"],
            "currency": ["USD", "CAD", "GBP", "EUR", "USD"],
        }
    )
    channels = pd.DataFrame(
        {
            "marketing_channel_id": ["CH01", "CH02", "CH03", "CH04", "CH05"],
            "channel_name": ["Organic", "Paid Search", "Partner", "Events", "Outbound"],
        }
    )
    products = pd.DataFrame(
        {
            "product_id": ["P01", "P02", "P03"],
            "product_name": ["Core Analytics", "Workflow Automation", "Data Connect"],
        }
    )
    plans = pd.DataFrame(
        {
            "plan_id": ["PL01", "PL02", "PL03"],
            "plan_name": ["Starter", "Growth", "Enterprise"],
            "monthly_price_per_seat": [39.0, 79.0, 149.0],
            "minimum_seats": [5, 15, 50],
            "gross_margin_rate": [0.78, 0.82, 0.86],
        }
    )
    sales = pd.DataFrame(
        {
            "sales_rep_id": _id("SR", np.arange(1, 13)),
            "sales_rep_name": [f"Sales Rep {i}" for i in range(1, 13)],
            "region": np.resize(["North America", "Europe", "APAC"], 12),
        }
    )
    csms = pd.DataFrame(
        {"csm_id": _id("CS", np.arange(1, 9)), "csm_name": [f"CS Manager {i}" for i in range(1, 9)]}
    )

    geography = rng.choice(geo.geography_id, n, p=[0.56, 0.1, 0.14, 0.12, 0.08])
    segment = rng.choice(["SMB", "Mid-Market", "Enterprise"], n, p=[0.5, 0.35, 0.15])
    created = start + pd.to_timedelta(rng.integers(0, max(1, (end - start).days - 15), n), unit="D")
    accounts = pd.DataFrame(
        {
            "account_id": _id("A", np.arange(1, n + 1)),
            "account_name": [f"Synthetic Account {i}" for i in range(1, n + 1)],
            "segment": segment,
            "employee_band": np.where(
                segment == "SMB", "10-99", np.where(segment == "Mid-Market", "100-999", "1000+")
            ),
            "geography_id": geography,
            "marketing_channel_id": rng.choice(channels.marketing_channel_id, n),
            "sales_rep_id": rng.choice(sales.sales_rep_id, n),
            "csm_id": rng.choice(csms.csm_id, n),
            "created_date": created.date,
            "initial_use_case": rng.choice(
                [
                    "Finance reporting",
                    "Product analytics",
                    "Revenue operations",
                    "Customer success",
                ],
                n,
            ),
        }
    )
    customers = pd.DataFrame(
        {
            "customer_id": _id("C", np.arange(1, n + 1)),
            "account_id": accounts.account_id,
            "customer_status": "customer",
            "customer_since": created.date,
        }
    )

    sub_rows: list[list[Any]] = []
    event_rows: list[list[Any]] = []
    invoice_rows: list[list[Any]] = []
    line_rows: list[list[Any]] = []
    payment_rows: list[list[Any]] = []
    refund_rows: list[list[Any]] = []
    # Ex-ante latent account characteristics are shared causes of observed behavior
    # and later cancellation. Predictors never read the realized churn outcome.
    risk_rng = np.random.default_rng(int(cfg["seed"]) + 17)
    account_friction = risk_rng.normal(0, 1, n)
    account_engagement = risk_rng.normal(0, 1, n)
    account_payment_risk = risk_rng.normal(0, 1, n)
    usage_profiles = []
    for i, acc in accounts.iterrows():
        aid = acc.account_id
        sid = f"S{i + 1:06d}"
        plan_idx = int(rng.choice([0, 1, 2], p=[0.48, 0.38, 0.14]))
        plan = plans.iloc[plan_idx]
        seats = int(max(plan.minimum_seats, rng.lognormal(np.log(plan.minimum_seats * 1.4), 0.35)))
        contract_type = rng.choice(["monthly", "annual"], p=[0.43, 0.57])
        trial_start = pd.Timestamp(acc.created_date)
        converted = rng.random() > 0.16
        start_date = trial_start + pd.offsets.Day(14)
        base_logit = (
            -1.15
            if acc.segment == "SMB"
            else -1.75
            if acc.segment == "Mid-Market"
            else -2.20
        )
        churn_logit = (
            base_logit
            + 0.80 * account_friction[i]
            - 0.70 * account_engagement[i]
            + 0.55 * account_payment_risk[i]
        )
        churn_prob = float(1 / (1 + np.exp(-churn_logit)))
        churned = converted and rng.random() < churn_prob
        max_end = min(end, start_date + pd.DateOffset(months=int(rng.integers(5, 33))))
        if max_end < start_date:
            max_end = start_date
        end_date = max_end if churned else pd.NaT
        discount = float(rng.choice([0, 0.05, 0.1, 0.15, 0.2], p=[0.56, 0.12, 0.18, 0.1, 0.04]))
        currency = geo.set_index("geography_id").loc[acc.geography_id, "currency"]
        monthly = round(seats * float(plan.monthly_price_per_seat) * (1 - discount), 2)
        status = "trial" if not converted else "canceled" if churned else "active"
        sub_rows.append(
            [
                sid,
                aid,
                plan.plan_id,
                products.iloc[int(rng.integers(0, 3))].product_id,
                trial_start.date(),
                start_date.date() if converted else None,
                end_date.date() if churned else None,
                status,
                contract_type,
                seats,
                discount,
                currency,
                monthly,
            ]
        )
        event_rows.append(
            [f"SE{len(event_rows) + 1:07d}", sid, trial_start, "trial_started", 0.0, 0.0, seats]
        )
        if not converted:
            continue
        event_rows.append(
            [f"SE{len(event_rows) + 1:07d}", sid, start_date, "new", 0.0, monthly, seats]
        )
        active_end = end if pd.isna(end_date) else pd.Timestamp(end_date)
        active_months = months[
            (months >= start_date.to_period("M").to_timestamp())
            & (months <= active_end.to_period("M").to_timestamp())
        ]
        current_mrr = monthly
        for mi, month in enumerate(active_months):
            if mi and rng.random() < 0.055:
                old = current_mrr
                factor = float(rng.choice([0.75, 1.2, 1.35], p=[0.28, 0.42, 0.3]))
                current_mrr = round(max(20, current_mrr * factor), 2)
                event_rows.append(
                    [
                        f"SE{len(event_rows) + 1:07d}",
                        sid,
                        month,
                        "expansion" if current_mrr > old else "contraction",
                        old,
                        current_mrr,
                        seats,
                    ]
                )
            inv_id = f"INV{len(invoice_rows) + 1:08d}"
            due = month + pd.offsets.Day(14)
            invoice_rows.append(
                [inv_id, aid, sid, month.date(), due.date(), current_mrr, currency, "paid"]
            )
            line_rows.append(
                [f"IL{len(line_rows) + 1:08d}", inv_id, "subscription", current_mrr, 1, current_mrr]
            )
            failed = rng.random() < 0.035
            if failed:
                invoice_rows[-1][-1] = "open"
            pay_id = f"PAY{len(payment_rows) + 1:08d}"
            payment_rows.append(
                [
                    pay_id,
                    inv_id,
                    (month + pd.offsets.Day(int(rng.integers(1, 12)))).date(),
                    current_mrr,
                    currency,
                    "failed" if failed else "succeeded",
                ]
            )
            if not failed and rng.random() < 0.012:
                refund_rows.append(
                    [
                        f"REF{len(refund_rows) + 1:08d}",
                        pay_id,
                        (month + pd.offsets.Day(20)).date(),
                        round(current_mrr * 0.25, 2),
                        currency,
                        "service_credit",
                    ]
                )
        if churned:
            event_rows.append(
                [f"SE{len(event_rows) + 1:07d}", sid, end_date, "churn", current_mrr, 0.0, seats]
            )
        usage_profiles.append((aid, start_date, end_date, churned, seats))

    subscriptions = pd.DataFrame(
        sub_rows,
        columns=[
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
        ],
    )
    sub_events = pd.DataFrame(
        event_rows,
        columns=[
            "subscription_event_id",
            "subscription_id",
            "event_timestamp",
            "event_type",
            "mrr_before",
            "mrr_after",
            "seats",
        ],
    )
    invoices = pd.DataFrame(
        invoice_rows,
        columns=[
            "invoice_id",
            "account_id",
            "subscription_id",
            "invoice_date",
            "due_date",
            "amount",
            "currency",
            "status",
        ],
    )
    invoice_lines = pd.DataFrame(
        line_rows,
        columns=[
            "invoice_line_id",
            "invoice_id",
            "line_type",
            "unit_amount",
            "quantity",
            "line_amount",
        ],
    )
    payments = pd.DataFrame(
        payment_rows,
        columns=["payment_id", "invoice_id", "payment_date", "amount", "currency", "status"],
    )
    refunds = pd.DataFrame(
        refund_rows,
        columns=["refund_id", "payment_id", "refund_date", "amount", "currency", "reason"],
    )

    tickets = pd.DataFrame(
        {
            "ticket_id": _id("T", np.arange(1, n * 3 + 1)),
            "account_id": rng.choice(accounts.account_id, n * 3),
            "created_at": start
            + pd.to_timedelta(rng.integers(0, (end - start).days, n * 3), unit="D"),
            "priority": rng.choice(
                ["low", "medium", "high", "urgent"], n * 3, p=[0.45, 0.36, 0.15, 0.04]
            ),
            "resolution_hours": np.round(rng.lognormal(2.2, 0.8, n * 3), 2),
            "escalated": rng.random(n * 3) < 0.09,
        }
    )
    spend_rows: list[list[Any]] = []
    lead_rows: list[list[Any]] = []
    opp_rows: list[list[Any]] = []
    for month in months:
        for ch in channels.marketing_channel_id:
            spend = round(float(rng.uniform(2500, 22000)), 2)
            spend_rows.append([f"MS{len(spend_rows) + 1:06d}", ch, month.date(), spend])
            for _ in range(int(rng.integers(10, 31))):
                lid = f"L{len(lead_rows) + 1:07d}"
                lead_date = month + pd.offsets.Day(int(rng.integers(0, 27)))
                qualified = rng.random() < 0.42
                lead_rows.append([lid, ch, lead_date.date(), bool(qualified)])
                if qualified and rng.random() < 0.55:
                    oid = f"O{len(opp_rows) + 1:07d}"
                    won = rng.random() < 0.29
                    amount = round(float(rng.lognormal(8.8, 0.8)), 2)
                    opp_rows.append(
                        [
                            oid,
                            lid,
                            rng.choice(accounts.account_id),
                            lead_date.date(),
                            (lead_date + pd.offsets.Day(int(rng.integers(12, 95)))).date(),
                            "won" if won else "lost",
                            amount,
                        ]
                    )
    spend = pd.DataFrame(
        spend_rows, columns=["marketing_spend_id", "marketing_channel_id", "month", "spend_usd"]
    )
    leads = pd.DataFrame(
        lead_rows, columns=["lead_id", "marketing_channel_id", "created_date", "is_qualified"]
    )
    opportunities = pd.DataFrame(
        opp_rows,
        columns=[
            "opportunity_id",
            "lead_id",
            "account_id",
            "created_date",
            "close_date",
            "stage",
            "amount_usd",
        ],
    )

    contracts = subscriptions.loc[
        subscriptions.start_date.notna(),
        ["subscription_id", "account_id", "start_date", "end_date", "contract_type", "currency"],
    ].copy()
    contracts.insert(0, "contract_id", _id("CT", np.arange(1, len(contracts) + 1)))
    health_dates = pd.to_datetime(subscriptions.end_date).fillna(end).dt.date
    health = pd.DataFrame(
        {
            "health_id": _id("H", np.arange(1, n + 1)),
            "account_id": accounts.account_id,
            "snapshot_date": health_dates,
            "health_score": rng.integers(20, 100, n),
            "days_since_last_activity": rng.integers(0, 90, n),
            "feature_adoption_rate": np.round(rng.beta(3, 2, n), 4),
        }
    )
    recognition = invoices[
        ["invoice_id", "account_id", "invoice_date", "amount", "currency"]
    ].copy()
    recognition.insert(0, "recognition_id", _id("RR", np.arange(1, len(recognition) + 1)))
    recognition.rename(
        columns={"invoice_date": "recognition_date", "amount": "recognized_amount"}, inplace=True
    )

    snapshot_rows = []
    # Churn features are noisy observations of the ex-ante latent account state.
    churn_rng = np.random.default_rng(int(cfg["seed"]) + 29)
    split_months = pd.date_range("2023-03-31", "2025-09-30", freq="3ME")
    for i, sub in subscriptions.iterrows():
        account = accounts.iloc[i]
        churn_date = pd.to_datetime(sub.end_date)
        for snapshot in split_months:
            if snapshot < pd.Timestamp(sub.trial_start_date):
                continue
            true_future_churn = int(
                pd.notna(churn_date)
                and snapshot < churn_date
                and churn_date <= snapshot + pd.offsets.Day(90)
            )
            # Snapshot-local operational pressure is generated from the ex-ante
            # account state plus fresh noise. It never reads cancellation timing.
            future_regime = snapshot >= pd.Timestamp("2025-01-01")
            signal_strength = 0.80 if future_regime else 1.0
            friction = account_friction[i]
            engagement = account_engagement[i]
            payment_risk = account_payment_risk[i]
            operational_pressure = max(
                0.0,
                0.35 * friction - 0.25 * engagement + churn_rng.normal(0, 0.40),
            )
            observed_label = true_future_churn
            # Labels reflect delayed CRM updates and occasional unrecorded churn.
            if observed_label and churn_rng.random() < (0.14 if future_regime else 0.09):
                observed_label = 0
            elif not observed_label and churn_rng.random() < (
                0.002 if future_regime else 0.001
            ):
                observed_label = 1
            usage_change = churn_rng.normal(
                -0.025
                - 0.15 * engagement
                - 0.25 * operational_pressure * signal_strength,
                0.30 + 0.05 * future_regime,
            )
            adoption = np.clip(
                churn_rng.beta(3, 2)
                + 0.12 * engagement
                - 0.15 * operational_pressure * signal_strength,
                0,
                1,
            )
            recency = churn_rng.gamma(
                2.0,
                max(2.0, 6.0 + 2.5 * friction + 2.0 * operational_pressure),
            )
            snapshot_rows.append(
                {
                    "account_id": sub.account_id,
                    "as_of_date": snapshot.date(),
                    "usage_change_30d": round(float(usage_change), 4),
                    "feature_adoption_rate": round(float(adoption), 4),
                    "support_tickets_90d": int(
                        churn_rng.poisson(
                            max(0.1, 1.5 + 0.60 * friction + 0.9 * operational_pressure)
                        )
                    ),
                    "failed_payments_90d": int(
                        churn_rng.binomial(
                            2,
                            float(
                                np.clip(
                                    0.045
                                    + 0.055 * payment_risk
                                    + 0.07 * operational_pressure,
                                    0.005,
                                    0.35,
                                )
                            ),
                        )
                    ),
                    "contract_age_months": max(
                        0,
                        (snapshot.year - pd.Timestamp(sub.trial_start_date).year) * 12
                        + snapshot.month
                        - pd.Timestamp(sub.trial_start_date).month,
                    ),
                    "seats": sub.seats,
                    "engagement_recency_days": round(float(recency), 2),
                    "prior_downgrades": int(
                        churn_rng.binomial(
                            2, float(np.clip(0.07 + 0.035 * friction, 0.01, 0.25))
                        )
                    ),
                    "mrr": sub.initial_mrr,
                    "plan_type": sub.contract_type,
                    "customer_size": str(account.segment).lower().replace("-", "_"),
                    "churned_within_90d": observed_label,
                }
            )
    churn_snapshots = pd.DataFrame(snapshot_rows)
    # Some recent operational observations are missing or delayed. Missingness is
    # applied only to predictors, never to dates, identifiers, or outcomes.
    delayed_columns = [
        "usage_change_30d",
        "feature_adoption_rate",
        "support_tickets_90d",
        "failed_payments_90d",
        "engagement_recency_days",
    ]
    for column in delayed_columns:
        missing_rate = 0.06 if column != "failed_payments_90d" else 0.035
        churn_snapshots.loc[
            churn_rng.random(len(churn_snapshots)) < missing_rate, column
        ] = np.nan

    tables = {
        "dim_geography": geo,
        "dim_marketing_channel": channels,
        "dim_product": products,
        "dim_plan": plans,
        "dim_sales_rep": sales,
        "dim_customer_success_manager": csms,
        "dim_account": accounts,
        "dim_customer": customers,
        "fact_subscriptions": subscriptions,
        "fact_subscription_events": sub_events,
        "fact_invoices": invoices,
        "fact_invoice_lines": invoice_lines,
        "fact_payments": payments,
        "fact_refunds": refunds,
        "fact_support_tickets": tickets,
        "fact_marketing_spend": spend,
        "fact_leads": leads,
        "fact_opportunities": opportunities,
        "fact_contracts": contracts,
        "fact_customer_health": health,
        "fact_revenue_recognition": recognition,
        "model_churn_snapshots": churn_snapshots,
    }
    for name, frame in tables.items():
        frame.to_csv(output / f"{name}.csv", index=False)

    # Event log is generated in chunks to keep memory bounded.
    event_count = int(cfg["usage_events"])
    account_ids = accounts.account_id.to_numpy()
    with (output / "product_usage_events.csv").open("w") as handle:
        handle.write(
            "usage_event_id,account_id,event_timestamp,feature,event_name,session_minutes\n"
        )
        written = 0
        while written < event_count:
            size = min(100_000, event_count - written)
            aids = rng.choice(account_ids, size)
            timestamps = start + pd.to_timedelta(
                rng.integers(0, (end - start).days * 86400, size), unit="s"
            )
            chunk = pd.DataFrame(
                {
                    "usage_event_id": _id("UE", np.arange(written + 1, written + size + 1)),
                    "account_id": aids,
                    "event_timestamp": timestamps,
                    "feature": rng.choice(
                        ["dashboard", "export", "alert", "integration", "forecast"],
                        size,
                        p=[0.34, 0.21, 0.18, 0.17, 0.1],
                    ),
                    "event_name": rng.choice(["view", "create", "share", "run"], size),
                    "session_minutes": np.round(rng.gamma(2, 4, size), 2),
                }
            )
            chunk.to_csv(handle, index=False, header=False)
            written += size

    counts = {name: len(frame) for name, frame in tables.items()} | {
        "product_usage_events": event_count
    }
    (output / "generation_manifest.json").write_text(
        json.dumps({"seed": cfg["seed"], "synthetic": True, "counts": counts}, indent=2)
    )
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/project.yml"))
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    print(json.dumps(generate(args.config, args.output), indent=2))
