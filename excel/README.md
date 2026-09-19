# Finance Reconciliation Workbook

`finance_reconciliation.xlsx` is a review-friendly finance workbook generated from the tested dbt marts. It does
not redefine any canonical metric: warehouse values arrive as data, and every check, variance, retention ratio and
scenario output is a live Excel formula.

```bash
make excel      # writes excel/finance_reconciliation.xlsx
```

| Sheet | Purpose |
|---|---|
| Control | Run ID, export SHA-256 hashes, count of failed checks, overall status |
| MRR Bridge | Monthly bridge, roll-forward check, NRR, GRR, ARR |
| Billing Reconciliation | Invoiced = paid + unpaid; net cash; recognized + deferred = invoiced |
| Exceptions | Summary formulas over the full exception list |
| Scenario Inputs | Four shaded assumption cells, the only editable cells |
| Scenario Output | Simulated MRR and cash under the assumptions, labeled as scenario |
| Metric Definitions | Only metrics implemented in the marts |

## Verification

- `tests/test_excel_workbook.py` checks sheet names, that every cross-sheet reference resolves, that the file has
  no macros, that formula cells are locked, and that only the scenario input cells are unlocked.
- The formulas were also evaluated with an independent calculation engine (the Python `formulas` package) against the
  full synthetic dataset: Control reports `ALL CHECKS PASS`, December 2025 NRR is 85.25% and GRR is 84.45% (matching
  `mart_revenue_kpis`), and invoiced totals of $40,862,284.26 tie to the warehouse. That evaluation was a one-off
  check, not part of CI, and the workbook has not been opened in desktop Excel on this build host.
