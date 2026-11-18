-- 使用入驻记录提供唯一店铺键和当前名称，避免同名店铺合并。
select store_id as raw_store_id, store_name as display_name
from {{ source('ecommerce_dw', 'ods_stores') }}
