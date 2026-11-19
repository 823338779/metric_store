-- 注册后首笔成交，每位用户最多贡献一次转化。
select o.customer_id as user_id, min(o.created_at) as created_at
from {{ source('ecommerce_dw', 'ods_orders') }} o
join {{ ref('users') }} u on o.customer_id = u.user_id
where o.order_status = 'COMPLETED' and o.created_at >= u.registered_at
group by o.customer_id
