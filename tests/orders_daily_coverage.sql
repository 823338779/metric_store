-- 每天至少有订单及已支付订单；缺失日期由 calendar_coverage 检测。
select ordered_at
from {{ source('ecommerce_raw', 'orders') }}
group by ordered_at
having count(*) < 10
    or sum(case when order_status = 'PAID' then 1 else 0 end) = 0
