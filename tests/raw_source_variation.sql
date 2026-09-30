-- 明细和流水数量应随业务变化，维度表也应分批进入市场。
select 'order_items' as source_name
from (select order_id, count(*) as n from {{ source('ecommerce_raw', 'order_items') }} group by order_id) t
having count(distinct n) < 3
union all
select 'payments'
from (select paid_at, count(*) as n from {{ source('ecommerce_raw', 'payments') }} group by paid_at) t
having count(distinct n) < 10
union all
select 'refunds'
from (select refunded_at, count(*) as n from {{ source('ecommerce_raw', 'refunds') }} group by refunded_at) t
having count(distinct n) < 3
union all
select 'users'
from {{ source('ecommerce_raw', 'users') }}
having count(distinct registered_at) < 1000
union all
select 'products'
from {{ source('ecommerce_raw', 'products') }}
having count(distinct listed_at) < 100
union all
select 'shops'
from {{ source('ecommerce_raw', 'shops') }}
having count(distinct opened_at) < 10
