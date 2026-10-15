-- 由模型定义保证原始键唯一；同一个显示值可以对应多个原始键。
select 200 as code, cast('成功' as varchar(32)) as label
union all
select 404, cast('失败' as varchar(32))
union all
select 502, cast('失败' as varchar(32))
union all
select 503, cast(null as varchar(32))
union all
select 504, cast('' as varchar(32))
-- 刻意不定义 599，用于验证缺失映射时回退到原始值文本。
