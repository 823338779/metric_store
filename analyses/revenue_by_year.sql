select year(order_date) as year_number,
    sum(order_count) as orders, sum(paid_amount) as paid_amount,
    sum(refund_amount) as refund_amount, sum(net_revenue) as net_revenue
from {{ ref('mart_daily_sales') }} group by 1 order by 1
