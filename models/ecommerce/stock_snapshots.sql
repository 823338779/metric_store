-- 每个店铺商品组合在同一天只有一条期末库存。
select snapshot_id, biz_date as stock_date, store_id, product_id, closing_quantity,
       concat(cast(store_id as varchar), ':', cast(product_id as varchar)) as stock_position
from {{ source('ecommerce_dw', 'ods_inventory_daily') }}
