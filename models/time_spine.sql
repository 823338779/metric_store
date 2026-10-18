-- 固定样本只覆盖一个业务日，不再依赖旧电商原始数据库。
select distinct ordered_at as date_day
from {{ ref('order_demo_orders') }}
