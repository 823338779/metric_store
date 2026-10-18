-- 唯一原始代码与显示标签常量；两个业务角色复用此字典。
with labels as (
    select 'EAST' as east_code, '华东' as east_label,
           'NORTH' as north_code, '华北' as north_label,
           'SOUTH' as south_code, '华南' as south_label
)
select east_code as code, east_label as label from labels
union all
select north_code, north_label from labels
union all
select south_code, south_label from labels
