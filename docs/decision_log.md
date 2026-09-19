# Stakeholder Decision Log

Which metric changes which decision. Observed dataset facts, model estimates, scenario outputs and
recommendations are kept separate. Every measure below is tied to the warehouse in
`dashboard/validation_evidence.csv`.

| Decision | Metric that drives it | Type | Owner | Action | How to validate |
|---|---|---|---|---|---|
| Is recurring revenue growing? | MRR, net new MRR, NRR, GRR | Observed fact | Finance, RevOps | Review the monthly bridge before any commentary | Bridge variance must be $0.00 |
| Is the December churn real? | Cancellations dated on the last day of the window | Observed fact | Data Engineering, Customer Success | Confirm how cancellation dates are set at window end | 120 of 132 cancellations fall on 2025-12-31 |
| Which failed payments to work first? | Unpaid amount per invoice | Observed fact | Finance Ops | Work the 638-invoice list by unpaid amount, largest first | Cash recovered within 14 days |
| Are contract rules wrong or is dating? | Contract exception position relative to contract window | Observed fact | RevOps | Align first-invoice dating with contract start, rerun the rule | Exception count after the change |
| Which accounts to contact? | Calibrated 90-day churn risk times MRR | Model estimate | Customer Success | Pilot the queue with a holdout group | Incremental renewal versus holdout |
| Is the retention queue worth running? | Threshold economics | Scenario | Customer Success, Finance | Do not scale until holdout net value is positive | On the synthetic holdout it is about -$2K at the cost-selected 4% threshold |
| Can the reconciliation be trusted? | Tie-out variance | Observed fact | Finance | Block reporting when a check fails | Control sheet in `excel/finance_reconciliation.xlsx` |
