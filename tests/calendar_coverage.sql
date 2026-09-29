-- 原始订单日期必须完整覆盖 2020-01-01 至 2027-12-31 的每一天。
select 1 as invalid_calendar
from (select distinct ordered_at from {{ source('ecommerce_raw', 'orders') }}) dates
having count(*) <> 2922
    or min(ordered_at) <> cast('2020-01-01' as date)
    or max(ordered_at) <> cast('2027-12-31' as date)
