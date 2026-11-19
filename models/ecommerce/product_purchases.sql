-- 每个观察对象仅保留首次浏览后最早一次购买，重复购买不会增加转化率。
select min_by(e.event_id, e.event_time) as event_id, e.customer_id as user_id, e.product_id, min(e.event_time) as event_time
from {{ source('ecommerce_dw', 'ods_user_events') }} e
join {{ ref('product_views') }} v on e.customer_id = v.user_id and e.product_id = v.product_id
where e.event_type = 'PURCHASE' and e.event_time >= v.event_time
group by e.customer_id, e.product_id
