select
    order_item_id,
    order_id,
    order_date,
    product_id,
    quantity,
    unit_price,
    unit_cost,
    gross_amount,
    discount_amount,
    net_amount,
    cost_amount,
    updated_at
from {{ source('ecommerce', 'order_items') }}
