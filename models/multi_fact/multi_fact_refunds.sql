-- 一行一笔退款：订单 1001 分两次退款，合计 50 元；全部退款合计 155 元。
with refunds as (
    select 9001 as refund_id, 1001 as order_id, cast(20.00 as decimal(18, 2)) as amount
    union all
    select 9002, 1001, cast(30.00 as decimal(18, 2))
    union all
    select 9003, 1002, cast(80.00 as decimal(18, 2))
    union all
    select 9004, 1004, cast(25.00 as decimal(18, 2))
),
business_constants as (
    select cast('2026-10-02' as date) as refunded_at
)
-- 从唯一订单键取得购买人与账户，退款金额仍来自退款明细，保持退款粒度。
select refunds.refund_id, refunds.order_id, orders.consumer_id, orders.account_id,
       business_constants.refunded_at, refunds.amount
from refunds
join {{ ref('multi_fact_orders') }} as orders on refunds.order_id = orders.order_id
cross join business_constants
