-- Grain: one row per acquisition cohort (first month with MRR) and months since start.
-- Logo retention counts customers with MRR > 0 in the month, so reactivated customers
-- re-enter the numerator. Dollar retention is cohort MRR over the cohort's month-0 MRR.
with customer_month as (
  select month_start, customer_id, sum(mrr) as mrr
  from {{ ref('int_customer_product_monthly_mrr') }}
  where mrr > 0
  group by 1, 2
), first_month as (
  select customer_id, min(month_start) as cohort_month
  from customer_month
  group by 1
), cohort_size as (
  select f.cohort_month,
         count(*) as cohort_customers,
         sum(c.mrr)::decimal(18,2) as starting_mrr
  from first_month f
  join customer_month c on c.customer_id = f.customer_id and c.month_start = f.cohort_month
  group by 1
), grid as (
  select s.cohort_month, m.month_start,
         date_diff('month', s.cohort_month, m.month_start) as months_since_start,
         s.cohort_customers, s.starting_mrr
  from cohort_size s
  join {{ ref('int_month_spine') }} m on m.month_start >= s.cohort_month
), activity as (
  select f.cohort_month, c.month_start,
         count(*) as active_customers,
         sum(c.mrr)::decimal(18,2) as cohort_mrr
  from first_month f
  join customer_month c on c.customer_id = f.customer_id
  group by 1, 2
)
select g.cohort_month, g.month_start, g.months_since_start,
       g.cohort_customers, g.starting_mrr,
       coalesce(a.active_customers, 0) as active_customers,
       coalesce(a.cohort_mrr, 0)::decimal(18,2) as cohort_mrr,
       coalesce(a.active_customers, 0)::double / g.cohort_customers as logo_retention,
       coalesce(a.cohort_mrr, 0)::double / nullif(g.starting_mrr, 0) as net_dollar_retention
from grid g
left join activity a on a.cohort_month = g.cohort_month and a.month_start = g.month_start
