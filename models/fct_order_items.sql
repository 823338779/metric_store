-- 订单明细事实保留业务状态；净成交和退款分别按状态计算。
select
    i.order_item_id,
    i.order_id,
    o.user_id,
    i.product_id,
    o.shop_id,
    o.ordered_at,
    o.order_status,
    o.sales_channel,
    i.quantity,
    cast(i.quantity * i.unit_price * (1 - i.discount_rate) as decimal(18, 2)) as gross_amount,
    case when o.order_status = 'PAID'
         then cast(i.quantity * i.unit_price * (1 - i.discount_rate) as decimal(18, 2))
         else cast(0 as decimal(18, 2)) end as revenue,
    case when o.order_status = 'REFUNDED'
         then cast(i.quantity * i.unit_price * (1 - i.discount_rate) as decimal(18, 2))
         else cast(0 as decimal(18, 2)) end as refund_amount,
    case when o.order_status = 'PAID' then o.order_id else null end as paid_order_id
from {{ source('ecommerce_raw', 'order_items') }} i
join {{ source('ecommerce_raw', 'orders') }} o on o.order_id = i.order_id
