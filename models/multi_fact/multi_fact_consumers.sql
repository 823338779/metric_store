-- 复用订单示例的客户资料，提供购买人与账户负责人共享的地区维度。
select customer_id as consumer_id, region_code as dima
from {{ ref('order_demo_customers') }}
