create temp table order_base as
select day_index * 1000 + n as order_id, dt as order_date,
    1 + rnd(day_index * 1000 + n, 'user', (day_index + 1) * 20) as user_id,
    1 + rnd(day_index * 1000 + n, 'shop', 30) as shop_id,
    case when n = 1 then 'refunded'
         when n = 2 then 'cancelled'
         when rnd(day_index * 1000 + n, 'status', 100) < 4 then 'partially_refunded'
         when rnd(day_index * 1000 + n, 'status', 100) < 12 then 'cancelled'
         else 'completed' end as order_status,
    list_extract(['organic', 'paid_search', 'social', 'direct'], (1 + rnd(day_index * 1000 + n, 'channel', 4))::integer) as channel,
    list_extract(['mobile', 'desktop', 'tablet'], (1 + rnd(day_index * 1000 + n, 'device', 3))::integer) as device_type,
    dt::timestamp + interval 8 hour + rnd(day_index * 1000 + n, 'time', 3600) * interval 1 second as ordered_at
from days cross join lateral range(1, 101 + rnd(day_index, 'volume', 201)) t(n);

create temp table incoming_order_items as
select b.order_id * 10 + line as order_item_id, b.order_id, b.order_date,
    p.product_id, 1 + rnd(b.order_id * 10 + line, 'quantity', 3) as quantity,
    p.list_price as unit_price, p.unit_cost,
    (quantity * p.list_price)::decimal(14,2) as gross_amount,
    (gross_amount * rnd(b.order_id * 10 + line, 'discount', 21) / 100)::decimal(14,2) as discount_amount,
    (gross_amount - discount_amount)::decimal(14,2) as net_amount,
    (quantity * p.unit_cost)::decimal(14,2) as cost_amount,
    b.ordered_at as updated_at
from order_base b
cross join lateral range(1, 2 + rnd(b.order_id, 'lines', 4)) t(line)
join raw.products p on p.product_id = (b.shop_id - 1) * 10 + 1 + (rnd(b.order_id, 'product', 10) + line) % 10;

create temp table incoming_orders as
select b.order_id, b.order_date, b.user_id, b.shop_id, b.order_status, b.channel, b.device_type,
    a.gross_amount, a.discount_amount, a.order_amount, a.cost_amount, a.item_quantity,
    (case when b.order_status = 'cancelled' then 0 else a.order_amount end)::decimal(14,2) as paid_amount,
    (case when b.order_status = 'refunded' then a.order_amount
          when b.order_status = 'partially_refunded' then a.order_amount * 0.5
          else 0 end)::decimal(14,2) as refund_amount,
    case when b.order_status <> 'cancelled' then
        list_extract(['alipay', 'wechat', 'bank_card'], (1 + rnd(b.order_id, 'payment', 3))::integer)
    end as payment_method,
    b.ordered_at,
    case when b.order_status <> 'cancelled' then b.order_date::timestamp + interval 10 hour end as paid_at,
    case when b.order_status in ('refunded', 'partially_refunded') then b.order_date::timestamp + interval 18 hour end as refunded_at,
    b.order_date::timestamp + interval 19 hour as updated_at
from order_base b
join (
    select order_id, sum(gross_amount)::decimal(14,2) as gross_amount,
        sum(discount_amount)::decimal(14,2) as discount_amount,
        sum(net_amount)::decimal(14,2) as order_amount,
        sum(cost_amount)::decimal(14,2) as cost_amount, sum(quantity)::bigint as item_quantity
    from incoming_order_items group by order_id
) a using(order_id);
