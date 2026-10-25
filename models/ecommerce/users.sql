-- 复用真实用户维表的当前属性；不复制姓名等个人信息到分析模型。
select
    customer_key as user_id,
    customer_code as user_code,
    gender,
    age_group,
    member_level,
    province,
    city,
    register_date,
    acquisition_channel
from {{ source('ecommerce_dw', 'dim_customer') }}
