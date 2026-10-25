# 电商语义模型与指标

本仓库是独立 dbt 工程，直接读取 StarRocks 的 `ecommerce_dw`，不使用 seed，不生成模拟订单或其他业务数据。保留 `ecommerce_metrics` 工程和 profile 名以兼容现有运行绑定。原采购订单与跨事实退款演示已替换，不再提供 `order_demo_*`、`metric_a`、`metric_b` 指标。

## 数据来源与模型

[源定义](models/ecommerce/sources.yml)声明五张真实源表，[语义定义](models/ecommerce/schema.yml)包含四个语义模型。

| 语义模型 | 数据源 | 粒度与关联 |
| --- | --- | --- |
| orders | fact_order_items + fact_orders | 一条订单商品明细；order_item_id 唯一，order_id 允许重复 |
| users | dim_customer | 一个用户；user_id 唯一 |
| products | dim_product | 一个商品；product_id 唯一 |
| stores | dim_store | 一家店铺；store_id 唯一 |

订单以 `user`、`product`、`store` 三个 foreign 实体连接维表 primary 实体。订单头只补充下单日期、用户、店铺、状态、渠道和支付方式，金额与件数只取明细。禁止把订单总额复制到明细后求和。

另有一个非语义物理模型 `time_spine`，按四种业务日期的最小/最大值生成连续自然日。源 `dim_date` 只覆盖订单期间，不足以覆盖更早的注册、开店和上架日期，所以不直接作为时间骨架。日期偏移使用 StarRocks 的 [generate_series](https://docs.starrocks.io/docs/sql-reference/sql-functions/table-functions/generate_series/)（要求 StarRocks 3.1+），没有固定业务日期或 seed。

## 指标口径

| 指标 | 展示名称 | 计算口径 |
| --- | --- | --- |
| order_count | 订单数 | 全状态订单 ID 去重数 |
| completed_order_count | 成交订单数 | COMPLETED 订单 ID 去重数 |
| sales_amount | 成交商品金额 | COMPLETED 明细 item_paid_amount 合计，元，不含运费 |
| sales_quantity | 成交销量 | COMPLETED 明细 quantity 合计，件 |
| buyer_count | 成交购买人数 | COMPLETED 订单用户 ID 去重数 |
| average_order_value | 成交客单价 | 成交商品金额 ÷ 成交订单数，元/单；分母为零时 NULL |
| user_count | 用户数 | 用户 ID 去重数 |
| new_user_count | 新增注册用户数 | 以注册日期为时间轴统计用户 ID 去重数 |
| product_count | 商品数 | 商品 ID 去重数 |
| active_product_count | 在售商品数 | 当前 is_active=1 的商品 ID 去重数 |
| store_count | 店铺数 | 店铺 ID 去重数 |
| new_store_count | 新开店铺数 | 以开店日期为时间轴统计店铺 ID 去重数 |

**成交按当前状态定义，只认 `COMPLETED`。** `PENDING`、`CANCELLED` 和 `REFUNDED` 即使金额字段非零也不计入成交；这不是支付流水净收入，也不单独统计退款现金流。成交时间归属于下单日期，不冒认支付完成时间。

订单和购买人数是去重指标，不能将各商品或各月份分组的结果直接相加当作总体。按商品或类目查询客单价时，分子只包含该商品分组金额，分母为包含该组商品的成交订单数；它不是这些订单的完整客单价。

用户、商品、店铺模型是当前快照。无日期限制时总数统计全体；时间筛选分别限定注册、上架和开店日期，不能解释为某日历史存量。新增用户数和用户数共享去重表达式，新开店铺数和店铺数亦然；无日期限制时数值相同。在售商品数使用当前在售状态，不是历史在售快照。用户会员等级、商品类目、店铺地区也是当前属性。

## 分析维度

- 订单：`order_item__order_id`、`order_item__order_status`、`order_item__sales_channel`、`order_item__payment_method`、`order_item__order_date`。
- 用户：`user__user_code`、`user__gender`、`user__age_group`、`user__member_level`、`user__province`、`user__city`、`user__acquisition_channel`、`user__register_date`。
- 商品：`product__sku_code`、`product__product_name`、`product__category_level1`、`product__category_level2`、`product__brand_name`、`product__is_active`、`product__launched_date`。
- 店铺：`store__store_code`、`store__store_name`、`store__store_type`、`store__province`、`store__city`、`store__opened_date`。

时间分组使用 `metric_time__day`、`metric_time__month` 等引擎支持的粒度。六个订单指标可以组合三个维表的维度；用户数仅按用户模型可达维度分析，商品数和店铺数同理，不通过反向一对多关联制造可用维度。用户省份与店铺省份名称相同但实体路径不同。

维度保留源值，不额外制造显示字典。通过服务查询时，先按当前 buildId 和指标集合发现可用维度，再使用返回的 optionId，不能跨构建复用。

## 本地构建与验收

使用当前服务虚拟环境中的 dbt、dbt-starrocks 和 MetricFlow。源表必须可读；目标 schema 必须与 `ecommerce_dw` 不同，且允许建表。不得在源 schema 执行模型构建。

在本仓库执行，先在当前终端安全注入 `DBT_ENV_SECRET_WAREHOUSE_USER`、`DBT_ENV_SECRET_WAREHOUSE_PASSWORD`，并配置 `ECOMMERCE_DB_HOST`、`ECOMMERCE_DB_PORT`、`ECOMMERCE_TARGET_SCHEMA`。凭据不写入仓库。

```powershell
$ecommerceScripts = (Resolve-Path ../dbt-metricflow-service/.venv/Scripts).Path
$ecommerceTemp = Join-Path $env:TEMP ("ecommerce-validation-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $ecommerceTemp | Out-Null
$env:DBT_TARGET_PATH = Join-Path $ecommerceTemp 'target'
$env:DBT_LOG_PATH = Join-Path $ecommerceTemp 'logs'
```

在 `$ecommerceTemp/profiles.yml` 写入以下模板：

```yaml
ecommerce_metrics:
  target: validation
  outputs:
    validation:
      type: starrocks
      host: "{{ env_var('ECOMMERCE_DB_HOST') }}"
      port: "{{ env_var('ECOMMERCE_DB_PORT', '9030') | int }}"
      username: "{{ env_var('DBT_ENV_SECRET_WAREHOUSE_USER') }}"
      password: "{{ env_var('DBT_ENV_SECRET_WAREHOUSE_PASSWORD') }}"
      catalog: default_catalog
      schema: "{{ env_var('ECOMMERCE_TARGET_SCHEMA') }}"
      threads: 2
```

```powershell
& (Join-Path $ecommerceScripts 'dbt.exe') build --no-partial-parse --project-dir . --profiles-dir $ecommerceTemp --target-path $env:DBT_TARGET_PATH --log-path $env:DBT_LOG_PATH
if ($LASTEXITCODE -ne 0) { throw '电商模型构建失败' }
& (Join-Path $ecommerceScripts 'python.exe') scripts/verify_ecommerce.py --profiles-dir $ecommerceTemp --manifest (Join-Path $env:DBT_TARGET_PATH 'manifest.json')
if ($LASTEXITCODE -ne 0) { throw '电商指标验收失败' }
```

构建包含 **5 个物理模型、45 项数据测试、4 个语义模型、12 个指标**。测试覆盖源主键/外键、明细唯一性、三个实体关系、金额/件数逐单对账、维表数量和时间骨架连续性。

验收脚本先检查实际 manifest，无 profile 时只检查模型/指标/无 seed 契约。提供 profile 后执行 14 组真实查询及对应 EXPLAIN SQL，与源表独立查询逐行比较：订单头总额、三个维表计数、非成交状态与零分母、商品类目品牌、用户会员、店铺类型、双省份路径、三维表组合、按月成交、原码筛选、2019 年注册月份和维值查询。金额允许浮点级误差，不放宽到业务金额差额。

原生 MetricFlow CLI 尚不支持 StarRocks 枚举；验收脚本使用与现有服务相同的 DuckDB SQL renderer 和 dbt-starrocks adapter，只验证这里实际执行的聚合/时间 SQL。脚本不导入相邻服务实现类。执行完成后可清理自己创建的临时目录；数据库验收 schema 由执行者按保留需求管理。

## 构建发布

服务从远端 Git 的指定提交读取工程，不读取本地未提交文件。发布前需单独确认推送与目标环境。通过 dbt-service 公开 `POST /builds` 提交完整执行快照，目标 schema 必须与源 `ecommerce_dw` 分离；源数据读取权限也须授予构建凭据。

构建成功后还需检查部署状态和当前生效指针，不能将构建成功等同于发布成功。旧指标名不兼容新目录；旧 buildId 仍指向原构建。移除 Git 模型不会自动删除旧数据库表，本变更不执行历史表清理。
