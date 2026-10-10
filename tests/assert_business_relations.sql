select 'user_before_registration' as failure, o.order_id as id
from {{ ref('fct_orders') }} o join {{ ref('dim_users') }} u using(user_id)
where o.order_date < u.registered_date
union all
select 'product_shop_mismatch', i.order_item_id
from {{ ref('fct_order_items') }} i join {{ ref('dim_products') }} p using(product_id)
where i.shop_id <> p.shop_id
union all
select 'invalid_payment_time', order_id from {{ ref('fct_orders') }}
where paid_at < ordered_at or refunded_at < paid_at
   or (paid_amount > 0 and paid_at is null)
   or (refund_amount > 0 and refunded_at is null)
   or (order_status = 'cancelled' and (paid_at is not null or refunded_at is not null))
union all
select 'order_before_shop_open', o.order_id
from {{ ref('fct_orders') }} o join {{ ref('dim_shops') }} s using(shop_id)
where o.order_date < s.opened_date
union all
select 'order_before_product_listing', i.order_item_id
from {{ ref('fct_order_items') }} i join {{ ref('dim_products') }} p using(product_id)
where i.order_date < p.listed_date
