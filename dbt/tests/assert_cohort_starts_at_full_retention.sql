-- Every cohort must be fully active in its own acquisition month.
select cohort_month, active_customers, cohort_customers
from {{ ref('mart_cohort_retention') }}
where months_since_start = 0 and active_customers <> cohort_customers
