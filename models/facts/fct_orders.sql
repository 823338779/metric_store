{{ config(unique_key='order_id') }}
select *,
    (paid_amount - refund_amount)::decimal(14,2) as net_revenue,
    case when paid_amount > 0 then cost_amount else 0 end::decimal(14,2) as fulfilled_cost,
    (net_revenue - fulfilled_cost)::decimal(14,2) as gross_profit,
    1 as order_count,
    case when paid_amount > 0 then 1 else 0 end as paid_order_count,
    case when order_status = 'cancelled' then 1 else 0 end as cancelled_order_count,
    case when refund_amount > 0 then 1 else 0 end as refunded_order_count
from {{ ref('stg_orders') }}
where {{ incremental_date_filter('order_date') }}
