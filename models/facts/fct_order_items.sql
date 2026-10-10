{{ config(unique_key='order_item_id') }}
select i.*, o.user_id, o.shop_id, o.channel, o.order_status,
    case when o.order_status <> 'cancelled' then i.net_amount else 0 end as paid_item_amount,
    case when o.order_status <> 'cancelled' then i.quantity else 0 end as paid_quantity
from {{ ref('stg_order_items') }} i
join {{ ref('stg_orders') }} o using (order_id, order_date)
where {{ incremental_date_filter('order_date') }}
