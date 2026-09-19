# Metric dictionary

> Synthetic data from a seeded generator. Not real company, customer or financial results.

Generated from `metrics/semantic_layer.yml` (contract version 1) by `python -m src.validation.semantic_layer`. That file is a portable metric contract shaped like a dbt Semantic Layer spec; it is validated against the marts by this project, not executed by MetricFlow. The broader catalog, including backlog definitions, is in [metric_backlog.md](metric_backlog.md) and `dbt/metrics.yml`. Change rules: [metric governance](metric_governance.md).

## Ending MRR

- **ID and version:** `ending_mrr` v1 (headline KPI)
- **Business question:** How much recurring revenue is active at the end of the month?
- **Owner role:** Revenue Operations
- **Description:** Monthly recurring revenue active at month end.
- **Grain:** month
- **Source model:** `fct_mrr_movement` (semantic model `customer_month_revenue`)
- **Calculation:** `sum(closing_mrr)`
- **Numerator:** sum of closing MRR
- **Denominator:** none
- **Inclusions:** active recurring subscription lines
- **Exclusions:** one-time fees, taxes, refunds
- **Valid dimensions:** month, segment, plan_name, acquisition_channel
- **Time basis:** calendar month of the MRR snapshot
- **Refresh expectation:** rebuilt from the seeded generator on every pipeline run
- **Quality checks:** assert_mrr_bridge_rolls_forward, mart_mrr_bridge cents_close
- **Tie-out:** `analytics_revenue.mart_revenue_kpis.closing_mrr`
- **Known limits:** Contract value can differ from billed timing.

## ARR

- **ID and version:** `arr` v1
- **Business question:** What is the annualized recurring run rate?
- **Owner role:** Finance
- **Description:** Ending MRR times 12.
- **Grain:** month
- **Source model:** `fct_mrr_movement` (semantic model `customer_month_revenue`)
- **Calculation:** `ending_mrr * 12`
- **Numerator:** ending MRR times 12
- **Denominator:** none
- **Inclusions:** same as ending MRR
- **Exclusions:** same as ending MRR
- **Valid dimensions:** month, segment, plan_name
- **Time basis:** calendar month
- **Refresh expectation:** every pipeline run
- **Quality checks:** mart_revenue_kpis arr non_negative
- **Tie-out:** `analytics_revenue.mart_revenue_kpis.arr`
- **Known limits:** A run rate, not GAAP revenue or contracted backlog.

## Net new MRR

- **ID and version:** `net_new_mrr` v1 (headline KPI)
- **Business question:** Did recurring revenue grow or shrink this month, and why?
- **Owner role:** Finance
- **Description:** New plus expansion plus reactivation, less contraction and churned MRR.
- **Grain:** month
- **Source model:** `fct_mrr_movement` (semantic model `customer_month_revenue`)
- **Calculation:** `new_mrr + expansion_mrr + reactivation_mrr - contraction_mrr - churned_mrr`
- **Numerator:** movement components
- **Denominator:** none
- **Inclusions:** every customer-product-plan movement in the month
- **Exclusions:** one-time fees
- **Valid dimensions:** month, segment, plan_name, acquisition_channel
- **Time basis:** calendar month
- **Refresh expectation:** every pipeline run
- **Quality checks:** assert_mrr_bridge_rolls_forward, mart_mrr_bridge cents_close
- **Tie-out:** `analytics_revenue.mart_revenue_kpis.net_new_mrr`
- **Known limits:** A movement metric, not recognized revenue.

## Gross revenue retention

- **ID and version:** `gross_revenue_retention` v1 (headline KPI)
- **Business question:** How much of last month's recurring revenue did we keep before expansion?
- **Owner role:** Customer Success
- **Description:** Opening MRR less contraction and churned MRR, divided by opening MRR.
- **Grain:** month
- **Source model:** `fct_mrr_movement` (semantic model `customer_month_revenue`)
- **Calculation:** `(opening_mrr - contraction_mrr - churned_mrr) / opening_mrr`
- **Numerator:** opening MRR less contraction and churned MRR
- **Denominator:** opening MRR (null when zero)
- **Inclusions:** customers with opening MRR
- **Exclusions:** new, expansion and reactivation MRR
- **Valid dimensions:** month, segment, plan_name
- **Time basis:** calendar month
- **Refresh expectation:** every pipeline run
- **Quality checks:** mart_revenue_kpis accepted_range 0 to 1
- **Tie-out:** `analytics_revenue.mart_revenue_kpis.gross_revenue_retention`
- **Known limits:** Undefined when opening MRR is zero; mix changes affect comparisons.

## Net revenue retention

- **ID and version:** `net_revenue_retention` v1 (headline KPI)
- **Business question:** Including expansion, how much of last month's recurring revenue do we have now?
- **Owner role:** Revenue Operations
- **Description:** Opening MRR plus expansion and reactivation, less contraction and churned MRR, divided by opening MRR.
- **Grain:** month
- **Source model:** `fct_mrr_movement` (semantic model `customer_month_revenue`)
- **Calculation:** `(opening_mrr + expansion_mrr + reactivation_mrr - contraction_mrr - churned_mrr) / opening_mrr`
- **Numerator:** opening MRR plus expansion and reactivation, less contraction and churn
- **Denominator:** opening MRR (null when zero)
- **Inclusions:** customers with opening MRR
- **Exclusions:** new MRR
- **Valid dimensions:** month, segment, plan_name
- **Time basis:** calendar month
- **Refresh expectation:** every pipeline run
- **Quality checks:** mart_revenue_kpis accepted_range 0 to 2
- **Tie-out:** `analytics_revenue.mart_revenue_kpis.net_revenue_retention`
- **Known limits:** Can exceed 100 percent; small bases are volatile.

## Active customers

- **ID and version:** `active_customers` v1 (headline KPI)
- **Business question:** How many customers pay recurring revenue at month end?
- **Owner role:** Revenue Operations
- **Description:** Distinct customers with closing MRR above zero.
- **Grain:** month
- **Source model:** `fct_mrr_movement` (semantic model `customer_month_revenue`)
- **Calculation:** `count distinct customer_id where closing_mrr > 0`
- **Numerator:** customers with positive closing MRR
- **Denominator:** none
- **Inclusions:** customers with positive closing MRR on any product
- **Exclusions:** zero-MRR customers
- **Valid dimensions:** month, segment, plan_name, acquisition_channel
- **Time basis:** calendar month
- **Refresh expectation:** every pipeline run
- **Quality checks:** mart_revenue_kpis active_customers not_null
- **Tie-out:** `analytics_revenue.mart_revenue_kpis.active_customers`
- **Known limits:** Counts customers, not accounts; product-level churn can leave the customer active.

## Churned customers

- **ID and version:** `logo_churn` v1
- **Business question:** How many customers moved from positive MRR to zero this month?
- **Owner role:** Customer Success
- **Description:** Distinct customers with a churn movement in the month.
- **Grain:** month
- **Source model:** `fct_mrr_movement` (semantic model `customer_month_revenue`)
- **Calculation:** `count distinct customer_id where movement_type = 'churn'`
- **Numerator:** customers with a churn movement
- **Denominator:** none
- **Inclusions:** product-level churn rows
- **Exclusions:** partial contraction
- **Valid dimensions:** month, segment, plan_name
- **Time basis:** calendar month
- **Refresh expectation:** every pipeline run
- **Quality checks:** fct_mrr_movement movement_type accepted_values
- **Tie-out:** contract value is the reference; Tableau and Excel tie to it
- **Known limits:** 120 of 132 December 2025 cancellations are dated on the last day of the data window.

## Failed-payment exposure

- **ID and version:** `failed_payment_exposure` v1 (headline KPI)
- **Business question:** How much billed revenue is sitting on failed payment attempts?
- **Owner role:** Billing Operations
- **Description:** Invoice total on invoices whose payment attempts failed.
- **Grain:** invoice month
- **Source model:** `fct_billing_reconciliation` (semantic model `billing_reconciliation`)
- **Calculation:** `sum(failed_payment_exposure)`
- **Numerator:** failed-payment exposure
- **Denominator:** none
- **Inclusions:** invoices with a failed attempt and no successful payment
- **Exclusions:** successful attempts
- **Valid dimensions:** month, status, currency
- **Time basis:** invoice date month
- **Refresh expectation:** every pipeline run
- **Quality checks:** assert_failed_payment_exposure_quantified, fct_billing_reconciliation non_negative
- **Tie-out:** contract value is the reference; Tableau and Excel tie to it
- **Known limits:** Exposure is not certain loss; attempts can later recover.

## Billing reconciliation variance

- **ID and version:** `reconciliation_variance` v1 (headline KPI)
- **Business question:** Do invoices equal successful payments plus unpaid failed exposure?
- **Owner role:** Finance
- **Description:** Billed amount less successful payments less failed-payment exposure. Must be zero.
- **Grain:** invoice month
- **Source model:** `fct_billing_reconciliation` (semantic model `billing_reconciliation`)
- **Calculation:** `billed_amount - paid_amount - failed_payment_exposure`
- **Numerator:** billed less paid less unpaid exposure
- **Denominator:** none
- **Inclusions:** all invoices
- **Exclusions:** none
- **Valid dimensions:** month
- **Time basis:** invoice date month
- **Refresh expectation:** every pipeline run
- **Quality checks:** assert_invoice_arithmetic, Excel Billing Reconciliation tie-out
- **Tie-out:** contract value is the reference; Tableau and Excel tie to it
- **Known limits:** Partial payments are not modeled.

## Billed amount

- **ID and version:** `billed_amount` v1
- **Business question:** How much did we invoice?
- **Owner role:** Finance
- **Description:** Invoice totals including tax.
- **Grain:** invoice month
- **Source model:** `fct_billing_reconciliation` (semantic model `billing_reconciliation`)
- **Calculation:** `sum(total_amount)`
- **Numerator:** invoice totals
- **Denominator:** none
- **Inclusions:** all invoices
- **Exclusions:** none
- **Valid dimensions:** month, status, currency
- **Time basis:** invoice date month
- **Refresh expectation:** every pipeline run
- **Quality checks:** assert_invoice_arithmetic
- **Tie-out:** contract value is the reference; Tableau and Excel tie to it
- **Known limits:** Mixed-currency rows are exceptions until converted.

## Billing exceptions requiring review

- **ID and version:** `exception_count` v1 (headline KPI)
- **Business question:** How many invoice-rule violations are waiting for review?
- **Owner role:** Finance
- **Description:** Invoice and rule pairs in the finance exception queue.
- **Grain:** invoice and rule
- **Source model:** `mart_finance_exceptions` (semantic model `finance_exceptions`)
- **Calculation:** `count(*)`
- **Numerator:** exception rows
- **Denominator:** none
- **Inclusions:** every rule violation
- **Exclusions:** none
- **Valid dimensions:** exception_type, severity
- **Time basis:** not time-bound (queue at refresh)
- **Refresh expectation:** every pipeline run
- **Quality checks:** mart_finance_exceptions not_null
- **Tie-out:** contract value is the reference; Tableau and Excel tie to it
- **Known limits:** All 969 current exceptions trace to invoice dating in the generator.
