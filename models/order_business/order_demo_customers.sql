-- 地区代码静态常量：采购人和账户负责人共享同一客户维表。
with region_codes as (
    select 'EAST' as east_code, 'NORTH' as north_code, 'SOUTH' as south_code
)
select 1 as customer_id, east_code as region_code from region_codes
union all
select 2, north_code from region_codes
union all
select 3, south_code from region_codes
