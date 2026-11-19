-- 每个用户商品首次浏览形成一个观察对象，归属于首次浏览时刻。
select min_by(event_id, event_time) as event_id, customer_id as user_id, product_id, min(event_time) as event_time
from {{ source('ecommerce_dw', 'ods_user_events') }}
where event_type = 'VIEW'
group by customer_id, product_id
