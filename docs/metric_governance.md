# Metric governance and change control

> Synthetic data from a seeded generator. Not real company, customer or financial results.

`metrics/semantic_layer.yml` is the canonical contract for governed metrics. `docs/metric_dictionary.md`, the Tableau field dictionary and `tableau/expected_kpis.csv` are generated from it; the broader catalog (`dbt/metrics.yml`, [metric backlog](metric_backlog.md)) lists definitions that are not yet promoted.

## When a metric formula changes

1. Change the dbt model and the contract entry in one pull request, and increase the entry's `version`.
2. Run `make pipeline`. These fail on drift or broken logic: dbt tests (including `assert_mrr_bridge_rolls_forward` and `assert_invoice_arithmetic`), `src/validation/semantic_layer.py` (every metric-month must tie to its mart and stay in bounds), the dashboard measure checks, the Excel workbook checks, the Tableau tie-out and the pytest suite.
3. Rebuilt artifacts: marts, `data/exports`, `docs/metric_dictionary.md`, the Excel workbook and control PDF, `tableau/data`, the packaged `.twbx`, the offline dashboard.
4. Approval: the metric's `owner_role` approves the definition. Finance approves any change to a reconciliation or tolerance.
5. Republish the Tableau Public workbook after the change (docs/tableau_public_release.md).

## Rules

- A ratio with a zero denominator is empty, never zero (for example, GRR in the first month).
- GRR must stay in [0, 1], NRR in [0, 2], and the reconciliation variance must be exactly zero.
- Metric names and IDs are unique; every metric names a real dbt model.
