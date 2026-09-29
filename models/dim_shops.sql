-- 店铺语义维表供成交指标按店铺类型和地区关联分析。
select shop_id, shop_name, region, shop_type
from {{ source('ecommerce_raw', 'shops') }}
