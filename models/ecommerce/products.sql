-- ODS 商品上架记录映射商品实体；仅保留源表实际提供的商品属性。
select
    product_id,
    sku_code,
    product_name,
    category as category_level1,
    brand as brand_name,
    list_price,
    cost_price,
    biz_date as launched_date
from {{ source('ecommerce_dw', 'ods_products') }}
