-- 按退款流水保留金额和发生日期，仅从唯一订单头补充买家和店铺。
select r.refund_id, cast(r.refunded_at as date) as refund_date,
       o.customer_id as user_id, o.store_id, r.refund_status, r.refund_amount
from {{ source('ecommerce_dw', 'ods_refunds') }} as r
left join {{ source('ecommerce_dw', 'ods_orders') }} as o on r.order_id = o.order_id
