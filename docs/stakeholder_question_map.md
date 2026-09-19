# Stakeholder Question Map

| Stakeholder | Question | Metric or analysis | Decision | Primary page |
|---|---|---|---|---|
| Executive | Why did recurring revenue change? | Opening MRR, new, expansion, contraction, churn, reactivation, closing MRR | Prioritize growth and retention actions | Executive overview; MRR and ARR movement |
| Finance | Does reported recurring revenue agree with billing and accounting activity? | MRR tie-out, invoices, cash, refunds, recognized and deferred revenue | Investigate close exceptions | Billing and revenue reconciliation |
| RevOps | Which commercial motions produce durable growth? | NRR, renewal, win rate, cycle length, expansion by segment | Adjust coverage and renewal motions | MRR and ARR movement; Sales and marketing efficiency |
| Marketing | Which channels justify spend? | CAC, retained revenue, LTV:CAC, payback, assumed marketing return | Reallocate future budget under stated assumptions | Sales and marketing efficiency |
| Customer Success | Which accounts need attention now? | Calibrated risk, health score, renewal date, exposure, drivers | Prioritize outreach | Customer health and churn risk |
| Product | Which adoption behaviors associate with retention? | Feature adoption, time to value, usage change, survival | Improve onboarding and adoption hypotheses | Retention and cohorts |
| Data owner | Which numbers are trustworthy? | Freshness, test status, exception counts, tie-out status | Resolve quality failures before use | Data quality and metric trust |

## Tableau workbook pages (generated; publication pending)

| Tableau page | Audience | Questions | Metrics (`metrics/semantic_layer.yml`) |
|---|---|---|---|
| Executive overview | Executive, Finance | What is ending MRR, how did it move this month, and is retention holding? What needs review? | `ending_mrr`, `net_new_mrr`, `gross_revenue_retention`, `net_revenue_retention`, `active_customers`, `exception_count` |
| Revenue and retention | RevOps, Finance | Which movements drive MRR by month, segment, plan and channel? How do cohorts retain? | MRR movement components, GRR, NRR, cohort logo retention |
| Customer risk | Customer Success | Which accounts to contact first, and how many can the team handle at a given precision? | risk score, lift by decile, precision, recall and queue size by threshold |
| Finance controls | Finance, data owner | Do invoices, payments, refunds and revenue tie out? Which exceptions need review? Is the data fresh? | `reconciliation_variance`, `failed_payment_exposure`, `billed_amount`, `exception_count` |
