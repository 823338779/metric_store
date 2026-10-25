-- 全量逐单核对明细粒度、金额和件数，缺失/重复明细或订单头扇出都必须失败。
with actual as (
    select order_id, count(*) as line_count, sum(quantity) as quantity,
           sum(item_gross_amount) as gross_amount, sum(item_discount_amount) as discount_amount,
           sum(item_paid_amount) as paid_amount
    from {{ ref('orders') }}
    group by order_id
), source_lines as (
    select order_id, count(*) as line_count
    from {{ source('ecommerce_dw', 'ods_order_items') }}
    group by order_id
)
select coalesce(o.order_id, a.order_id) as order_id
from {{ source('ecommerce_dw', 'ods_orders') }} as o
full outer join actual as a on o.order_id = a.order_id
left join source_lines as i on a.order_id = i.order_id
where o.order_id is null or a.order_id is null or i.order_id is null
   or a.line_count <> i.line_count or a.quantity <> o.total_quantity
   or abs(a.gross_amount - o.gross_amount) > 0.01
   or abs(a.discount_amount - o.discount_amount) > 0.01
   or abs(a.paid_amount - (o.payable_amount - o.shipping_amount)) > 0.01
