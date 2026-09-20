# Tableau QA checklist

> Synthetic data from a seeded generator. Not real company, customer or financial results.

| Field | Value |
|---|---|
| Tableau version | Tableau Public 2026.2.2 (macOS, Apple silicon) |
| Tester | Vijay Chamakuri |
| Date | 2026-09-19 |
| Tableau Public URL | https://public.tableau.com/app/profile/vijay.chamakuri/viz/SaaSRevenueIntelligenceMRRRetentionBillingControls/Executiveoverview |

| # | Check | Result | Notes |
|---|---|---|---|
| 1 | Opens with no error dialog or missing data source | Pass | Tableau log shows no errors |
| 2 | KPI tiles match `expected_kpis.csv` | Pass | December 2025 checked on screen ($1,914,753 ending MRR, -$259,564 net new, 84.5% GRR, 85.3% NRR, 756 active customers, 969 exceptions); all months tied in `validation_evidence.csv` (288 of 288) |
| 3 | Calculated fields match `calculated_fields.md` | Pass | Generated from the same specification |
| 4 | Month and Risk threshold parameters change their sheets; Revert resets | Pass | |
| 5 | Plan, channel and year filters work on Revenue and retention | Pass | |
| 6 | Selecting an exception class lists its invoices | Pass | |
| 7 | Tooltips readable; no clipped labels, horizontal scroll or unreadable legends at 1366 x 768 | Pass after fixes | Fixed: pinned zone sizes, readable bridge labels, captions, cohort labels removed |
| 8 | Synthetic notice, source and refresh text on every dashboard; risk page says prioritization aid | Pass | Also asserted by tests |
| 9 | Phone layout reviewed | Not reviewed | Desktop layout is the tested one |
| 10 | Published with the final title; URL in README and `tableau/README.md` | Pass | |
| 11 | One Tableau screenshot per dashboard in `tableau/screenshots/` | Pass | 4 screenshots |
