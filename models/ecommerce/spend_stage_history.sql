-- 日初消费阶段由此前是否有成交决定，首个成交日仍属于首购前阶段。
with first_purchase as (
    select user_id, min(order_date) as first_day
    from {{ ref('orders') }}
    where is_completed = 1
    group by user_id
)
select u.user_id, u.register_date as valid_from, days_add(p.first_day, 1) as valid_to,
       'before_first_purchase' as spend_stage
from {{ ref('users') }} u
left join first_purchase p on u.user_id = p.user_id
where p.first_day is null or u.register_date <= p.first_day
union all
select user_id, days_add(first_day, 1), cast(null as date), 'returning_buyer'
from first_purchase
