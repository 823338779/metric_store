-- StarRocks 原始订单每日必须有 24 笔；缺失日期由 calendar_coverage 检测。
select ordered_at
from {{ source('ecommerce_raw', 'orders') }}
group by ordered_at
having count(*) <> 24
