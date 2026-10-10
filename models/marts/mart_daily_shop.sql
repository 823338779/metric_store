select o.order_date, o.shop_id, s.shop_name, s.shop_type, s.province,
    count(*) as order_count, sum(o.paid_order_count) as paid_order_count,
    sum(o.paid_amount) as paid_amount, sum(o.refund_amount) as refund_amount,
    sum(o.net_revenue) as net_revenue, sum(o.gross_profit) as gross_profit
from {{ ref('fct_orders') }} o join {{ ref('dim_shops') }} s using(shop_id)
group by all
