-- 账户 10 为企业账户，20 为渠道账户；负责人沿账户到客户路径访问。
with account_types as (
    select 10 as account_id, 1 as dimb
    union all
    select 20, 2
)
select accounts.account_id, accounts.owner_customer_id as owner_consumer_id, account_types.dimb
from {{ ref('order_demo_accounts') }} as accounts
join account_types on accounts.account_id = account_types.account_id
