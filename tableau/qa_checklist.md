# Tableau QA checklist

| Field | Value |
|---|---|
| Tableau version | |
| Tester | |
| Date | |
| Workbook commit | |

| # | Check | Result | Notes |
|---|---|---|---|
| 1 | Opens with no error dialog or missing data source | | Automated load check: pass, Tableau Public 2026.2.2, 2026-09-19 |
| 2 | KPI tiles match `expected_kpis.csv` for the latest month and two other months (Month control) | | Extract tie-out 288 of 288 |
| 3 | Calculated fields match `calculated_fields.md` | | |
| 4 | Month and Risk threshold parameters change their sheets; Revert resets | | |
| 5 | Plan, channel and year filters work on Revenue and retention | | |
| 6 | Selecting an exception class lists its invoices | | |
| 7 | Tooltips readable; no clipped labels, horizontal scroll or unreadable legends at 1366 x 768 | | |
| 8 | Synthetic notice, source and refresh text on every dashboard; risk page says prioritization aid | | Also asserted by tests |
| 9 | Phone layout reviewed | | |
| 10 | Published with the final title; URL in README and `tableau/README.md` | | |
| 11 | One Tableau screenshot per dashboard in `tableau/screenshots/` | | |
