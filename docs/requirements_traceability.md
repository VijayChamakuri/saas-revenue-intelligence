# Requirements traceability matrix

All project data is synthetic. Outputs describe patterns detected in the generated dataset, not real company outcomes.

Every functional requirement in the [business requirements](business_requirements.md) appears exactly once, with the story that expresses it, the artifact that implements it and the check that verifies it.

| Req | Requirement (quoted from the BRD) | User story | Implementing artifacts | Verification | Status |
|---|---|---|---|---|---|
| FR-01 | "Generate deterministic, realistic source data with documented assumptions and impossible-state checks." | US-12, US-13 | `src/generation/generate.py`, `docs/data_generation_rules.md` | `tests/test_generation.py::test_generation_is_reproducible_and_valid`, `tests/test_adversarial_sources.py::test_clean_dataset_passes` | Met |
| FR-02 | "Process high-volume product events with Spark into partitioned Parquet and Hive-compatible tables." | US-13 | `spark/process_usage_events.py`, `hive/product_usage_daily.sql` | `tests/test_source_validation.py::test_usage_validation_detects_duplicate_across_chunks_and_unknown_account`; `make spark-validate` (`spark/validate_hive_table.py`) writes a Hive validation report when the optional Spark path is run | Met, optional extended path |
| FR-03 | "Transform source data through dbt staging, intermediate, fact, dimension, and mart layers." | US-01, US-03 | `dbt/models/` | dbt build (34 models, 80 tests) in `make pipeline` | Met |
| FR-04 | "Calculate and test the metrics documented in `metric_dictionary.md`." | US-09 | `metrics/semantic_layer.yml`, `src/validation/semantic_layer.py`, `docs/metric_dictionary.md` | `tests/test_semantic_layer.py::test_contract_has_every_required_field_and_real_models`, `tests/test_semantic_layer.py::test_generated_dictionary_matches_the_contract` | Met |
| FR-05 | "Reconcile monthly customer MRR from opening balance through movements to closing balance." | US-01 | `dbt/models/marts/revenue/mart_mrr_bridge.sql` | dbt `assert_mrr_bridge_rolls_forward`, `tests/test_semantic_layer.py::test_mrr_bridge_variance_is_exactly_zero_every_month` | Met |
| FR-06 | "Reconcile contracts, invoices, payments, refunds, revenue recognition, and deferred revenue." | US-03 | `dbt/models/marts/finance/fct_billing_reconciliation.sql` | dbt `assert_invoice_arithmetic`, dbt `assert_recognized_not_above_invoice_line` | Met |
| FR-07 | "Produce actionable exception tables with stable identifiers, severity, and resolution context." | US-04 | `dbt/models/marts/finance/mart_finance_exceptions.sql` | `tests/dashboard/test_dashboard.py::test_exception_exposure_counts_each_invoice_once` | Met |
| FR-08 | "Analyze logo and revenue retention by relevant customer, product, contract, and acquisition cohorts." | US-02, US-08 | `dbt/models/marts/growth/mart_cohort_retention.sql` | dbt `assert_cohort_starts_at_full_retention`, dbt `assert_cohorts_cover_all_customers` | Met |
| FR-09 | "Estimate unit economics with transparent assumptions and sensitivity ranges." | US-08 | `dbt/models/marts/growth/mart_channel_efficiency.sql`, `docs/analytical_design.md` | `tests/modeling/test_diagnostics.py::test_threshold_sensitivity_economics_are_explicit` | Met, assumptions labeled |
| FR-10 | "Build time-aware churn models with calibration, lift, explainability, and a cost-based threshold." | US-06, US-07 | `src/modeling/churn.py` | `tests/modeling/test_churn.py::test_temporal_split_has_no_overlap`, `tests/modeling/test_churn.py::test_threshold_maximizes_stated_expected_value` | Met, weak model reported honestly |
| FR-11 | "Independently validate a retention question in R and cross-check it against SQL or Python." | US-02 | `r/survival_analysis.R`, `src/analytics/survival_crosscheck.py` | `tests/analytics/test_survival_crosscheck.py::test_kaplan_meier_known_example` | Met, optional extended path |
| FR-12 | "Backtest forecasts and label actual, forecast, and scenario values distinctly." | US-13 | `src/modeling/forecast.py` | `tests/modeling/test_forecast.py::test_backtest_uses_only_prior_observations_and_all_methods` | Met |
| FR-13 | "Publish decision-ready datasets for an eight-page Power BI report." | US-10 | `src/analytics/export_bi.py`, `powerbi/` (specification only) | `dashboard/validation_evidence.csv`, `tableau/validation_evidence.csv` | Partially met, deliberately: the governed export datasets exist and are tied out, but no Power BI report was built. Tableau is the delivered BI artifact ([decision log](decision_log.md)). |
| FR-14 | "Orchestrate the reproducible workflow in Airflow with monitoring and failure visibility." | US-13 | `airflow/dags/subscription_intelligence.py` | `make airflow-test`; run audit closes with `tests/test_run_audit.py::test_close_run_marks_any_failure_failed` | Met, optional extended path |

## Coverage

All 14 functional requirements are traced: 14 of 14. FR-13 is the only partially met requirement and is marked as such rather than restated; no Power BI artifact exists and none is claimed. Stories US-05, US-11 and US-14 support these requirements rather than adding new ones: failed-payment exposure, workbook usability and disclosure control.
