# Metric catalog and backlog

## Governance conventions

The SQL references below define the governed target state. The current executable release implements and tests the MRR movement bridge, ARR, net new MRR, GRR, NRR, billing reconciliation, finance exceptions, customer-month health inputs, and channel efficiency. Other rows are explicitly backlog definitions and must not be interpreted as implemented marts. The test-reference column states the test required before a backlog metric can be promoted to trusted status. Currency metrics use reporting currency unless explicitly labeled otherwise.

## Revenue metrics

| Metric | Business definition and target SQL | Grain | Owner | Inclusion and exclusion rules | Implemented or required test | Limitation |
|---|---|---|---|---|---|---|
| MRR | Normalized recurring subscription value at month end. `SUM(closing_mrr)` from `mart_mrr_movement` | month and allowed slices | RevOps | active recurring lines; excludes tax, fees, one-time services, trials | `assert_mrr_nonnegative`; `assert_mrr_snapshot_ties_subscription` | Contract value may differ from billed timing |
| ARR | Run-rate recurring value. `12 * MRR` | month and slices | RevOps | same as MRR | `assert_arr_equals_12_mrr` | Not GAAP revenue or contracted backlog |
| New MRR | Closing MRR from accounts with no prior paid recurring state. `SUM(CASE movement_type WHEN 'new' THEN movement_mrr END)` | account-product-month | RevOps | first paid activation | `assert_movement_type_exclusive`; bridge test | Definition depends on account identity resolution |
| Expansion MRR | Positive increase for a continuing recurring relationship | account-product-month | RevOps | upgrades and seat expansion; excludes reactivation | movement sign and bridge tests | Price and volume effects may require deeper decomposition |
| Contraction MRR | Absolute negative decrease while recurring relationship remains active | account-product-month | RevOps | downgrades and seat contraction | movement sign and bridge tests | Does not represent full logo churn |
| Churned MRR | Absolute opening MRR lost when relationship becomes inactive | account-product-month | Customer Success | paid recurring value only | movement sign and bridge tests | Product-level churn can coexist with account retention |
| Reactivation MRR | Closing MRR after at least one inactive paid month | account-product-month | RevOps | requires prior paid state and gap | reactivation-history test | Sensitive to observation-window start |
| Net new MRR | `new + expansion + reactivation - contraction - churned` | month and slices | RevOps | completed periods | `assert_net_new_components`; bridge test | Same limitations as components |
| GRR | `(opening MRR - contraction - churned) / opening MRR` | cohort or period | Customer Success | starting recurring base; caps expansion benefit at zero | bounds test; numerator-component test | Mix changes affect comparisons |
| NRR | `(opening MRR + expansion + reactivation - contraction - churned) / opening MRR` | cohort or period | RevOps | starting base; reactivation policy documented | numerator-component test | Can exceed 100 percent; small cohorts are volatile |
| ARPA | `SUM(closing_mrr) / COUNT(DISTINCT active_account_id)` | month and slices | Finance | active paid accounts | denominator and weighted-total test | Account structure affects comparability |
| Recognized revenue | Revenue allocated to accounting period from eligible invoice lines | accounting period and line | Finance | excludes tax and refundable deposits; follows service period | schedule-to-line tie-out | Illustrative policy, not audited GAAP conclusion |
| Deferred revenue | Eligible billed amount not yet recognized at period end | account-period | Finance | billed service not delivered; net of eligible adjustments | roll-forward and nonnegative tests | Simplifies contract modifications |
| Collected cash | Settled payments less settled refunds in period | payment date and slices | Finance | successful settlements only | payment-refund tie-out | Excludes processor timing outside data window |
| Failed-payment exposure | Open recurring invoice amount associated with latest failed attempt | invoice-period | Finance | unpaid or partially paid recurring invoices; avoids duplicate attempts | invoice uniqueness and amount ceiling tests | Exposure is not certain loss |
| Refund rate | `refunded amount / settled payment amount` | period and slices | Finance | comparable settled payments; zero denominator returns null | bounds and denominator tests | Timing differences can distort short periods |
| Discount leakage | Discount beyond policy or lacking valid approval, measured against list price | invoice line | Finance | eligible recurring lines; flagged policy exceptions | policy threshold and approval tests | Estimated counterfactual, not recoverable cash |

## Customer and unit-economics metrics

| Metric | Business definition and target SQL | Grain | Owner | Inclusion and exclusion rules | Implemented or required test | Limitation |
|---|---|---|---|---|---|---|
| Logo churn | churned starting accounts divided by starting paid accounts | cohort-period | Customer Success | account inactive across all products at period end | bounds and starting-base tests | Does not weight revenue |
| Revenue churn | churned MRR divided by opening MRR | cohort-period | RevOps | full churn component only | bounds and component test | Excludes contraction by design |
| Renewal rate | renewed eligible contracts divided by contracts due for renewal | renewal period and slices | Customer Success | excludes not-yet-due and administrative replacements | bounds and eligibility tests | Renewal can occur with contraction |
| Cohort retention | retained logos or MRR divided by cohort starting value at month age | cohort-month age | Product Analytics | fixed cohort membership; logo and revenue variants separate | month-age uniqueness and month-zero tests | Recent cohorts have censored tails |
| CLV | Expected discounted contribution from an account using documented retention and margin assumptions | cohort or account estimate | Finance | paid customers; sensitivity ranges required | input completeness and monotonic sensitivity tests | Model-based estimate, not realized value |
| CAC | Eligible acquisition spend divided by newly acquired paid accounts | channel-cohort | Marketing | defined attribution window; includes stated sales cost policy | spend and denominator tie-outs | Attribution and shared cost allocation are assumptions |
| LTV:CAC | gross-margin-adjusted CLV divided by CAC | channel-cohort | Finance | comparable acquisition cohorts only | ratio recomputation test | Inherits both estimates' uncertainty |
| CAC payback | acquisition cost divided by expected monthly contribution margin | channel-cohort | Marketing | positive contribution only | recomputation and null-policy tests | Ignores timing variation within cohort |
| Customer health score | weighted, normalized payment, usage, adoption, support, and renewal components | account-score date | Customer Success | features available as of score date; score 0 to 100 | bounds, component, and as-of tests | Operational heuristic, not causal probability |
| Support burden | weighted tickets or support hours per active account or recurring revenue unit | account-period | Customer Success | valid resolved and open tickets; weighting documented | nonnegative and denominator tests | Synthetic effort proxy may simplify real staffing |
| Feature adoption | eligible key features used divided by eligible key features | account-product-period | Product | requires minimum activity and valid feature catalog | bounds and feature-eligibility tests | Breadth does not measure depth or value |
| Time to value | days from activation to first defined value event | account-product | Product | converted paid accounts; censored if not reached | nonnegative chronology test | Value event is a documented proxy |

## Sales and marketing metrics

| Metric | Business definition and target SQL | Grain | Owner | Inclusion and exclusion rules | Implemented or required test | Limitation |
|---|---|---|---|---|---|---|
| Lead-to-opportunity conversion | leads creating a qualified opportunity divided by eligible leads | channel-cohort | Marketing | deduplicated leads within attribution window | funnel bounds and chronology tests | Lead identity and attribution can be ambiguous |
| Opportunity-to-win conversion | closed-won opportunities divided by closed opportunities | close period and slices | Sales | excludes open opportunities | bounds and status tests | Does not adjust for deal-size mix |
| Sales-cycle length | days from opportunity creation to closed-won date | won opportunity | Sales | won deals with valid timestamps | nonnegative chronology test | Excludes unresolved open pipeline |
| Pipeline coverage | open weighted or unweighted pipeline divided by target for horizon | period, team | RevOps | eligible stages and target period | amount and target-presence tests | Depends on CRM hygiene and probability policy |
| Win rate | won value or count divided by closed value or count, variant labeled | period and slices | Sales | closed outcomes only | bounds and variant-label tests | Count and value variants answer different questions |
| Acquisition cost by channel | eligible acquisition spend divided by new paid accounts attributed to channel | channel-cohort | Marketing | documented first-touch policy and window | spend-to-source and denominator tests | Multi-touch influence is simplified |
| Revenue and retention by channel | MRR, NRR, and logo retention grouped by acquisition channel | channel-cohort-period | Marketing | fixed acquisition channel; mature cohorts flagged | aggregate tie-out and cohort tests | Channel selection may correlate with customer mix |
| Marketing return | attributable gross-margin value less eligible spend, divided by spend | channel-horizon-scenario | Marketing | labels modeled attribution and horizon assumptions | recomputation and scenario-label tests | Scenario estimate, not causal return |

## Required metric test pattern

Each implemented metric must have at least one explicit dbt test named in model YAML or `tests/`, a documented owner, and a queryable reconciliation field. Ratio metrics return null for zero denominators rather than zero. Aggregate totals are computed from additive numerators and denominators, never as unweighted averages of displayed percentages.
