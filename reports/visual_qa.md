# Visual QA

> Synthetic data from a seeded generator. Not real company, customer or financial results.

| Date | Artifact | Viewport | Issue | Disposition |
|---|---|---|---|---|
| 2026-09-19 | `reports/finance_control_summary.pdf` (Control sheet) | Letter landscape, 75 dpi render | None: title, synthetic caveat, refresh time, source commit, status and latest KPIs all readable on one page | Pass |
| 2026-09-19 | Tableau, all four dashboards | Presentation mode on a 2560 x 1440 display | Tableau ignored proportional zone sizes: KPI values hidden and tables crushed | Fixed: zones now carry fixed pixel sizes |
| 2026-09-19 | Tableau Executive overview and Revenue and retention | Same | Raw field names as bridge labels and axis captions; a label in every cohort cell | Fixed: readable component labels, captions, labels removed |
| 2026-09-19 | Tableau Finance controls | Same | Month-filtered tiles with no Month control and no "selected month" label | Fixed |
| 2026-09-19 | Tableau, all four dashboards (final) | Same | No clipping, readable tables and legends, banner and source on every page | Pass; screenshots in `tableau/screenshots/`; published |
| 2026-09-19 | Excel key sheets at 100% zoom | Not captured | Values, formulas, tables and protection verified by tests and the formula engine | **Open**: open in Excel or LibreOffice and review |
| 2026-09-19 | Offline HTML dashboard | Not changed in this upgrade | Existing screenshots still current for the HTML pages | No action |
