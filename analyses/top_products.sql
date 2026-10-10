select product_id, product_name, sum(paid_quantity) as paid_units,
    sum(paid_item_amount) as paid_amount
from {{ ref('mart_daily_product') }} group by 1, 2 order by paid_amount desc limit 20
