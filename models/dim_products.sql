-- 商品语义维表供成交指标按类目和品牌关联分析。
select product_id, sku, category, brand
from {{ source('ecommerce_raw', 'products') }}
