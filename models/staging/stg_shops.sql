select
    shop_id,
    shop_name,
    shop_type,
    province,
    opened_date,
    shop_status
from {{ source('ecommerce', 'shops') }}
