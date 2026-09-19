# Dashboard

`dashboard/index.html` is a single offline file (about 2 MB, no network calls) with four pages. It is built from the
tested dbt marts by `make dashboard`, and every number on it is tied back to the warehouse.

| Page | Question it answers |
|---|---|
| Executive Overview | Did revenue grow, and what changed this month? |
| Revenue & Retention | Which segments, plans, products, cohorts and accounts moved MRR? |
| Customer Risk | Which accounts should Customer Success contact, and how good is the score? |
| Finance Controls | Do invoices, payments, refunds and revenue tie out, and what is in the exception queue? |

Screenshots: [executive](../dashboard/screenshots/01_executive.png),
[revenue](../dashboard/screenshots/02_revenue_retention.png),
[risk](../dashboard/screenshots/03_customer_risk.png),
[finance](../dashboard/screenshots/04_finance_controls.png).

## Labels

Every panel is tagged as an **Observed dataset fact**, a **Model estimate**, a **Scenario** or a **Recommendation**.
Scenario economics never share a chart with actuals.

## How the numbers are verified

`make dashboard` runs `src/dashboard/validate.py`. It evaluates the dashboard's own measure code
(`dashboard/measures.js`) in Node under default and filtered states, recomputes each value from warehouse SQL or
pandas, and writes [`dashboard/validation_evidence.csv`](../dashboard/validation_evidence.csv) with the page,
measure, filter, warehouse total, report total, variance, tolerance and status. Any failure exits non-zero and fails
CI. A tamper test proves the check fails when a number is wrong.

## Power BI

No `.pbix` is included. Power BI Desktop runs only on Windows and this repository was built on macOS, so a
Power BI report would have been unverified. The [`powerbi/`](../powerbi/) folder holds the semantic-model and DAX
specification. To build the report, run `make dashboard-export`, import the CSVs in `data/exports/`, and use
`powerbi/measures.dax` with the four pages above.
