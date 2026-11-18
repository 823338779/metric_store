-- 骨架必须连续，并覆盖订单、用户、商品、店铺和退款的业务日期。
with business_dates as (
    select order_date as business_day from {{ ref('orders') }}
    union all
    select register_date from {{ ref('users') }}
    union all
    select launched_date from {{ ref('products') }}
    union all
    select opened_date from {{ ref('stores') }}
    union all
    select refund_date from {{ ref('refunds') }}
), bounds as (
    select min(business_day) as first_day, max(business_day) as last_day from business_dates
), calendar as (
    select min(date_day) as first_day, max(date_day) as last_day, count(*) as days
    from {{ ref('time_spine') }}
)
select b.first_day, b.last_day
from bounds as b cross join calendar as c
where c.first_day is null or c.last_day is null
   or c.first_day <> b.first_day or c.last_day <> b.last_day
   or c.days <> datediff(b.last_day, b.first_day) + 1
