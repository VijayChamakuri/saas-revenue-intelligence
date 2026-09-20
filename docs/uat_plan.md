# User acceptance test plan

All project data is synthetic. Outputs describe patterns detected in the generated dataset, not real company outcomes.

Acceptance scenarios for the personas in the [stakeholder question map](stakeholder_question_map.md). Each maps to a check that already runs, so acceptance is re-provable on every build. Actors are documented personas, not people who were interviewed.

| ID | Actor | Business scenario | Preconditions | Steps | Expected result | Automated evidence |
|---|---|---|---|---|---|---|
| UAT-01 | Executive | Explain why recurring revenue changed last month | Pipeline run complete | Open the Tableau Executive overview, select the latest month, read the bridge and tiles | Components sum to closing MRR; tiles equal the marts | `tests/test_semantic_layer.py::test_mrr_bridge_variance_is_exactly_zero_every_month`, `tableau/validation_evidence.csv` |
| UAT-02 | Finance | Close the month against billing and cash | Pipeline run complete | Open `excel/finance_reconciliation.xlsx`, read Control, then Billing Reconciliation | Control shows ALL CHECKS PASS with refresh time and source commit; every month reconciles | `tests/test_excel_workbook.py::test_control_records_refresh_commit_status_and_caveat` |
| UAT-03 | Finance | Work billing exceptions in priority order | Pipeline run complete | Open Finance controls, select an exception class, read the invoice list | Only that class lists; each invoice counted once per rule | `tests/dashboard/test_dashboard.py::test_exception_exposure_counts_each_invoice_once` |
| UAT-04 | Finance | Size failed-payment exposure | Pipeline run complete | Read the failed-payment exposure tile and monthly trend | Exposure is quantified, never negative, and matches the mart | dbt `assert_failed_payment_exposure_quantified` |
| UAT-05 | RevOps | Compare retention across segments and plans | Pipeline run complete | Open Revenue and retention; apply plan, channel and year filters | GRR stays within 0 to 1, NRR within 0 to 2, values tie to the marts | `tests/test_semantic_layer.py::test_every_metric_ties_to_its_mart_and_stays_in_bounds` |
| UAT-06 | Customer Success | Decide how many accounts to contact | Model artifacts present | Open Customer risk, move the threshold, read precision, recall and queue size | The three move together and the page says prioritization aid, not automated action | `tests/modeling/test_diagnostics.py::test_threshold_sensitivity_economics_are_explicit` |
| UAT-07 | Marketing | Judge a channel on retained revenue | Pipeline run complete | Read cohort logo retention and channel efficiency | Every cohort starts at full retention; every customer is in exactly one cohort | dbt `assert_cohort_starts_at_full_retention`, dbt `assert_cohorts_cover_all_customers` |
| UAT-08 | Data owner | Refuse a release when sources are broken | Fixture inputs | Inject a duplicate subscription event and a refund above its payment, then run validation | Both are detected and the run fails | `tests/test_adversarial_sources.py::test_duplicated_subscription_events`, `tests/test_adversarial_sources.py::test_refund_exceeding_payment` |
| UAT-09 | Data owner | Detect a tampered dashboard number | Dashboard built | Alter a value in the dashboard payload and rerun validation | Validation fails and names the measure | `tests/dashboard/test_dashboard.py::test_validation_detects_a_tampered_dashboard_payload` |
| UAT-10 | Data owner | Detect drift between Tableau and the warehouse | Tableau package built | Change an expected KPI value and rerun the tie-out | The tie-out fails | `tests/test_tableau_package.py::test_tieout_passes_and_detects_drift` |
| UAT-11 | Data owner | Confirm no personal data is published | Tableau package built | Inspect the columns of every extract | No customer or account name, no contact field | `tests/test_tableau_package.py::test_extracts_carry_no_personal_fields` |
| UAT-12 | Product | Check that adoption analysis is time-safe | Model artifacts present | Review the split and leakage checks behind the health features | Train, calibration and test windows do not overlap; no post-label feature is used | `tests/modeling/test_churn.py::test_temporal_split_has_no_overlap`, dbt `assert_no_temporal_health_leakage` |

## Exit criteria

All twelve scenarios pass under `make pipeline`, and GitHub Actions is green on Python 3.11 and 3.12. A failing scenario blocks release of the affected metric.
