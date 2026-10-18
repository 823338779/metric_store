-- 日期常量与固定订单数据：一行一单，总金额 800 元；20、30 为已支付状态。
with business_constants as (
    select cast('2026-10-01' as date) as business_date
),
orders as (
    select 1001 as order_id, 1 as buyer_customer_id, 10 as account_id,
           20 as status_code, 1 as channel_code, cast(100.00 as decimal(18, 2)) as amount
    union all
    select 1002, 1, 20, 30, 2, cast(200.00 as decimal(18, 2))
    union all
    select 1003, 2, 10, 20, 1, cast(50.00 as decimal(18, 2))
    union all
    select 1004, 3, 10, 30, 2, cast(150.00 as decimal(18, 2))
    union all
    select 1005, 1, 20, 40, 1, cast(120.00 as decimal(18, 2))
    union all
    select 1006, 3, 10, 41, 99, cast(180.00 as decimal(18, 2))
)
-- 固定下单日期；不将展示字典连接进事实表，避免提前改变分组语义。
select orders.order_id, orders.buyer_customer_id, orders.account_id,
       business_constants.business_date as ordered_at,
       orders.status_code, orders.channel_code, orders.amount
from orders
cross join business_constants
