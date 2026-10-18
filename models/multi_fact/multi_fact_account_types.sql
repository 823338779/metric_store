-- 唯一原码对应账户类型显示名称，映射只在指标聚合之后应用。
select 1 as code, '企业账户' as label
union all
select 2, '渠道账户'
