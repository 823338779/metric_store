select
    user_id,
    user_name,
    registered_date,
    province,
    membership_tier,
    acquisition_channel
from {{ source('ecommerce', 'users') }}
