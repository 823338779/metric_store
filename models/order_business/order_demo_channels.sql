-- 99 故意不配置，验收未匹配字典时回退原值的行为。
with labels as (
    select '网页' as web_label, '应用' as app_label
)
select 1 as code, web_label as label from labels
union all
select 2, app_label from labels
