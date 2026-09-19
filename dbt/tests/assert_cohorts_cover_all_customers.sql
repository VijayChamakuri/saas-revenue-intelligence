-- Cohort sizes must add up to the customers that ever held MRR.
with cohort_total as (
  select sum(cohort_customers) as customers
  from {{ ref('mart_cohort_retention') }}
  where months_since_start = 0
), ever_active as (
  select count(distinct customer_id) as customers
  from {{ ref('int_customer_product_monthly_mrr') }}
  where mrr > 0
)
select c.customers as cohort_customers, e.customers as ever_active_customers
from cohort_total c cross join ever_active e
where c.customers <> e.customers
