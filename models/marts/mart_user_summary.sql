select u.user_id, u.registered_date, u.province, u.membership_tier,
    min(o.order_date) as first_order_date, max(o.order_date) as last_order_date,
    count(o.order_id) as order_count, coalesce(sum(o.paid_order_count), 0) as paid_order_count,
    coalesce(sum(o.net_revenue), 0) as lifetime_net_revenue,
    coalesce(sum(o.refund_amount), 0) as lifetime_refund_amount
from {{ ref('dim_users') }} u left join {{ ref('fct_orders') }} o using(user_id)
group by all
