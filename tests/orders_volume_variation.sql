-- 订单量需要具有足够的每日波动，避免固定笔数的示例数据。
select 1 as insufficient_variation
from (
    select ordered_at, count(*) as daily_orders
    from {{ source('ecommerce_raw', 'orders') }}
    group by ordered_at
) daily
having count(distinct daily_orders) < 20
