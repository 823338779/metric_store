-- 独立渠道字典；查询三个维度时，它与两个状态字典关联分别生成 JOIN。
select 1 as code, cast('网页' as varchar(32)) as label
union all
select 2, cast('应用' as varchar(32))
