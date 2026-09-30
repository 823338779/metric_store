-- 仅创建 StarRocks 模拟原表结构；数据由 generate_raw_data.py 生成并写入。
create database if not exists ecommerce_raw;

-- 用户、商品、店铺为缓慢增长的业务实体，日期字段记录首次可用时间。
create table if not exists ecommerce_raw.users (
    user_id int not null comment '用户唯一标识',
    registered_at date not null comment '用户注册日期',
    region varchar(32) not null comment '用户所在地区',
    membership_tier varchar(32) not null comment '会员等级',
    acquisition_channel varchar(32) not null comment '获客渠道'
) duplicate key(user_id) distributed by hash(user_id) buckets 4 properties ('replication_num'='1');

create table if not exists ecommerce_raw.products (
    product_id int not null comment '商品唯一标识',
    sku varchar(32) not null comment '商品库存单位编码',
    category varchar(32) not null comment '商品类目',
    brand varchar(32) not null comment '商品品牌',
    list_price decimal(18, 2) not null comment '商品标价',
    listed_at date not null comment '商品首次上架日期'
) duplicate key(product_id) distributed by hash(product_id) buckets 4 properties ('replication_num'='1');

create table if not exists ecommerce_raw.shops (
    shop_id int not null comment '店铺唯一标识',
    shop_name varchar(32) not null comment '店铺展示名称',
    region varchar(32) not null comment '店铺所在地区',
    shop_type varchar(32) not null comment '店铺经营类型',
    opened_at date not null comment '店铺开业日期'
) duplicate key(shop_id) distributed by hash(shop_id) buckets 4 properties ('replication_num'='1');

-- 交易原表保留业务状态、渠道、金额及完整关联键。
create table if not exists ecommerce_raw.orders (
    order_id bigint not null comment '订单唯一标识',
    ordered_at date not null comment '下单日期',
    user_id int not null comment '下单用户标识',
    shop_id int not null comment '成交店铺标识',
    order_status varchar(32) not null comment '订单状态',
    sales_channel varchar(32) not null comment '销售渠道',
    discount_rate decimal(5, 2) not null comment '订单折扣比例'
) duplicate key(order_id) distributed by hash(order_id) buckets 8 properties ('replication_num'='1');

create table if not exists ecommerce_raw.order_items (
    order_item_id bigint not null comment '订单明细唯一标识',
    order_id bigint not null comment '所属订单标识',
    product_id int not null comment '所购商品标识',
    quantity int not null comment '购买件数',
    unit_price decimal(18, 2) not null comment '成交时商品单价',
    discount_rate decimal(5, 2) not null comment '订单折扣比例'
) duplicate key(order_item_id) distributed by hash(order_item_id) buckets 8 properties ('replication_num'='1');

create table if not exists ecommerce_raw.payments (
    payment_id bigint not null comment '支付流水唯一标识',
    order_id bigint not null comment '所属订单标识',
    paid_at date not null comment '支付日期',
    paid_amount decimal(18, 2) not null comment '支付金额',
    payment_status varchar(32) not null comment '支付状态',
    payment_method varchar(32) not null comment '支付方式'
) duplicate key(payment_id) distributed by hash(payment_id) buckets 8 properties ('replication_num'='1');

create table if not exists ecommerce_raw.refunds (
    refund_id bigint not null comment '退款流水唯一标识',
    order_id bigint not null comment '所属订单标识',
    refunded_at date not null comment '退款日期',
    refund_amount decimal(18, 2) not null comment '退款金额',
    refund_reason varchar(32) not null comment '退款原因'
) duplicate key(refund_id) distributed by hash(refund_id) buckets 4 properties ('replication_num'='1');
