-- 每个企业账户恰有一位负责人；负责人可以与实际采购人不同。
select 10 as account_id, 2 as owner_customer_id
union all
select 20 as account_id, 3 as owner_customer_id
