-- 40 为用户取消，41 为超时关闭；共享标签不能合并原始分组。
with labels as (
    select '已支付' as paid_label, '已完成' as completed_label, '已关闭' as closed_label
)
select 20 as code, paid_label as label from labels
union all
select 30, completed_label from labels
union all
select 40, closed_label from labels
union all
select 41, closed_label from labels
