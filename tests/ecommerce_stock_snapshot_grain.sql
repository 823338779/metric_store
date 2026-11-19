-- 同一货位同日出现两条快照会导致期末合计翻倍。
select store_id, product_id, stock_date
from {{ ref('stock_snapshots') }}
group by store_id, product_id, stock_date
having count(*) > 1 or store_id is null or product_id is null or stock_date is null
