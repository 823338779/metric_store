-- 一行一家店铺；地域维度区分店铺所在地与用户所在地。
select
    store_key as store_id,
    store_code,
    store_name,
    store_type,
    province,
    city,
    opened_date
from {{ source('ecommerce_dw', 'dim_store') }}
