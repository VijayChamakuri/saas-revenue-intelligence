# Implementation Status and Extended Stack

The core analyst path is SQL, dbt, DuckDB, Python and the offline dashboard, run by `make pipeline`. Spark, Hive, Airflow and R are an optional extended implementation: they show the same logic running on other engines and are not needed to reproduce any headline result.

## Technology responsibilities

| Technology | Nonduplicative responsibility |
|---|---|
| SQL and dbt | Primary transformation language, metric logic, lineage, documentation, and tests |
| Python | Synthetic generation, contracts, loading, modeling, forecasting, exports, and automation |
| PySpark | High-volume product-event aggregation and partitioned Parquet output |
| DuckDB | Tested local warehouse and reproducible fallback |
| Airflow | Pipeline dependency graph from generation through monitoring |
| R | Independent Kaplan-Meier and Cox proportional-hazards implementation |
| Power BI and DAX | Report and semantic-model specification, not a completed native report |
| GitHub Actions | Automated Python, SQL, and dbt validation |

BigQuery is the intended cloud warehouse path when credentials are available. This repository does not claim an untested cloud deployment.

## Proof of work

This repository contains executable evidence for the critical business logic:

| Capability | Implementation | Verification |
|---|---|---|
| Reproducible synthetic system | [`src/generation/generate.py`](src/generation/generate.py) | Fixed seed, source manifest, generation tests |
| Source contracts | [`src/validation/validate_sources.py`](src/validation/validate_sources.py) | Schemas, keys, dates, ranges, and 25 relationships across all 23 sources |
| MRR movement classification | [`fct_mrr_movement.sql`](dbt/models/marts/revenue/fct_mrr_movement.sql) | Movement exclusivity, uniqueness, nonnegative balances |
| MRR roll-forward | [`mart_mrr_bridge.sql`](dbt/models/marts/revenue/mart_mrr_bridge.sql) | Maximum difference equals $0.00 |
| Billing reconciliation | [`fct_billing_reconciliation.sql`](dbt/models/marts/finance/fct_billing_reconciliation.sql) | Invoice arithmetic and recognition tests |
| Exception detection | [`mart_finance_exceptions.sql`](dbt/models/marts/finance/mart_finance_exceptions.sql) | Tested types, severities, and non-null invoice keys |
| Failed-payment exposure | [`assert_failed_payment_exposure_quantified.sql`](dbt/tests/assert_failed_payment_exposure_quantified.sql) | Nonzero exposure required when failed attempts exist |
| Leakage-safe churn modeling | [`src/modeling/churn.py`](src/modeling/churn.py) | Time splits, calibration, lift, Brier score, and threshold economics |
| Rolling forecast backtests | [`src/modeling/forecast.py`](src/modeling/forecast.py) | Naive, seasonal-naive, and drift candidates compared |
| Distributed-event path | [`spark/process_usage_events.py`](spark/process_usage_events.py) | 600,000 events processed in 5.984 seconds into 36 partitions |
| Hive compatibility | [`spark/validate_hive_table.py`](spark/validate_hive_table.py) | DDL loaded in Spark Hive support; 600,000 events reconciled |
| R survival analysis | [`r/survival_analysis.R`](r/survival_analysis.R) | 1,004 spells, 248 events; Kaplan-Meier output matches Python within 4.45e-16 |
| Orchestration | [`airflow/dags/subscription_intelligence.py`](airflow/dags/subscription_intelligence.py) | Local Airflow 2.11.2 DAG test completed successfully |
| BI semantic design | [`powerbi/semantic_model.md`](powerbi/semantic_model.md) | 39 explicit DAX measures and QA checklist |
| README evidence charts | [`scripts/generate_readme_visuals.py`](scripts/generate_readme_visuals.py) | Regenerated from tested exports and model artifacts |

## Optional extended runs

### Prerequisites

- Python 3.11 or 3.12
- [`uv`](https://docs.astral.sh/uv/)
- Git
- Java 11 or 17 for the optional Spark execution
- R and the `survival` package for the optional independent analysis

### Rebuild the README evidence

```bash
uv run python scripts/generate_readme_visuals.py
```

### Full Spark, Hive, and R verification

```bash
brew install openjdk@17 r
export JAVA_HOME="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
uv sync --extra spark --extra dev
make pipeline-full
```

### Local Airflow DAG test

```bash
export JAVA_HOME="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
export AIRFLOW_HOME="$(mktemp -d)"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
uv sync --extra airflow --extra spark --extra dev
uv run --extra airflow airflow db migrate
make airflow-test
```

## Verification summary

| Check | Result |
|---|---|
| dbt build | 114 of 114 resources passed (34 models, 80 tests) |
| Dashboard measures tied to the warehouse | 128 of 128 |
| MRR bridge maximum variance | $0.00 |
| Source contracts | 23 of 23 tables passed |
| Ruff, mypy | Clean |
| Python tests | 47 passed, 84% line coverage |
| CI | Python 3.11 and 3.12 matrix runs the same commands as `make pipeline` |
| Spark, Hive, R, Airflow | Local runs recorded in [reports/runtime_verification.md](../reports/runtime_verification.md); not part of CI |
| Power BI, BigQuery | Not executed; not claimed |

## Known limitations

- The project is synthetic and cannot substantiate causal or production impact.
- Multi-product lifecycle behavior, reactivation movements, and deferred-revenue schedules need further implementation.
- Several catalog metrics remain governed roadmap definitions rather than tested marts.
- The Airflow evidence is a successful local DAG test, not a long-running production scheduler deployment.
- BigQuery and native Power BI behavior were not validated on this host.

See [limitations and ethics](docs/limitations_and_ethics.md) and the [technical report](reports/technical_report.md) for the complete disclosure.

## BI upgrade (2026-09-19)

| Item | Status | Evidence |
|---|---|---|
| Canonical metric contract with mart tie-outs | Met (portable contract, not MetricFlow) | `metrics/semantic_layer.yml`; 361 of 361 metric-months tie; `tests/test_semantic_layer.py` |
| MRR bridge variance exactly $0 every month | Met | `test_mrr_bridge_variance_is_exactly_zero_every_month` |
| Excel tables, filters, protection, input styling, Control, PDF | Met | `tests/test_excel_workbook.py`; `reports/finance_control_summary.pdf` |
| Real Tableau workbook with four checked dashboards and a Tableau Public URL | Met | Generated `.twbx` opens with no errors; 288 of 288 KPI tie-outs; all four dashboards inspected and fixed; screenshots in `tableau/screenshots/`; published at https://public.tableau.com/app/profile/vijay.chamakuri/viz/SaaSRevenueIntelligenceMRRRetentionBillingControls/Executiveoverview. |
| Cloud-warehouse portability (P1) | Not done | No BigQuery or Snowflake profile; nothing is claimed. |
