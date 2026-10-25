-- 商品维度使用当前目录属性，在售状态不代表历史库存或历史在售快照。
select
    product_key as product_id,
    sku_code,
    product_name,
    category_level1,
    category_level2,
    brand_name,
    list_price,
    cost_price,
    launched_date,
    is_active
from {{ source('ecommerce_dw', 'dim_product') }}
