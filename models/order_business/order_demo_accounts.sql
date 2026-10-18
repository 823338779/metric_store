-- 每个账户只有一位负责人；A 归属客户 2，B 归属客户 3。
select 10 as account_id, 2 as owner_customer_id
union all
select 20, 3
