-- 每位用户仅最后一段可开放，历史阶段之间首尾必须相接。
with versions as (
    select user_id, valid_from, valid_to,
           lead(valid_from) over (partition by user_id order by valid_from) as next_start
    from {{ ref('spend_stage_history') }}
)
select user_id, valid_from, valid_to
from versions
where valid_from is null or valid_from >= valid_to
   or (next_start is null and valid_to is not null)
   or (next_start is not null and (valid_to is null or valid_to <> next_start))
