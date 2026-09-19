# Churn Model Feature Dictionary

One row per `model_churn_snapshots` row at an `as_of_date`. The label is `churned_within_90d`, a cancellation
in the 90 days after the snapshot. Every feature is a trailing measurement as of the snapshot date. The generator
derives features from ex-ante account state plus noise and never reads cancellation timing
(`src/generation/generate.py`), and `dbt/tests/assert_no_temporal_health_leakage.sql` guards the health mart.

| Feature | Definition | Why it is included |
|---|---|---|
| `usage_change_30d` | Change in product usage over the last 30 days | Falling usage precedes cancellation |
| `feature_adoption_rate` | Share of core features used | Low adoption signals weak value realization |
| `support_tickets_90d` | Tickets opened in the last 90 days | Support burden as friction |
| `failed_payments_90d` | Failed payment attempts in the last 90 days | Payment trouble raises involuntary churn |
| `contract_age_months` | Months since contract start | Tenure |
| `seats` | Licensed seats | Account size |
| `engagement_recency_days` | Days since last engagement | Disengagement |
| `prior_downgrades` | Downgrades before the snapshot | Prior contraction |
| `mrr` | MRR at the snapshot | Exposure, also a size proxy |
| `plan_type` | Monthly or annual | Contract cadence |
| `customer_size` | Small, mid-market, enterprise | Segment |

Missing values (3.6% to 6.4% for the usage-derived features) are median-imputed in the model pipeline and shown
as `n/a` on the dashboard. Time-based splits: train through 2024-06-30, calibration through 2024-12-31, future test
after that. No protected characteristics are used.
