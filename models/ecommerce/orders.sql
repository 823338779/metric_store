-- ODS 明细是一行一条商品；订单头仅补充上下文，避免重复累计订单总额。
{% set completed_status = 'COMPLETED' %}
select
    i.order_item_id,
    i.order_id,
    o.customer_id as user_id,
    i.product_id,
    o.store_id,
    o.biz_date as order_date,
    o.order_status,
    o.sales_channel,
    -- 在唯一订单头判档，商品筛选不会改变整单金额。
    case when o.payable_amount - o.shipping_amount is null then 'unknown'
         when o.payable_amount - o.shipping_amount < 100 then 'under_100'
         when o.payable_amount - o.shipping_amount < 500 then '100_to_under_500'
         else '500_plus' end as order_value_band,
    i.quantity,
    i.unit_price,
    i.gross_amount as item_gross_amount,
    i.discount_amount as item_discount_amount,
    -- 源字段是折后应付金额；仅 COMPLETED 明细通过成交标记计入成交金额。
    i.payable_amount as item_paid_amount,
    case when o.order_status = '{{ completed_status }}' then 1 else 0 end as is_completed
from {{ source('ecommerce_dw', 'ods_order_items') }} as i
inner join {{ source('ecommerce_dw', 'ods_orders') }} as o
    on i.order_id = o.order_id
