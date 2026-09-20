with active as (
    select month_start, count(distinct customer_id) as active_customers
    from {{ ref('fct_mrr_movement') }}
    where closing_mrr > 0
    group by month_start
)
select b.month_start, b.closing_mrr, b.closing_mrr * 12 as arr, b.net_new_mrr,
       case when b.opening_mrr > 0 then (b.opening_mrr - b.contraction_mrr - b.churned_mrr) / b.opening_mrr end as gross_revenue_retention,
       case when b.opening_mrr > 0 then (b.opening_mrr + b.expansion_mrr + b.reactivation_mrr - b.contraction_mrr - b.churned_mrr) / b.opening_mrr end as net_revenue_retention,
       coalesce(a.active_customers, 0) as active_customers,
       b.closing_mrr / nullif(a.active_customers, 0) as average_revenue_per_active_customer
from {{ ref('mart_mrr_bridge') }} b
left join active a using (month_start)
