-- 明细是唯一事实粒度；订单头只补充上下文，禁止复制订单总金额或运费。
{% set completed_status = 'COMPLETED' %}
select
    i.order_item_id,
    i.order_id,
    o.customer_key as user_id,
    i.product_key as product_id,
    o.store_key as store_id,
    o.order_date,
    o.order_status,
    o.sales_channel,
    o.payment_method,
    i.quantity,
    i.unit_price,
    i.item_gross_amount,
    i.item_discount_amount,
    i.item_paid_amount,
    -- 成交判定集中在此，所有成交金额、数量和去重指标复用同一个标记。
    case when o.order_status = '{{ completed_status }}' then 1 else 0 end as is_completed
from {{ source('ecommerce_dw', 'fact_order_items') }} as i
inner join {{ source('ecommerce_dw', 'fact_orders') }} as o
    on i.order_id = o.order_id
