-- 唯一性测试之外，核对维表行数，避免过滤掉没有成交的用户、商品或店铺。
select source_count, model_count
from (
    select (select count(*) from {{ source('ecommerce_dw', 'dim_customer') }}) as source_count,
           (select count(*) from {{ ref('users') }}) as model_count
    union all
    select (select count(*) from {{ source('ecommerce_dw', 'dim_product') }}),
           (select count(*) from {{ ref('products') }})
    union all
    select (select count(*) from {{ source('ecommerce_dw', 'dim_store') }}),
           (select count(*) from {{ ref('stores') }})
) as counts
where source_count <> model_count
