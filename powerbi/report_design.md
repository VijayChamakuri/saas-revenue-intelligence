> **Status:** roadmap specification. Only the Executive Overview, Revenue & Retention, Customer Risk and Finance Controls pages are built, in [`dashboard/index.html`](../dashboard/index.html). Other pages described here have no tested marts yet and are not shown anywhere.

# Eight-Page Report Design

## Global design system

Use a restrained, color-blind-safe palette. Blue communicates neutral actuals, teal positive movement, orange risk, red confirmed exceptions, and gray context. Color never carries meaning alone. All pages show the selected period, active filters, last refresh, metric-definition tooltip, and actual versus forecast or scenario status. Slicers are limited to decisions: period, segment, plan, product, geography, channel, and contract type.

## 1. Executive overview

Question: Where is performance changing, why, and where does leadership need attention?

- KPI cards: MRR, ARR, net new MRR, NRR, GRR, active accounts, collected cash, open exception amount.
- MRR trend with prior-year or prior-period comparison.
- Compact movement waterfall.
- Retention and risk callout by largest exposed segment.
- Forecast range with actuals visually distinct.
- A maximum of five recommendation cards, populated only from verified report outputs.
- Drill-through from segment and recommendation evidence to the relevant operational page.

## 2. MRR and ARR movement

Question: Which accounts, products, plans, and movement types explain recurring revenue change?

- Opening-to-closing waterfall with bridge variance indicator.
- Movement trend by month.
- Decomposition tree by segment, product, plan, channel, and geography.
- Account-level matrix with opening, movement components, closing, and event evidence.
- Drill-through to synthetic account history.

## 3. Retention and cohorts

Question: Which cohorts retain logos and revenue, and what behavior differs?

- Separate logo and revenue cohort heatmaps.
- Retention curve by selected cohort dimension with cohort-size context.
- NRR and GRR by month age.
- Time-to-value distribution and feature adoption comparison.
- Small-cohort warning and right-censoring tooltip.

## 4. Customer health and churn risk

Question: Which accounts should Customer Success prioritize, and why?

- High-risk accounts and MRR exposure cards.
- Calibrated risk distribution with chosen intervention threshold.
- Prioritization matrix: predicted risk versus MRR or renewal proximity.
- Account queue with risk drivers, health components, renewal date, failed payment, support, and usage trends.
- Model performance panel: precision, recall, ROC-AUC, PR-AUC, calibration, lift, and validation window.
- Explainability is associative and never phrased as causal.

## 5. Sales and marketing efficiency

Question: Which channels and motions acquire durable, economically attractive customers?

- Funnel with lead-to-opportunity and opportunity-to-win conversion.
- CAC, gross-margin-adjusted LTV:CAC, payback, NRR, and retained revenue by channel.
- Sales-cycle distribution and pipeline coverage by team.
- Spend-allocation scenario with assumptions visible.
- Cohort maturity and attribution-policy tooltips.

## 6. Billing and revenue reconciliation

Question: Can Finance trace recurring activity through invoices, cash, refunds, recognition, and deferral?

- Tie-out cards for contract value, invoices, cash, refunds, recognized revenue, deferred revenue, MRR, and ARR.
- Reconciliation flow with variance amounts.
- Exception counts and amounts by rule and severity.
- Operational exception queue with record identifier and evidence.
- Drill-through to invoice, payment, contract, and revenue-schedule details.

## 7. Forecast and scenario planning

Question: What is the expected range, how accurate were candidate models, and how do stated assumptions change it?

- Actual plus selected forecast and interval.
- Rolling-backtest error comparison across methods.
- Separate scenario controls for churn, price, marketing allocation, expansion, discounts, and failed-payment recovery.
- Scenario delta waterfall and assumptions panel.
- Clear warning that scenario opportunity is modeled, not realized.

## 8. Data quality and metric trust

Question: Which metrics are certified for this refresh and what needs investigation?

- Trust status, last refresh, freshness, test pass rate, and reconciliation status.
- Failed tests and exception trend by severity and owner.
- Source-to-target freshness matrix.
- Metric dictionary browser with definition, owner, grain, rules, and limitations.
- Lineage navigation or link to generated dbt docs.

## Interaction standards

Visual interactions are intentional and documented. Decorative charts do not cross-filter. Tooltips disclose denominators, cohort size, currency, comparison basis, and last completed period. Empty states say why data is absent and suggest a valid filter change. Dynamic titles repeat the metric variant and selected scope.
