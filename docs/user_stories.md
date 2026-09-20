# User stories and acceptance criteria

All project data is synthetic. Outputs describe patterns detected in the generated dataset, not real company outcomes.

Roles are the documented personas in the [business requirements](business_requirements.md) and the [stakeholder question map](stakeholder_question_map.md). They are personas for a demonstration project, not people who were interviewed. Every acceptance criterion ends with the executable check that proves it: a pytest test, a dbt test, or a committed evidence file.

## US-01 Explain the monthly MRR movement

**As a** Executive, **I want** the monthly movement from opening to closing MRR, **so that** I can prioritize growth and retention actions.

- **Given** a built warehouse, **when** the MRR bridge is computed, **then** opening plus new plus expansion plus reactivation less contraction less churn equals closing MRR for every month. Check: dbt test `assert_mrr_bridge_rolls_forward`.
- **Given** the bridge, **when** the roll-forward variance is measured, **then** it is exactly zero in every month. Check: `tests/test_semantic_layer.py::test_mrr_bridge_variance_is_exactly_zero_every_month`.
- **Given** the Tableau Executive overview, **when** a month is selected, **then** the bridge and the KPI tiles show the mart values. Check: `tests/test_tableau_package.py::test_tieout_passes_and_detects_drift`; evidence `tableau/validation_evidence.csv`.

## US-02 Trust the retention ratios

**As a** RevOps analyst, **I want** gross and net revenue retention computed one way, **so that** I can adjust coverage and renewal motions on comparable numbers.

- **Given** the metric contract, **when** GRR and NRR are recomputed from the customer-month fact, **then** they tie to the reporting mart for every month. Check: `tests/test_semantic_layer.py::test_every_metric_ties_to_its_mart_and_stays_in_bounds`; evidence `artifacts/semantic_layer_validation.csv`.
- **Given** a month with zero opening MRR, **when** the ratios are computed, **then** the result is empty rather than zero. Check: `tests/test_semantic_layer.py::test_zero_opening_mrr_gives_an_empty_ratio_not_zero`.
- **Given** a tampered churn value that pushes retention out of range, **when** validation runs, **then** the bounds check fails. Check: `tests/test_semantic_layer.py::test_retention_outside_bounds_is_caught`.

## US-03 Reconcile billing to cash and revenue

**As a** Finance analyst, **I want** invoices, payments, refunds, recognition and deferrals to reconcile, **so that** I can investigate close exceptions instead of chasing spreadsheets.

- **Given** invoice-level records, **when** the tie-out is computed, **then** billed equals paid plus unpaid failed exposure for every month. Check: dbt test `assert_invoice_arithmetic`.
- **Given** a corrupted invoice total, **when** the contract validation runs, **then** the reconciliation variance leaves its bounds and the check fails. Check: `tests/test_semantic_layer.py::test_invoice_arithmetic_mismatch_is_caught`.
- **Given** the Excel workbook, **when** the Billing Reconciliation sheet is evaluated, **then** every month shows OK. Check: `tests/test_excel_workbook.py::test_bridge_formulas_and_tie_out_checks_exist`.

## US-04 Work the exception queue

**As a** Finance analyst, **I want** billing exceptions with stable identifiers, severity and context, **so that** I can work them in order.

- **Given** the exception mart, **when** exposure is summed, **then** each invoice is counted once per rule it breaks. Check: `tests/dashboard/test_dashboard.py::test_exception_exposure_counts_each_invoice_once`.
- **Given** the Tableau Finance controls dashboard, **when** an exception class is selected, **then** the invoice list filters to that class. Check: `tests/test_tableau_package.py::test_manifest_matches_the_packaged_workbook` covers the action's source and target sheets.
- **Given** the queue, **when** it is read, **then** the page states that all current exceptions trace to invoice dating in the generator. Check: `tests/test_tableau_package.py::test_every_dashboard_shows_the_synthetic_notice_source_and_refresh`.

## US-05 Size failed-payment exposure

**As a** Finance analyst, **I want** the amount sitting on failed payment attempts, **so that** I can decide where collection effort goes first.

- **Given** invoices with failed attempts, **when** exposure is computed, **then** it is quantified and never negative. Check: dbt test `assert_failed_payment_exposure_quantified`.
- **Given** the metric contract, **when** exposure is recomputed from the billing fact, **then** it matches the value the dashboards show. Check: `tests/test_semantic_layer.py::test_every_metric_ties_to_its_mart_and_stays_in_bounds`.

## US-06 Prioritize accounts for outreach

**As a** Customer Success manager, **I want** a churn-risk queue with a threshold I control, **so that** I can prioritize outreach to a queue my team can actually work.

- **Given** scored accounts, **when** a threshold is chosen, **then** precision, recall and queue size are shown for that threshold. Check: `tests/modeling/test_diagnostics.py::test_threshold_sensitivity_economics_are_explicit`.
- **Given** the model, **when** its quality is reported, **then** lift by decile is shown rather than a single headline score. Check: `tests/modeling/test_diagnostics.py::test_calibration_and_deciles_partition_all_rows`.
- **Given** the Tableau Customer risk dashboard, **when** it is opened, **then** it states the model is a prioritization aid, not automated action. Check: `tests/test_tableau_package.py::test_every_dashboard_shows_the_synthetic_notice_source_and_refresh`.

## US-07 Keep the risk model honest about time

**As a** Data owner, **I want** the churn model trained without future information, **so that** its numbers are not optimistic by construction.

- **Given** health features and outcomes, **when** the training data is built, **then** no feature observed after the label window leaks in. Check: dbt test `assert_no_temporal_health_leakage`.
- **Given** the split, **when** train, calibration and test windows are compared, **then** they do not overlap. Check: `tests/modeling/test_churn.py::test_temporal_split_has_no_overlap`.

## US-08 Judge channels on retained revenue

**As a** Marketing analyst, **I want** cohort retention alongside acquisition cost, **so that** I can reallocate budget under stated assumptions.

- **Given** acquisition cohorts, **when** retention is computed, **then** every cohort starts at full retention and every customer belongs to exactly one cohort. Checks: dbt tests `assert_cohort_starts_at_full_retention` and `assert_cohorts_cover_all_customers`.
- **Given** unit economics, **when** they are published, **then** their assumptions and sensitivity are explicit rather than a single number. Check: `tests/modeling/test_diagnostics.py::test_threshold_sensitivity_economics_are_explicit`.

## US-09 One definition per metric

**As a** Data owner, **I want** one governed definition per metric, **so that** Excel, Tableau and the documentation cannot disagree.

- **Given** the contract, **when** a metric is added, **then** it carries owner, grain, source model, numerator, denominator, inclusions, exclusions, quality checks and known limits. Check: `tests/test_semantic_layer.py::test_contract_has_every_required_field_and_real_models`.
- **Given** two metrics with the same name, **when** the contract is validated, **then** it is rejected. Check: `tests/test_semantic_layer.py::test_duplicate_metric_names_are_rejected`.
- **Given** the contract, **when** the metric dictionary is generated, **then** the committed dictionary matches it. Check: `tests/test_semantic_layer.py::test_generated_dictionary_matches_the_contract`.

## US-10 Dashboards that match the warehouse

**As a** Executive, **I want** every number on a dashboard to come from the warehouse, **so that** I can quote it without re-checking.

- **Given** the offline dashboard, **when** each measure is compared with warehouse SQL, **then** all measures tie. Check: `tests/dashboard/test_dashboard.py::test_every_dashboard_measure_ties_to_the_warehouse`; evidence `dashboard/validation_evidence.csv`.
- **Given** the Tableau package, **when** every expected KPI is queried from its Hyper extract, **then** all values match; and a changed expectation fails the check. Check: `tests/test_tableau_package.py::test_tieout_passes_and_detects_drift`.
- **Given** a tampered dashboard payload, **when** validation runs, **then** it fails. Check: `tests/dashboard/test_dashboard.py::test_validation_detects_a_tampered_dashboard_payload`.

## US-11 An Excel workbook finance can drive

**As a** Finance analyst, **I want** a workbook with live formulas and protected structure, **so that** I can test scenarios without breaking the reconciliation.

- **Given** the workbook, **when** cells are inspected, **then** only the shaded scenario inputs are editable and every sheet is protected. Check: `tests/test_excel_workbook.py::test_only_scenario_inputs_are_editable`.
- **Given** the workbook, **when** scenario inputs change, **then** the outputs recompute from those inputs and the baseline is unchanged. Check: `tests/modeling/test_forecast.py::test_scenario_math_is_explicit_and_baseline_unchanged`.
- **Given** the Control sheet, **when** it is opened, **then** it shows refresh time, source commit, reconciliation status and the data caveat. Check: `tests/test_excel_workbook.py::test_control_records_refresh_commit_status_and_caveat`.

## US-12 Refuse bad source data

**As a** Data owner, **I want** impossible records rejected at the source, **so that** a broken extract cannot reach a metric.

- **Given** duplicated subscription events, refunds above payments, currency mismatches or overlapping contracts, **when** source validation runs, **then** each is detected. Checks: `tests/test_adversarial_sources.py::test_duplicated_subscription_events`, `tests/test_adversarial_sources.py::test_refund_exceeding_payment`, `tests/test_adversarial_sources.py::test_currency_mismatch_between_invoice_and_subscription`, `tests/test_adversarial_sources.py::test_overlapping_contract_dates`.
- **Given** a clean generated dataset, **when** the same validation runs, **then** it passes. Check: `tests/test_adversarial_sources.py::test_clean_dataset_passes`.

## US-13 Reproducible runs

**As a** Data owner, **I want** every run reproducible and recorded, **so that** a number can be traced back to the code and data that produced it.

- **Given** a fixed seed, **when** generation runs twice, **then** the output is identical and valid. Check: `tests/test_generation.py::test_generation_is_reproducible_and_valid`.
- **Given** a completed run, **when** the audit closes, **then** artifacts are versioned with their hashes recorded and a failure marks the run failed. Checks: `tests/modeling/test_diagnostics.py::test_run_artifacts_are_versioned_and_hash_recorded`, `tests/test_run_audit.py::test_close_run_marks_any_failure_failed`.

## US-14 No personal data in published extracts

**As a** Data owner, **I want** published extracts limited to aggregates and synthetic identifiers, **so that** the same habit holds if this pipeline is ever pointed at customer data that is not synthetic.

- **Given** any Tableau extract, **when** its columns are inspected, **then** no customer or account name and no contact field is present. Check: `tests/test_tableau_package.py::test_extracts_carry_no_personal_fields`.
- **Given** the README, **when** its claims are read, **then** the data is labeled synthetic and no business impact is claimed. Check: `tests/test_tableau_package.py::test_readme_labels_the_data_synthetic_and_claims_no_impact`.
