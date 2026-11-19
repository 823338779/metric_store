-- 仅对已确认到齐的闭区间补零；任何未确认日都会使包含它的期间比率未知。
with daily_sales as (
    select order_date, sum(case when is_completed = 1 then item_paid_amount else 0 end) as sales
    from {{ ref('orders') }}
    group by order_date
), daily_refunds as (
    select refund_date, sum(case when refund_status = 'SUCCESS' then refund_amount else 0 end) as refunds
    from {{ ref('refunds') }}
    group by refund_date
)
select c.date_day, coalesce(s.sales, 0) as sales, coalesce(r.refunds, 0) as observed_refunds,
       case when c.date_day between cast(nullif('{{ var("refund_complete_from", "") }}', '') as date)
                                 and cast(nullif('{{ var("refund_complete_through", "") }}', '') as date)
            then 0 else 1 end as unconfirmed
from {{ ref('time_spine') }} c
left join daily_sales s on c.date_day = s.order_date
left join daily_refunds r on c.date_day = r.refund_date
