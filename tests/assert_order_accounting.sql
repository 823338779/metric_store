select o.order_id
from {{ ref('fct_orders') }} o
join (
    select order_id, sum(net_amount) as item_amount, sum(cost_amount) as item_cost
    from {{ ref('fct_order_items') }} group by order_id
) i using(order_id)
where o.order_amount <> i.item_amount
   or o.cost_amount <> i.item_cost
   or o.gross_amount - o.discount_amount <> o.order_amount
   or o.net_revenue <> o.paid_amount - o.refund_amount
   or o.gross_profit <> o.net_revenue - o.fulfilled_cost
   or o.refund_amount < 0 or o.refund_amount > o.paid_amount
   or (o.order_status = 'cancelled' and (o.paid_amount <> 0 or o.fulfilled_cost <> 0))
   or (o.order_status <> 'cancelled' and o.paid_amount <> o.order_amount)
