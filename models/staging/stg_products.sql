select
    product_id,
    shop_id,
    sku,
    product_name,
    category_name,
    brand_name,
    list_price,
    unit_cost,
    listed_date,
    product_status
from {{ source('ecommerce', 'products') }}
