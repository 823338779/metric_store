-- 此脚本直接在 StarRocks 中创建独立原表；dbt 只通过 source() 读取，不管理这些表。
-- 首次执行前确认 ecommerce_raw 数据库未被其他业务使用；重复执行不会覆盖已有表。
create database if not exists ecommerce_raw;

-- 用户、商品、店铺均为固定规则的虚构维度数据。
create table if not exists ecommerce_raw.users as
select
    cast(n as int) as user_id,
    cast(date_add(cast('2018-01-01' as date), interval mod(n * 17, 730) day) as date) as registered_at,
    case mod(n, 5) when 0 then 'East' when 1 then 'North' when 2 then 'South'
         when 3 then 'West' else 'Central' end as region,
    case mod(n, 3) when 0 then 'Bronze' when 1 then 'Silver' else 'Gold' end as membership_tier,
    case mod(n, 4) when 0 then 'Organic' when 1 then 'Search'
         when 2 then 'Social' else 'Referral' end as acquisition_channel
from table(generate_series(1, 1200)) as t(n);

create table if not exists ecommerce_raw.products as
select
    cast(n as int) as product_id,
    concat('SKU-', lpad(cast(n as varchar), 4, '0')) as sku,
    case mod(n, 5) when 0 then 'Electronics' when 1 then 'Home' when 2 then 'Food'
         when 3 then 'Fashion' else 'Beauty' end as category,
    case mod(n, 4) when 0 then 'Aurora' when 1 then 'Cedar'
         when 2 then 'Harbor' else 'Summit' end as brand,
    cast(19 + n * 3.25 as decimal(18, 2)) as list_price
from table(generate_series(1, 40)) as t(n);

create table if not exists ecommerce_raw.shops as
select
    cast(n as int) as shop_id,
    concat('Shop ', lpad(cast(n as varchar), 2, '0')) as shop_name,
    case mod(n, 5) when 0 then 'East' when 1 then 'North' when 2 then 'South'
         when 3 then 'West' else 'Central' end as region,
    case when mod(n, 3) = 0 then 'Flagship' else 'Marketplace' end as shop_type
from table(generate_series(1, 8)) as t(n);

-- 每个自然日生成 24 笔订单，日期区间包含首尾两日。
create table if not exists ecommerce_raw.orders as
select
    cast(d.day_index * 100 + s.order_slot as bigint) as order_id,
    cast(date_add(cast('2020-01-01' as date), interval d.day_index day) as date) as ordered_at,
    cast(mod((d.day_index + 1) * 7 + s.order_slot * 11, 1200) + 1 as int) as user_id,
    cast(mod(d.day_index + 1 + s.order_slot, 8) + 1 as int) as shop_id,
    case when mod(d.day_index + 1 + s.order_slot, 20) = 0 then 'REFUNDED'
         when mod(d.day_index + 1 + s.order_slot, 10) = 0 then 'CANCELLED'
         else 'PAID' end as order_status,
    case mod(s.order_slot, 3) when 0 then 'App' when 1 then 'Web' else 'MiniProgram' end as sales_channel,
    case when mod(s.order_slot, 7) = 0 then cast(0.10 as decimal(5, 2))
         else cast(0 as decimal(5, 2)) end as discount_rate
from table(generate_series(0, 2921)) as d(day_index)
cross join table(generate_series(1, 24)) as s(order_slot);

-- 订单商品明细和支付、退款流水直接由 StarRocks 中的原表生成。
create table if not exists ecommerce_raw.order_items as
select
    cast(o.order_id * 10 + i.item_slot as bigint) as order_item_id,
    o.order_id,
    p.product_id,
    cast(mod(o.order_id + i.item_slot, 3) + 1 as int) as quantity,
    p.list_price as unit_price,
    o.discount_rate
from ecommerce_raw.orders o
cross join table(generate_series(1, 2)) as i(item_slot)
join ecommerce_raw.products p
  on p.product_id = cast(mod(o.order_id + i.item_slot * 13, 40) + 1 as int);

create table if not exists ecommerce_raw.payments as
select
    o.order_id as payment_id,
    o.order_id,
    o.ordered_at as paid_at,
    cast(sum(i.quantity * i.unit_price * (1 - i.discount_rate)) as decimal(18, 2)) as paid_amount,
    case when o.order_status = 'REFUNDED' then 'REFUNDED' else 'SETTLED' end as payment_status,
    case mod(o.order_id, 3) when 0 then 'Card' when 1 then 'Wallet' else 'Bank' end as payment_method
from ecommerce_raw.orders o
join ecommerce_raw.order_items i on i.order_id = o.order_id
where o.order_status <> 'CANCELLED'
group by o.order_id, o.ordered_at, o.order_status;

create table if not exists ecommerce_raw.refunds as
select
    p.payment_id as refund_id,
    p.order_id,
    p.paid_at as refunded_at,
    p.paid_amount as refund_amount,
    case mod(p.order_id, 2) when 0 then 'CustomerRequest' else 'OutOfStock' end as refund_reason
from ecommerce_raw.payments p
where p.payment_status = 'REFUNDED';
