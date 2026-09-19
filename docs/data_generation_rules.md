# Data Generation Rules

Confidential SaaS billing data is not available, so `src/generation/generate.py` builds a seeded synthetic
company (seed `20260831`, 1,200 accounts, 36 months). Behaviors below are the ones an analyst is expected to find.
Each row names the rule in the generator, whether it is deliberate, and the output that proves it.

## Planted conditions

| Condition | Generator rule | Deliberate? | Proof in this repository |
|---|---|---|---|
| Failed payments | Each invoice has a 3.5% independent chance of a failed payment and stays open | Yes | `assert_failed_payment_exposure_quantified` (dbt); 638 open invoices, $1,461,681.54, on the Finance Controls page |
| Refunds | 1.2% of successful payments get a 25% service credit | Yes | `fact_refunds` never exceeds its payment (`tests/test_adversarial_sources.py`) |
| Segment churn propensity | Cancellation odds rise with segment risk (SMB highest), account friction and payment risk, and fall with engagement | Yes | Cancelled share of started subscriptions: SMB 30.3%, mid-market 20.6%, enterprise 13.8% |
| Class imbalance | Churn labels are rare | Yes | Churn snapshot base rate 1.77% (1.90% in the future test window); PR-AUC 0.031 is judged against that base rate |
| Temporal drift | From 2025-01-01 the feature signal is weaker (0.8x) and label noise higher | Yes | `artifacts/modeling/runs/<run_id>/feature_drift.csv`; holdout ROC-AUC 0.633 |
| Delayed observations | 3.6% to 6.4% of snapshot features are blank | Yes | Missing values are reported as `n/a` and excluded from driver averages |
| Label noise | 9% of true churners are unlabeled before 2025 (14% after); 0.1% to 0.2% false positives | Yes | Churn model ceiling; see calibration on the Customer Risk page |
| Seasonality | **Not generated.** Volumes and churn have no calendar pattern | No | Seasonal-naive forecasts are a candidate only; they should not beat the naive baseline for structural reasons |

## Unintended side effects

Two patterns in the data are artifacts of how the generator assigns dates. They are real properties of the
dataset and the analytics detect them correctly, but they are not organic business behavior and must not be
presented as findings about customers.

| Pattern | Cause | Evidence |
|---|---|---|
| December 2025 churn cliff | Cancellation dates are clipped to the end of the observation window | 120 of 132 December 2025 cancellations are dated 2025-12-31; a typical month has about 4 |
| 969 `contract_date_conflict` exceptions | Every invoice is dated the first of the month, and some contracts start mid-month | All 969 precede the contract start within the start month; none falls after the contract end |

Treat both as data-quality diagnoses: the first is a window-boundary check, the second is an invoice-dating
convention mismatch. The dashboard states this next to the numbers. A follow-up generator change would
right-censor cancellations at the window end and date the first invoice on the contract start; that changes every
headline number, so it has not been made without a decision from the repository owner.

## What synthetic data can and cannot show

- It can show that the pipeline detects planted and unplanted conditions, that tests catch corrupted inputs, and
  that metrics reconcile.
- It cannot show real customer behavior, real model performance, or real business impact.
- 600,000 usage events demonstrate the processing path. They do not demonstrate scale engineering.
