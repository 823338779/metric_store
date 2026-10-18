-- 一行一单；订单金额只在本事实表聚合，不关联退款明细。
select order_id, buyer_customer_id as consumer_id, account_id, ordered_at, amount
from {{ ref('order_demo_orders') }}
