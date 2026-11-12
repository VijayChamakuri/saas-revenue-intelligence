# Methodology

Settings for the generator, the churn score, and the forecast. Results that come out of these settings are in [RESULTS.md](RESULTS.md). The company is synthetic.

## Generator

[`src/generation/generate.py`](../src/generation/generate.py) reads [`config/project.yml`](../config/project.yml).

| Setting | Value |
|---|---|
| Seed | 20260831 |
| Window | 2023-01-01 through 2025-12-31 |
| Accounts | 1,200 |
| Usage events | 600,000 |
| Segment mix | SMB 50%, mid-market 35%, enterprise 15% |
| Plan mix | Starter 48%, Growth 38%, Enterprise 14% |
| Seat price | $39, $79, $149 per month |
| Trial | 14 days; 16% of accounts do not convert |
| Failed payment | 3.5% of invoices, left open |
| Refund | 1.2% of successful payments, at 25% of the payment |
| Price change | 5.5% of active months, factors 0.75, 1.20, or 1.35 |

Cancellation odds use a logit of −1.15 (SMB), −1.75 (mid-market), or −2.20 (enterprise), plus latent friction, engagement, and payment risk drawn once per account. A canceled subscription's end date is the earlier of a drawn date and 2025-12-31. Invoices are dated the first of the month. The contract start is the trial start plus 14 days, so the first invoice of a start month can fall before the contract.

Churn snapshots are one row per account on quarter-ends from 2023-03-31 through 2025-09-30. The label is a cancellation in the next 90 days. Before 2025, 9% of true churn labels are flipped off and 0.1% of non-churn labels are flipped on. From 2025-01-01 those rates are 14% and 0.2%, and the feature signal is multiplied by 0.8. About 6% of usage, adoption, ticket, and recency values are blank, and 3.5% of the failed-payment feature. The blank cells are never the date, the id, or the label.

## Churn model

[`src/modeling/churn.py`](../src/modeling/churn.py).

Features: `usage_change_30d`, `feature_adoption_rate`, `support_tickets_90d`, `failed_payments_90d`, `contract_age_months`, `seats`, `engagement_recency_days`, `prior_downgrades`, `mrr`, `plan_type`, `customer_size`. Numeric columns are median-imputed and scaled. Categorical columns take the most frequent value and then a one-hot encoding that ignores unseen levels.

| | Logistic regression | Gradient boosting |
|---|---|---|
| Estimator | `LogisticRegression` | `HistGradientBoostingClassifier` |
| Settings | `max_iter=1000`, `class_weight="balanced"`, `random_state=42` | `max_iter=160`, `learning_rate=0.06`, `max_leaf_nodes=15`, `random_state=42` |
| Calibration | Sigmoid, fit on the calibration window after the base model is frozen | Same |

The time split is train through 2024-06-30, calibration through 2024-12-31, and test after that. The threshold grid is 0.01, 0.02, …, 0.99. The chosen threshold maximizes `true positives × (6000 × 0.18 − 35) − false positives × 35` on the calibration window. That payoff is an assumption, not a measured save rate. The shipped score is the logistic model.

## Forecast

[`src/modeling/forecast.py`](../src/modeling/forecast.py) compares three methods on monthly ending MRR, churned MRR, and net cash collected:

- Naive: repeat the last value.
- Seasonal naive: repeat the value from 12 months earlier.
- Drift: draw a straight line from the first history point to the last, and extend it. Forecasts are clipped at zero.

The backtest uses a 3-month horizon and requires 18 months of history before the first origin. Each origin is scored only on months before it. The kept method is the one with the lowest mean absolute error. WAPE is total absolute error divided by total actual. The code does not store a prediction interval.
