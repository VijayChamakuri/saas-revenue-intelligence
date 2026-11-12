# Technical Report

## Verified implementation

Python generates and validates deterministic source records. DuckDB provides the tested local warehouse. Contract views isolate source names from dbt, which owns staging, intermediate logic, star-schema dimensions, MRR movements, revenue KPIs, growth marts, finance reconciliation, and exceptions. Python implements calibrated churn modeling and rolling-origin forecasts. Spark, Hive-compatible DDL, R, and Airflow were executed locally. Power BI remains a specification with an explicit native-runtime boundary.

## Reproducibility record

| Evidence | Value |
|---|---|
| Git state | Working tree at verification; the resulting commit is recorded in public repository history |
| Generator | Seed `20260831`; config SHA-256 `3dca59977a0ff9ea459eb1c6385e488e216f84ac2027fe163eaa061e00b155b3` |
| Observation window | 2023-01-01 through 2025-12-31 |
| Runtime | Python 3.13.14, DuckDB 1.5.5, dbt Core 1.12.3, dbt-duckdb 1.11.0 |
| Host | Apple arm64 macOS, 10 logical CPUs, 16 GiB memory |
| Scale | 693,805 source and modeling rows; 600,000-event CSV is 33,944,898 bytes |

## Transformation and quality evidence

Source contracts passed for all 23 files, including schemas, keys, date ordering, range constraints, and 25 cross-table relationships. dbt parses 37 models. Three intermediate models are ephemeral, so `dbt build` runs 114 resources: 34 models and 80 data tests, all passing. Source freshness passes for all 22 dbt sources. No incremental equivalence benchmark is claimed.

## Revenue and finance validation

The 36-month MRR bridge enforces `closing = opening + new + expansion + reactivation - contraction - churn`. Maximum absolute variance is $0.00. The finance exception mart detects 969 contract-date conflicts. Failed-payment exposure totals $1,461,681.54 across 638 attempts. These conditions are generated simulation evidence, not real accounting errors or losses.

## Churn modeling

The modeling contract is one account snapshot per as-of date with a 90-day future churn label. Identifiers and post-outcome fields are excluded. Ex-ante latent account characteristics generate both behavior and later cancellation, so predictors never read the realized future outcome or cancellation timing. The generator also introduces missing and delayed observations, temporal drift, label noise, and unseen future conditions. Splits contain 2,122 training, 1,587 calibration, and 3,057 future test rows. Calibrated logistic regression reaches 0.633 ROC-AUC, 0.031 PR-AUC, and a Brier score of 0.0186. The boosting challenger reaches 0.502 ROC-AUC and 0.020 PR-AUC. Economics assume a $35 contact cost, $6,000 retained margin, and 18% intervention success. The modest precision reflects the low event rate and is disclosed rather than hidden.

## Forecasting and statistical validation

Forecast code compares naive, seasonal-naive, and drift methods with rolling-origin backtesting, then labels forecasts and scenarios separately. R analyzed 1,004 customer spells with 248 churn events and produced Cox concordance of 0.6246. Payment, support, and health covariates are restricted to records on or before each spell's event or censor date. Its 57 Kaplan-Meier estimates matched the independent Python calculation within `4.45e-16`.

## Spark and orchestration

PySpark 3.5.9 processed the 600,000-event CSV in 5.984 seconds using `local[*]`, produced 481,716 account-day rows across 36 year/month partitions, and reconciled the event total through the included Hive-compatible DDL. Airflow 2.11.2 successfully executed a local `dags test` across generation, validation, Spark, load, dbt, analytics, export, and monitoring. This is local runtime evidence, not a production scheduler or big-data performance claim.

## BI verification

Eight BI-ready extracts were generated, including 18,596 MRR movement rows, 17,348 billing-reconciliation rows, 969 finance-exception rows, and a 36-month forecast input. The repository includes an eight-page Power BI design, semantic model, 39-measure DAX library, and QA checklist. Power BI Desktop is unavailable on macOS, so native refresh, interactions, accessibility, screenshots, and `.pbix` delivery remain unverified. No screenshot or native report is fabricated.

## Residual limitations

The project uses synthetic data and cannot substantiate production impact, causal effects, audited accounting compliance, cloud performance, or production security readiness. BigQuery was not compiled. The Tableau workbook is generated from the marts and tied to them (288 of 288 KPI values). There is no Power BI file.
