# Gap analysis

All project data is synthetic. Outputs describe patterns detected in the generated dataset, not real company outcomes.

As-is is the manual close in [process_map.md](process_map.md); to-be is what this repository does today. Every number comes from a committed artifact. Where nothing was measured, the row says "not measured".

| Area | As-is (manual close) | To-be (this repository) | Measured delta | Evidence |
|---|---|---|---|---|
| MRR roll-forward | Spreadsheet bridge, differences explained in email | Bridge tested to roll forward every month | Variance exactly $0.00 in all 36 months | `tests/test_semantic_layer.py::test_mrr_bridge_variance_is_exactly_zero_every_month` |
| Metric definitions | Retention defined differently by team | One versioned contract, recomputed from source and tied to the marts | 11 governed metrics; 361 of 361 metric-months tie and stay in bounds | `artifacts/semantic_layer_validation.csv` |
| Billing tie-out | Manual VLOOKUPs across exports | Invoice-level reconciliation tested on every build | Billed equals paid plus unpaid exposure in every month | dbt `assert_invoice_arithmetic` |
| Exception handling | Ad hoc, no owner or severity | Exception mart with rule, severity and context | 969 invoice-rule pairs queued, each counted once per rule | `dbt/models/marts/finance/mart_finance_exceptions.sql`, `tests/test_excel_workbook.py::test_exception_exposure_counts_each_invoice_once` |
| Failed payments | Noticed late, sized by hand | Exposure quantified per invoice and per month | $1.46M unpaid across 638 invoices in the generated window | `README.md`, dbt `assert_failed_payment_exposure_quantified` |
| Source quality | Bad rows discovered downstream | Impossible states rejected before load | 8 adversarial source cases detected | `tests/test_adversarial_sources.py` |
| Spreadsheet trust | Formulas edited in place, no audit | Protected workbook with live formulas and a control sheet | 854 formulas evaluated by an independent engine with no errors; only shaded inputs editable | `reports/bi_upgrade_verification.md`, `tests/test_excel_workbook.py::test_only_scenario_inputs_are_editable` |
| BI delivery | Static deck, numbers not traceable | Offline dashboard and a published Tableau workbook, both tied to the warehouse | 128 of 128 dashboard measures; 288 of 288 Tableau KPI values | `dashboard/validation_evidence.csv`, `tableau/validation_evidence.csv` |
| Churn prioritization | Recent cancellations from memory | Time-safe model with lift, threshold economics and a queue | Test ROC-AUC 0.63, reported as weak rather than headlined | `artifacts/modeling/churn_metrics.json`, `docs/analytical_design.md` |
| Run traceability | No record of what produced a number | Versioned run artifacts with hashes and a pass or fail verdict | Run ID, seed and artifact hashes recorded every run | `artifacts/verification_summary.json`, `tests/test_run_audit.py::test_run_artifacts_are_versioned_and_hash_recorded` |
| Close cycle time | Not measured | Not measured | Not measured | No timing was recorded; this project does not estimate time savings |
| Cash recovered or churn avoided | Not measured | Not measured | Not measured | Synthetic data cannot support a recovery or impact claim ([limitations](limitations_and_ethics.md)) |

## Remaining gaps

- The December 2025 churn spike is a data-dating artifact: 120 of 132 cancellations fall on the last day of the window, so it must not be read as behavior ([decision log](decision_log.md)).
- No Power BI report exists (FR-13 partially met by design); Tableau is the delivered BI artifact.
- Collections, dunning and tax are not modeled, and revenue recognition is a simplified synthetic schedule.
- Phone layouts for the Tableau workbook are not reviewed; the desktop layout is the tested one.
