-- 从 StarRocks 原始订单提取每日日期，构建 MetricFlow 时间骨架。
select distinct ordered_at as date_day
from {{ source('ecommerce_raw', 'orders') }}
