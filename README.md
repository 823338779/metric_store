# 电商语义模型与指标

本仓库是独立 dbt 工程，直接读取 StarRocks 的 `ecommerce_dw`，不使用 seed，不生成模拟订单或其他业务数据。保留 `ecommerce_metrics` 工程和 profile 名以兼容现有运行绑定。原采购订单与跨事实退款演示已替换，不再提供 `order_demo_*`、`metric_a`、`metric_b` 指标。

## 数据来源与模型

[源定义](models/ecommerce/sources.yml)声明八张 ODS 源表。订单、用户、商品和店铺的[语义定义](models/ecommerce/schema.yml)与退款、展示字典共同组成以下模型。

| 语义模型 | 数据源 | 粒度与关联 |
| --- | --- | --- |
| refunds | ods_refunds + ods_orders | 一笔退款流水，通过订单头取得用户、店铺；按实际退款日期归属 |
| store_directory | ods_stores | 每个店铺 ID 一行，提供当前展示名称 |
| orders | ods_order_items + ods_orders | 一条订单商品明细；order_item_id 唯一，order_id 允许重复 |
| users | ods_customers | 一个用户；user_id 唯一 |
| products | ods_products | 一个商品；product_id 唯一 |
| stores | ods_stores | 一家店铺；store_id 唯一 |

订单以 `user`、`product`、`store` 三个 foreign 实体连接维表 primary 实体。ODS 明细的 `payable_amount` 映射为 `item_paid_amount`，只在成交状态下计入成交金额；全状态逐单对账使用订单头应付金额减运费。ODS 未提供的性别、年龄段、城市、店铺类型、支付方式和在售状态等字段不对外暴露，移除 `active_product_count` 指标。

订单头只补充下单日期、用户、店铺、状态和渠道，金额与件数只取明细。禁止把订单总额复制到明细后求和。

另有一个非语义物理模型 `time_spine`，按订单、注册、商品、店铺、退款、库存及行为事件日期的最小/最大值生成连续自然日。日期范围直接来自 ODS 映射后的业务模型，不依赖独立日期源表。日期偏移使用 StarRocks 的 [generate_series](https://docs.starrocks.io/docs/sql-reference/sql-functions/table-functions/generate_series/)（要求 StarRocks 3.1+），没有固定业务日期或 seed。

## 指标口径

| 指标 | 展示名称 | 计算口径 |
| --- | --- | --- |
| order_count | 订单数 | 全状态订单 ID 去重数 |
| completed_order_count | 成交订单数 | COMPLETED 订单 ID 去重数 |
| sales_amount | 成交商品金额 | COMPLETED 明细 payable_amount（模型别名 item_paid_amount）合计，元，不含运费 |
| sales_quantity | 成交销量 | COMPLETED 明细 quantity 合计，件 |
| buyer_count | 成交购买人数 | COMPLETED 订单用户 ID 去重数 |
| average_order_value | 成交客单价 | 成交商品金额 ÷ 成交订单数，元/单；分母为零时 NULL |
| user_count | 用户数 | 用户 ID 去重数 |
| new_user_count | 新增注册用户数 | 以注册日期为时间轴统计用户 ID 去重数 |
| product_count | 商品数 | 商品 ID 去重数 |
| store_count | 店铺数 | 店铺 ID 去重数 |
| new_store_count | 新开店铺数 | 以开店日期为时间轴统计店铺 ID 去重数 |
| completed_gross_amount | 成交折前商品额 | 成交商品明细折前金额，元 |
| completed_discount_amount | 成交商品优惠额 | 成交商品明细优惠金额，元 |
| discount_rate | 成交折扣率（优惠占比） | 成交优惠额 ÷ 成交折前商品额 |
| units_per_order | 成交件单量 | 成交件数 ÷ 成交订单数 |
| average_selling_price | 件均成交价 | 成交商品金额 ÷ 成交件数 |
| selling_store_count | 动销店铺数 | 所选期间和商品范围内有成交的店铺去重数 |
| successful_refund_amount | 成功退款金额 | 成功流水按 refunded_at 归属，金额单位元 |

## 复杂经营资产

订单模型提供三个可直接分组或筛选的表达式维度。 `order_item__item_value_band` 按单条明细应付额分为不足 100 元、100 至不足 500 元、500 元及以上三档；空值单列。`order_item__item_discount_band` 用明细优惠额和折前额区分无优惠、低于 20% 和至少 20% 的优惠；折前额非正或任一输入缺失时归入 unknown。`order_item__order_month__month` 按下单月分组。维度可以与商品类目、用户渠道或店铺省份组合。

[经营指标定义](models/ecommerce/operating_metrics.yml)复用现有成交和退款指标。500 元、20% 和 10000 元是本组资产选用的分析阈值。

| 指标 | 使用口径 |
| --- | --- |
| high_value_vs_deep_discount_sales_gap | 高额明细成交额减去深折明细成交额，两侧独立筛选。既高额又深折的明细同时进入两侧。 |
| sales_above_target | 分组汇总成交额后取超过 10000 元的部分。按店铺、月查询时每个店月各用一次目标。 |
| high_value_discounted_order_share | 有高额明细的成交订单中，有同一条明细同时满足高额和深折的订单占比。一个订单有多条符合条件的明细也只计一次。 |
| refund_to_sales_amount_ratio | 按共同月份、店铺等维度分别汇总退款发生额与下单成交额再相除。以前月份的订单可在本月退款，比值可能超过 100%。 |
| sales_mtd | 按 metric_time__day 查询当月累计成交额，跨月重置。 |
| sales_wow_growth | 按 metric_time__week 对比前一自然周成交额，前周为零或缺失时返回 NULL。 |

## 历史维度、窗口与快照

[扩展语义模型](models/ecommerce/advanced_assets.yml)直接读取商品行为和库存，使用订单头金额为整单判档。以下分组与时间口径用于经营复盘。

| 查询资产 | 粒度与边界 |
| --- | --- |
| high_spend_user_count | 在完整成交历史中按买家合计商品成交额，严格大于 1000 元入选。注册月份描述用户所属批次。 |
| rolling_7d_buyers | 按 metric_time__day 查询，对当日及前六个自然日的成交买家一次去重。 |
| registration_purchase_7d | 按注册时刻起算，在左闭右开的七天内首次下单且订单当前已成交，每位注册用户最多计一次。 |
| same_product_purchase_7d | 分母为首次浏览的用户商品组合，分子为同一组合首次浏览起七天内购买的组合。按首次浏览月份归属，重复浏览和购买均不增加权重。 |
| sales_amount × buyer_history__spend_stage | SCD II 按日初有无既往成交划分客户阶段。首购日全部成交归入首购前阶段，次日起归入回购买家阶段。原注册会员等级仍可独立分析。 |
| period_closing_stock | 对统计期内有快照的每个店铺商品取最后一次 closing_quantity，再汇总；期内无观测的组合不参与。 |
| completed_order_count × order_item__order_value_band | 按整单应付额扣除运费后分档。商品筛选只决定哪些订单入选。 |
| confirmed_refund_to_sales_ratio | 按自然日关联两张事实表到日历，再按整个查询期间判定完整性。任一天未确认或期间成交额为零返回 NULL，已确认且有成交无退款返回 0。 |

退款到齐区间由上游确认后通过 dbt 构建变量传入，例如 `--vars '{"refund_complete_from":"2024-01-01","refund_complete_through":"2024-01-31"}'`。两端均包含。默认所有日期为未知。此示例仅演示参数格式。漏斗按秒匹配，报表按日或更粗粒度查询；观察期最后七日的结果可能随新事件到来而变化。

当前 dbt 1.12 构建通过 semantic_manifest 提供完整语义；OSI 转换器无法导出引用转化指标的派生表达式。StarRocks 服务渲染器需使用支持 UUID() 的版本才能执行原生漏斗。

## 月度区域经营与店铺复盘

区域经营月报同时看本省用户贡献的成交额和本省店铺发生的退款额。使用以下两个公共分组，按完整的月份、省份组合对齐；仅一侧有记录时保留该行，另一侧金额为 NULL。

| 查询输出 | sales_amount | successful_refund_amount |
| --- | --- | --- |
| period | order_item__order_date，month | refund__refund_date，month |
| province | user__province | store__province |

两列分别反映买家侧成交和商家侧退款，日期、归属角色及金额口径各异，不能直接相减作为净收入。渠道运营和商品团队可以按类目、品牌、渠道复用折扣、件价和动销指标。件单量乘以件均成交价可与同一分组内的客单价核对。

店铺复盘使用同一维度 `store__store_code`。普通查询按店铺 ID 汇总后显示店名；绑定查询返回原始 ID，方便上下游按稳定键对齐。两种模式均使用源表对账，可执行查询见[验收脚本](scripts/verify_ecommerce.py)。

**成交按当前状态定义，只认 `COMPLETED`。** `CANCELLED` 和 `REFUNDED` 即使金额字段非零也不计入成交；这不是支付流水净收入；成功退款额由独立退款流水提供。成交时间归属于下单日期，不冒认支付完成时间。

订单和购买人数是去重指标，不能将各商品或各月份分组的结果直接相加当作总体。按商品或类目查询客单价时，分子只包含该商品分组金额，分母为包含该组商品的成交订单数；它不是这些订单的完整客单价。

用户、商品、店铺模型分别读取 ODS 注册、上架和入驻记录。无日期限制时总数统计全体；时间筛选分别限定注册、上架和开店日期，不能解释为某日历史存量。新增用户数和用户数共享去重表达式，新开店铺数和店铺数亦然；无日期限制时数值相同。用户会员等级为注册时属性；商品类目和店铺地区沿用 ODS 属性。

## 分析维度

- 订单：`order_item__order_id`、`order_item__order_status`、`order_item__sales_channel`、`order_item__order_date`。
- 用户：`user__member_level`、`user__province`、`user__acquisition_channel`、`user__register_date`。
- 商品：`product__sku_code`、`product__product_name`、`product__category_level1`、`product__brand_name`、`product__launched_date`。
- 店铺：`store__store_name`、`store__province`、`store__opened_date`。

时间分组使用 `metric_time__day`、`metric_time__month` 等引擎支持的粒度。订单指标可以组合三个维表的维度；用户数仅按用户模型可达维度分析，商品数和店铺数同理，不通过反向一对多关联制造可用维度。用户省份与店铺省份名称相同但实体路径不同。

店铺经营维度 `store__store_code` 按店铺 ID 分组，通过 `store_directory` 映射到当前店名。同名店铺保留各自的结果行。绑定查询及筛选使用原始键。通过服务查询时，先按当前 buildId 和指标集合发现可用维度，再使用返回的 optionId，不能跨构建复用。

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

构建包含 **13 个物理模型、52 项数据测试、12 个语义模型、39 个指标（含两个内部分子匹配比率）**。测试覆盖源主键/外键、明细唯一性、三个实体关系、金额/件数逐单对账、维表数量和时间骨架连续性。

验收脚本先检查实际 manifest，无 profile 时只检查模型/指标/无 seed 契约。提供 profile 后执行 22 组真实查询及对应 EXPLAIN SQL，与源表独立查询逐行比较：订单头总额、三个维表计数、非成交状态与零分母、商品类目品牌、用户会员、店铺省份、双省份路径、三维表组合、按月成交、原码筛选、2020 年注册月份和维值查询。金额允许浮点级误差，不放宽到业务金额差额。

原生 MetricFlow CLI 尚不支持 StarRocks 枚举；验收脚本使用与现有服务相同的 基于 DuckDB 的 SQL renderer（漏斗使用 StarRocks 的 UUID 函数）和 dbt-starrocks adapter，只验证这里实际执行的聚合/时间 SQL。脚本不导入相邻服务实现类。执行完成后可清理自己创建的临时目录；数据库验收 schema 由执行者按保留需求管理。

## 构建发布

服务从远端 Git 的指定提交读取工程，不读取本地未提交文件。发布前需单独确认推送与目标环境。通过 dbt-service 公开 `POST /builds` 提交完整执行快照，目标 schema 必须与源 `ecommerce_dw` 分离；源数据读取权限也须授予构建凭据。

构建成功后还需检查部署状态和当前生效指针，不能将构建成功等同于发布成功。旧指标名不兼容新目录；旧 buildId 仍指向原构建。移除 Git 模型不会自动删除旧数据库表，本变更不执行历史表清理。
