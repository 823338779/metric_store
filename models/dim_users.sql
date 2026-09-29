-- 用户语义维表供成交指标按地区、等级和来源渠道关联分析。
select user_id, registered_at, region, membership_tier, acquisition_channel
from {{ source('ecommerce_raw', 'users') }}
