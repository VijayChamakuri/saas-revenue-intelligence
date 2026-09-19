# Tableau Public release checklist

> Synthetic data from a seeded generator. Not real company, customer or financial results.

Status: **Tableau package prepared; workbook generated and load-checked in Tableau Public 2026.2.2; visual QA and publication not yet verified.**

1. `make pipeline` regenerates `tableau/data`, `tableau/workbook/saas_revenue_intelligence.twbx`, `expected_kpis.csv` and `validation_evidence.csv` (every row must pass).
2. Open the `.twbx` in Tableau Public; it must open with no error dialog.
3. Complete `tableau/qa_checklist.md` for all four dashboards.
4. Sign in to Tableau Public and publish with the title **SaaS Revenue Intelligence | MRR, Retention & Billing Controls**.
5. Put the exact Tableau Public URL in `README.md` and `tableau/README.md`.
6. Save one Tableau screenshot per dashboard in `tableau/screenshots/`.
7. Rerun `make test` and commit.

Known Tableau Public limits: extracts are required (the workbook ships Hyper extracts), everything published is public (only aggregates and synthetic IDs are included), there is no image export in the desktop app, and the workbook is a snapshot that must be republished after a refresh.
