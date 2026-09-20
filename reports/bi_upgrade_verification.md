# BI upgrade verification

> Synthetic data from a seeded generator. Not real company, customer or financial results.

Starting commit: `69af662c793219c0e70295ae8aae532e84977f4e` (main, 2026-09-19). Environment: macOS on Apple silicon, Python 3.12, dbt-core with dbt-duckdb, Tableau Hyper API, LibreOffice for PDF export, Tableau Public 2026.2.2.

| Command | Result |
|---|---|
| `make pipeline` (baseline, before changes) | dbt 111 of 111, dashboard 128 of 128, 47 tests passed |
| `make pipeline` (after changes) | dbt 114 of 114 (34 models, 80 tests); metric contract 361 of 361 metric-months tie to the marts and stay in bounds; dashboard 128 of 128; audit passed; 68 tests passed; Ruff and mypy clean |
| Formula engine on `excel/finance_reconciliation.xlsx` | 854 formulas, 0 errors, all checks pass |
| `reports/finance_control_summary.pdf` | 1 page, readable, no clipping (rendered and inspected) |
| Tableau tie-out (`tableau/validation_evidence.csv`) | 288 of 288 KPI values in the packaged Hyper extract match |
| Tableau load check (launch Tableau Public with the `.twbx`, read Tableau's log) | opened, 0 errors |
| MRR bridge variance | exactly $0.00 in every month (`test_mrr_bridge_variance_is_exactly_zero_every_month`) |

## Defect found and fixed

- `mart_revenue_kpis.average_revenue_per_active_row` divided MRR by the number of mart rows (one per month), so it always equaled MRR. The mart now carries `active_customers` from `fct_mrr_movement` and `average_revenue_per_active_customer`, with not-null, non-negative and NRR range tests.

## Not verified yet

- Phone layout of the Tableau workbook (desktop layout tested).

## Tableau checkpoint (2026-09-19)

Opened in Tableau Public 2026.2.2, all four dashboards inspected, defects fixed in the generator (see `reports/visual_qa.md`), screenshots captured from Tableau, and published: https://public.tableau.com/app/profile/vijay.chamakuri/viz/SaaSRevenueIntelligenceMRRRetentionBillingControls/Executiveoverview. The live viz shows the same December 2025 KPIs as the marts.
- No dbt Semantic Layer (MetricFlow) execution: the metric contract is validated by this project instead, and is labeled that way.
- Cloud warehouse compilation (BigQuery or Snowflake) was not attempted.
- Excel open-in-Excel check for repair warnings; LibreOffice opens and renders it without error.
