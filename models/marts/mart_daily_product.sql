select i.order_date, i.product_id, p.product_name, p.shop_id, p.category_name, p.brand_name,
    count(distinct i.order_id) as order_count,
    sum(i.paid_quantity) as paid_quantity,
    sum(i.paid_item_amount) as paid_item_amount,
    sum(i.discount_amount) as ordered_discount_amount
from {{ ref('fct_order_items') }} i join {{ ref('dim_products') }} p using(product_id)
group by all
