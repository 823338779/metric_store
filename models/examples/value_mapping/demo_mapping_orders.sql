-- 八笔固定模拟订单：404 与 502 共享用户，但仍按原始状态分别分组。
-- NULL 分支放在首位，让 StarRocks CTAS 将状态列推断为可空。
select 7 as order_id, 50 as user_id, cast(null as integer) as status_code, 200 as target_status_code,
       2 as channel_code, cast('2026-10-01' as date) as ordered_at,
       cast(7.00 as decimal(18, 2)) as amount
union all
select 1, 10, 200, 404, 1, cast('2026-10-01' as date), cast(100.00 as decimal(18, 2))
union all
select 2, 20, 404, 502, 1, cast('2026-10-01' as date), cast(20.00 as decimal(18, 2))
union all
select 3, 20, 502, 200, 2, cast('2026-10-01' as date), cast(10.00 as decimal(18, 2))
union all
select 4, 30, 599, 200, 2, cast('2026-10-01' as date), cast(4.00 as decimal(18, 2))
union all
select 5, 30, 503, 200, 2, cast('2026-10-01' as date), cast(5.00 as decimal(18, 2))
union all
select 6, 40, 504, 200, 2, cast('2026-10-01' as date), cast(6.00 as decimal(18, 2))
union all
select 8, 20, 404, 502, 1, cast('2026-10-01' as date), cast(30.00 as decimal(18, 2))
