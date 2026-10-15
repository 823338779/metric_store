-- 固定模拟客户；同一地区维度同时用于采购人和企业账户负责人分析。
select 1 as customer_id, 'EAST' as region
union all
select 2 as customer_id, 'NORTH' as region
union all
select 3 as customer_id, 'SOUTH' as region
