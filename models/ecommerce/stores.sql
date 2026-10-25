-- ODS 入驻商家记录映射店铺实体；业务日期表示店铺开业日期。
select
    store_id,
    store_name,
    province,
    biz_date as opened_date
from {{ source('ecommerce_dw', 'ods_stores') }}
