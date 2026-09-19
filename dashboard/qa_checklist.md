# Dashboard QA Checklist

Scope: `dashboard/index.html`, the four-page offline dashboard. The Power BI specification in `powerbi/` has its own
checklist and is not claimed complete. Status is `Pass` only where the evidence column names a check that was run.
`Not applicable` items are explained.

## Totals and measures

| Item | Status | Evidence |
|---|---|---|
| All displayed measures tie to the warehouse | Pass | `validation_evidence.csv`: 128 of 128 cases, status `pass` |
| MRR bridge variance is within one cent at total and sliced levels | Pass | `bridge_variance` cases for six filter states |
| Percentages recompute from numerator and denominator, not averaged rows | Pass | NRR, GRR and cohort ratios validated per filter state |
| All calculations are explicit, reusable measures | Pass | `dashboard/measures.js`, no inline arithmetic on rows in `app.js` |
| Month-end balances use the month value, not summed daily values | Pass | `closing_mrr` is one row per month in `mart_mrr_bridge` |
| The check fails when a number is wrong | Pass | `test_validation_detects_a_tampered_dashboard_payload` |

## Filters and interactions

| Item | Status | Evidence |
|---|---|---|
| Slicers change only intended content | Pass | Segment, plan and product filters checked in a browser; Finance cards stay unchanged when revenue filters change |
| Reset restores the default state | Pass | Browser check |
| Drill-through narrows the page and can be cleared | Pass | Account link sets the customer filter; reset clears it |
| Incompatible filters show a clear empty state | Pass | Customer with no MRR in an earlier month, and a rule with no exceptions |
| Source-record drill-through | Pass | Invoice drawer shows the full record; Escape closes it |
| Synchronized slicers across pages | Not applicable | Month is the only shared control and persists across pages |
| Tooltip pages | Not applicable | Native SVG titles are used instead |

## Date and scenario logic

| Item | Status | Evidence |
|---|---|---|
| Actual, model and scenario values are never combined | Pass | Every panel carries a fact, model, scenario or recommendation tag; scenario economics sit in their own panel |
| Prior-period comparison excludes incomplete periods | Pass | First month shows "no prior period" instead of a comparison |
| Forecast intervals and scenario controls | Not applicable | The dashboard shows no forecast. Forecasts stay in `artifacts/forecast` and are point estimates |

## Usability and accessibility

| Item | Status | Evidence |
|---|---|---|
| Keyboard navigation between pages | Pass | Arrow keys move between tabs and focus follows; verified in a browser |
| Focus is managed for the record drawer | Pass | Focus moves to Close, Escape closes |
| Charts have text alternatives | Pass | Each chart is `role="img"` with an `aria-label`; tables carry the same values |
| Color is not the only carrier of meaning | Pass | Legends and labels, values in tables beside charts |
| Dark and light themes | Pass | Screenshots captured in light; dark checked in a browser |
| No horizontal page overflow at 375 px | Pass | Measured `scrollWidth` equals viewport width |
| Last refresh and data status visible | Pass | Header states the data month and that the data is synthetic |

## Operational review

| Item | Status | Evidence |
|---|---|---|
| Finance, RevOps, Customer Success and Marketing sign-off | Not applicable | No reviewers exist for a synthetic portfolio project |
| Second reviewer with adversarial filter states | Not applicable | Adversarial states are covered by the validation cases and browser checks above |
