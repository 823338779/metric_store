-- 一行一笔采购订单：既记录采购人，也记录订单归属的企业账户。
select 1001 as purchase_order_id, 1 as buyer_customer_id, 10 as account_id,
       cast('2026-10-01' as date) as ordered_at, cast(100.00 as decimal(18, 2)) as amount
union all
select 1002, 1, 20, cast('2026-10-01' as date), cast(200.00 as decimal(18, 2))
union all
select 1003, 2, 10, cast('2026-10-02' as date), cast(50.00 as decimal(18, 2))
union all
select 1004, 3, 10, cast('2026-10-02' as date), cast(150.00 as decimal(18, 2))
