-- ODS 客户注册记录映射用户实体；会员等级保留源表的注册时口径。
select
    customer_id as user_id,
    member_level,
    province,
    biz_date as register_date,
    registered_at,
    acquisition_channel
from {{ source('ecommerce_dw', 'ods_customers') }}
