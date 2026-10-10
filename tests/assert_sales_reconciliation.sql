with source_orders as (
    select order_date, count(*) as order_count, sum(order_amount) as ordered_amount
    from {{ source('ecommerce', 'orders') }} group by 1
)
select coalesce(m.order_date, s.order_date) as order_date
from {{ ref('mart_daily_sales') }} m full outer join source_orders s using(order_date)
where m.order_date is null or s.order_date is null
   or m.order_count <> s.order_count or m.ordered_amount <> s.ordered_amount
