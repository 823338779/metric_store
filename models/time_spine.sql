-- 四个业务日期共同决定边界，注册和开店早于订单也不会被遗漏。
with business_bounds as (
    select min(order_date) as first_day, max(order_date) as last_day from {{ ref('orders') }}
    union all
    select min(register_date), max(register_date) from {{ ref('users') }}
    union all
    select min(launched_date), max(launched_date) from {{ ref('products') }}
    union all
    select min(opened_date), max(opened_date) from {{ ref('stores') }}
), calendar_bounds as (
    select min(first_day) as first_day, max(last_day) as last_day from business_bounds
)
-- 只生成日期偏移，不生成业务事实；动态边界无需固定年份或 seed。
select cast(days_add(b.first_day, generate_series) as date) as date_day
from calendar_bounds as b, generate_series(0, datediff(b.last_day, b.first_day))
