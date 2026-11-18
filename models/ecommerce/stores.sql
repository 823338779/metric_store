-- ODS 入驻商家记录映射店铺实体；业务日期表示店铺开业日期。
select
    store_id,
    -- 以店铺主键作为展示维度的原始键，与实体关联键保持相同类型。
    store_id as store_code,
    store_name,
    province,
    biz_date as opened_date
from {{ source('ecommerce_dw', 'ods_stores') }}
