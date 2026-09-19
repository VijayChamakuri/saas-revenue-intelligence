# Analytical Design

## Revenue movement

For every reporting month:

```text
Closing MRR = Opening MRR
            + New MRR
            + Expansion MRR
            + Reactivation MRR
            - Contraction MRR
            - Churned MRR
```

The bridge is tested at customer, product, plan, and month grain before aggregation.

## Finance reconciliation

The finance layer compares:

- invoice header to invoice lines;
- invoices to successful and failed payment attempts;
- payments to refunds;
- invoice lines to recognized and deferred amounts;
- invoice dates to subscription and contract validity;
- currencies across billing records.

Exceptions are materialized as operational records rather than buried in a QA notebook.

## Churn risk

The modeling contract uses one account snapshot per as-of date and a future 90-day churn label. Identifiers and post-outcome fields are excluded. The final split contains 2,122 training, 1,587 calibration, and 3,057 future-test rows. Threshold selection uses a documented contact-cost and retained-margin framework.

## Forecasts and scenarios

MRR, churned MRR, and cash use rolling-origin backtests. Scenario outputs separately label changes to churn, pricing, expansion, failed-payment recovery, and marketing assumptions, so projected values cannot be mistaken for actuals.

See [data_model.md](data_model.md) for grains and the ERD, and [decision_log.md](decision_log.md) for which metric drives which decision.
