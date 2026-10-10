-- Stable hash seed; lock DuckDB version to reproduce identical datasets.
create or replace macro rnd(k, salt, n) as (hash(k, salt, 20201010) % n)::bigint;

create table if not exists raw.shops as
select i as shop_id, '模拟店铺' || lpad(i::varchar, 3, '0') as shop_name,
    list_extract(['旗舰店', '专营店', '专卖店'], (1 + rnd(i, 'shop_type', 3))::integer) as shop_type,
    list_extract(['上海', '北京', '广东', '浙江', '江苏', '四川', '湖北', '陕西'], (1 + rnd(i, 'shop_province', 8))::integer) as province,
    date '2019-01-01' + rnd(i, 'shop_open', 365)::integer as opened_date,
    'active' as shop_status
from range(1, 31) t(i);

create table if not exists raw.products as
select i as product_id, (i - 1) // 10 + 1 as shop_id,
    'SKU-' || lpad(i::varchar, 6, '0') as sku,
    '模拟商品' || i as product_name,
    list_extract(['电子数码', '服装鞋包', '食品饮料', '家居家电', '美妆个护',
                  '母婴玩具', '运动户外', '图书文具', '宠物用品', '汽车用品'],
                 (1 + rnd(i, 'category', 10))::integer) as category_name,
    '模拟品牌' || (1 + rnd(i, 'brand', 30)) as brand_name,
    ((1000 + rnd(i, 'price', 99000)) / 100.0)::decimal(12,2) as list_price,
    (list_price * (35 + rnd(i, 'margin', 40)) / 100)::decimal(12,2) as unit_cost,
    date '2019-12-31' as listed_date, 'active' as product_status
from range(1, 301) t(i);

-- Full reference universe; orders only reference users already registered.
create table if not exists raw.users as
select i as user_id, '模拟用户' || i as user_name,
    date '2020-01-01' + ((i - 1) // 20)::integer as registered_date,
    list_extract(['上海', '北京', '广东', '浙江', '江苏', '四川', '湖北', '陕西'], (1 + rnd(i, 'province', 8))::integer) as province,
    list_extract(['standard', 'silver', 'gold'], (1 + rnd(i, 'tier', 3))::integer) as membership_tier,
    list_extract(['organic', 'paid_search', 'social', 'direct'], (1 + rnd(i, 'acquisition', 4))::integer) as acquisition_channel
from range(1, 58441) t(i);
