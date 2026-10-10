select order_date from {{ ref('fct_orders') }}
group by order_date having count(*) not between 100 and 300
