# Results

Synthetic data, seed `20260831`, January 2023 through December 2025. Figures below are the committed extracts and the model run that feeds the dashboard. Ratios in the README are these values rounded to one decimal place for percents, or three decimal places for the ROC-AUC and PR-AUC. There is no confidence interval in the repository.

## December 2025 bridge

Ending MRR is $1,914,752.62. Annualized, that is $22,977,031.44. Active customers are 756.

| Component | Amount |
|---|---:|
| Opening MRR | $2,174,316.64 |
| New | $61,123.55 |
| Expansion | $17,342.09 |
| Reactivation | $0.00 |
| Contraction | $2,929.51 |
| Churned | $335,100.15 |
| Ending MRR | $1,914,752.62 |
| Net new MRR | −$259,564.02 |

Opening plus new, expansion, and reactivation, minus contraction and churn, equals ending. The same identity holds in all 36 months. The stored reconciliation difference is $0.00.

Gross revenue retention is 0.844535 (84.5% to one decimal place): opening minus contraction minus churn, divided by opening. Net revenue retention is 0.852511 (85.3%): the same ratio with expansion added back. Reactivation is zero in this month, so it does not change the ratio.

## Two different customer counts

| Count | What it is | December 2025 |
|---|---|---:|
| Cancellations | Subscriptions whose end date falls in the month | 132 |
| Of those, dated 2025-12-31 | End date equals the last day of the window | 120 |
| Churned customers | Distinct customers with a churn movement (MRR to zero) | 129 |

The median count of cancellations in earlier months is 4. The mean of those earlier months is 4.46. Churned customers (129) are a different grain from cancellation end dates (132).

## Billing

Failed-payment exposure sums to $1,461,681.54 across 638 invoices. Billed amount over the same 36 months is $40,862,284.26, so the exposure is 3.6% of billed (the unrounded share is 0.0358). December's own exposure is $53,721.83. That month is not the $1,461,681.54.

All 969 finance-exception rows are `contract_date_conflict`. No other rule fires on this extract.

## Churn score

The shipped model is calibrated logistic regression. The holdout is every snapshot after 2024-12-31.

| | Logistic regression | Gradient boosting |
|---|---:|---:|
| ROC-AUC | 0.633 | 0.502 |
| PR-AUC | 0.031 | 0.020 |
| Brier score | 0.0186 | 0.0188 |
| Threshold chosen on the calibration window | 4% | 3% |
| Accounts flagged on the holdout | 419 | 571 |

Unrounded logistic scores are ROC-AUC 0.632981, PR-AUC 0.030602, and Brier score 0.018613. The dashboard prints the Brier score to four decimals (0.0186). Three decimals would be 0.019. Unrounded boosting scores are ROC-AUC 0.502127, PR-AUC 0.020342, and Brier score 0.018777.

The holdout has 3,057 rows and 58 cancellations, a 1.9% base rate. Across all 6,766 snapshots the label rate is 1.77%. Those are different denominators.

At the 4% logistic threshold the holdout flags 419 accounts and is right about 12 of them. Precision is 2.9% (12/419) and recall is 20.7% (12/58), which is 1.51 times the base rate. The stated payoff is $35 per contact, $6,000 of margin if a save works, and an 18% chance the save works, so a true positive is worth $1,045 and a false positive costs $35. Applied to the 12 and the 407 false positives, that is −$1,705. The 4% threshold was chosen on the calibration window, not on this holdout.

The split is 2,122 training rows through 2024-06-30, 1,587 calibration rows through 2024-12-31, and 3,057 test rows after that.

Of the 1,004 subscriptions that started, the share later canceled is 30.3% for SMB (158 of 521), 20.6% for mid-market (71 of 345), and 13.8% for enterprise (19 of 138). That is the subscription status, not the 90-day model label.

## Forecast backtest

Three methods, a 3-month horizon, and origins only after 18 months of history: 48 forecast points per series. The method with the lowest mean absolute error is the one the code keeps. WAPE is the sum of absolute errors divided by the sum of actuals. The chart in `assets/readme/model_validation.png` uses the one-decimal WAPE figures in this table.

| Series | Method kept | WAPE | Mean absolute error |
|---|---|---:|---:|
| Ending MRR | Drift | 1.4% | $23,070 |
| Churned MRR | Seasonal naive | 93.9% | $15,790 |
| Net cash collected | Drift | 2.2% | $35,792 |

The other methods, same 48 points:

| Series | Naive WAPE | Seasonal-naive WAPE | Drift WAPE |
|---|---:|---:|---:|
| Ending MRR | 7.7% | 45.4% | 1.4% |
| Churned MRR | 100.6% | 93.9% | 102.4% |
| Net cash collected | 7.6% | 45.2% | 2.2% |

Ending MRR and churned MRR are different series. A 1.4% error on the level of MRR does not mean churned MRR can be forecast. MAPE, the average of the monthly percentage errors, is a third statistic and is not the number in the README. For drift on ending MRR it is 1.4% as well (unrounded 0.0135, against a WAPE of 0.0137). For seasonal naive on churned MRR, MAPE is 133.7% while WAPE is 93.9%, because a small month with a large percentage error moves MAPE more than WAPE.
