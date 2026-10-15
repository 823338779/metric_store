# 电商指标 dbt 项目

本仓库根目录是 dbt 项目。原始数据独立存放在 StarRocks 的 `ecommerce_raw` 数据库：[raw_bootstrap.sql](raw_bootstrap.sql) 定义空表结构，[generate_raw_data.py](generate_raw_data.py) 使用 Python 随机生成业务数据、写入临时表并校验后替换七张原表。dbt 仅通过 `source()` 读取原表并构建维表、事实表和指标，不创建或写入原表。生成脚本会替换 `ecommerce_raw` 中的七张同名原表，**仅可用于模拟数据环境**；执行前请确认该数据库未用于其他业务。

原始订单覆盖 **2020-01-01 至 2027-12-31** 共 2,922 天，每天至少 12 笔。每日订单量在工作日、周末及旺季的基础上随机浮动；用户注册、商品上架、店铺开业、订单状态、渠道、折扣、每单明细数、购买件数、商品价格、支付方式和退款原因也分别随机抽样。订单只关联下单时已存在的用户、商品和店铺。每次运行默认使用新的随机种子，数据量会变化；输出中的 `seed` 可通过 `--seed` 传入，以复现同一批数据。

生成脚本使用 `dbt-metricflow-service` 已有的 Python 环境（其中包含 `mysql-connector-python`）。设置 `DBT_STARROCKS_HOST`、`DBT_STARROCKS_PORT`、`DBT_STARROCKS_USER` 和 `DBT_ENV_SECRET_STARROCKS_PASSWORD` 后，在该目录执行：

```powershell
uv run --frozen python ../metrics_store/generate_raw_data.py
```

`ecommerce_raw.users`、`products`、`shops`、`orders`、`order_items`、`payments`、`refunds` 是 StarRocks 中的七张原表，在 dbt 中声明为 source。`dim_users`、`dim_products`、`dim_shops` 与 `fct_order_items` 提供 MetricFlow 可关联的语义模型，`time_spine` 从订单日期构建时间骨架。指标包括 `revenue`（已支付成交金额）、`gross_amount`（所有订单折后金额）、`refund_amount`（退款金额）、`units_sold`（已支付商品件数）、`order_count`（去重已支付订单数）和 `average_order_value`（平均已支付订单金额）。可按日期、用户地区与等级、商品类目与品牌、店铺类型等维度查询。

数据完全为示例数据，不包含真实业务记录或凭据。先在目标 StarRocks 运行 Python 生成脚本，并授予 dbt 运行账号读取 `ecommerce_raw`、在固定 `dbt_ecom` schema 内建表和删表的权限。指标平台发布时会从本仓库 `main` 的固定提交读取 dbt 项目，在 `dbt_ecom` 中以 `rv_<runId>_` 前缀隔离每次全量 `dbt build` 的结果；原表不属于该构建的管理范围。

## StarRocks profile

在 dbt 运行服务的 `profiles/profiles.yml` 中配置 `ecommerce_metrics`。连接信息从服务环境变量提供；`schema` 必须由平台运行任务注入：

```yaml
ecommerce_metrics:
  target: starrocks
  outputs:
    starrocks:
      type: starrocks
      host: "{{ env_var('DBT_STARROCKS_HOST') }}"
      port: "{{ env_var('DBT_STARROCKS_PORT') | int }}"
      schema: "{{ env_var('DBT_PLATFORM_SCHEMA') }}"
      username: "{{ env_var('DBT_STARROCKS_USER') }}"
      password: "{{ env_var('DBT_ENV_SECRET_STARROCKS_PASSWORD', '') }}"
```

运行服务的项目绑定使用 `projectId: ecommerce_metrics`、`projectSubdir: .`、`profileBindingId: starrocks`、`schemaName: dbt_ecom`，`remote` 指向本仓库。指标平台的 Git 配置也设置 `schema-name: dbt_ecom`，并使用相同的项目和 profile 绑定。升级配置版本以触发一次新构建；首次固定 schema 构建失败时，旧活动版本及旧 `run_...` schema 继续可查。先在服务和平台分别完成配置，再启用平台的 Git 订阅与 dbt 运行服务开关。

本地校验可从 `dbt-metricflow-service` 的环境执行 `dbt build --project-dir <本仓库路径> --profiles-dir <profile目录> --target starrocks`。本地运行时需自行设置 `DBT_PLATFORM_SCHEMA` 为专用测试 schema。构建内的 `calendar_coverage`、`orders_daily_coverage`、`orders_volume_variation` 和 `raw_source_variation` 测试会检查日期边界、每日订单覆盖及各原表的数量波动。原表刷新后，需要重新发布 dbt 运行版本，指标平台才会使用新构建的事实表。

## 同一维度的多条实体路径示例

`models/examples/multi_path/` 提供独立的企业采购示例。三个模型直接生成固定模拟数据，不依赖或修改 `ecommerce_raw`。实体和指标均使用 `demo_` 前缀，与原有电商模型隔离；构建此分支时会新增这三个示例模型及其指标。

每笔采购订单记录实际采购人和归属的企业账户，账户另有一名负责人。采购人和账户负责人都来自 `demo_customers`，因此指标 `demo_purchase_amount` 可以通过两条路径访问同一个 `demo_customers.region` 维度：

```text
demo_purchase_orders ── demo_customer ──────────────────> demo_customers.region
                     └─ demo_account ─> demo_accounts
                                         └─ demo_customer ─> demo_customers.region
```

两条路径分别是：

| 查询维度 | 业务含义 |
| --- | --- |
| `demo_customer__region` | 实际采购人所在地区 |
| `demo_account__demo_customer__region` | 订单所属账户的负责人所在地区 |

所有关联都是 foreign → primary，客户与账户主键唯一，避免金额因关联产生重复。采购人与账户负责人刻意设置为不同客户，以证明同一个维度终点不代表相同统计口径。

四笔订单总额为 500，预期结果如下；“无分组行”表示该路径没有对应地区记录，不是金额为零：

| 地区 | 按采购人地区统计 | 按账户负责人地区统计 |
| --- | ---: | ---: |
| EAST | 300 | 无分组行 |
| NORTH | 50 | 300 |
| SOUTH | 150 | 200 |

### 本地复现与验收

在本仓库根目录使用相邻 `dbt-metricflow-service` 的已有环境执行以下 PowerShell 命令。示例只构建新模型，在系统临时目录中创建独立 DuckDB 数据库；无需 StarRocks 连接或原始数据。沿用项目默认的 `target/` 构建目录，MetricFlow CLI 从其中读取语义清单。

```powershell
$demoProfiles = Join-Path $env:TEMP ("metrics-multi-path-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $demoProfiles | Out-Null
$env:MULTIPATH_DEMO_DB = Join-Path $demoProfiles 'demo.duckdb'
@'
ecommerce_metrics:
  target: local
  outputs:
    local:
      type: duckdb
      path: "{{ env_var('MULTIPATH_DEMO_DB') }}"
      schema: main
      threads: 1
'@ | Set-Content -LiteralPath (Join-Path $demoProfiles 'profiles.yml') -Encoding utf8

$demoScripts = (Resolve-Path ../dbt-metricflow-service/.venv/Scripts).Path
& (Join-Path $demoScripts 'dbt.exe') build --project-dir . --profiles-dir $demoProfiles --select path:models/examples/multi_path
if ($LASTEXITCODE -ne 0) { throw '示例模型构建失败' }
& (Join-Path $demoScripts 'python.exe') scripts/verify_multi_path_dimensions.py --profiles-dir $demoProfiles
if ($LASTEXITCODE -ne 0) { throw '多路径验收失败' }
```

构建包含三个模型及 15 项非空、唯一性和外键校验。验收脚本调用真实 `engine.list_dimensions(metric_names=["demo_purchase_amount"])`，检查两条完整路径、实体顺序及相同的维度来源，再执行两次单路径查询和一次双路径交叉分组查询，核对实际金额。正常运行应打印两条 `PATH` 和三条 `PASS`。

验收脚本放在 `scripts/`，仅供本地手动运行，不属于 dbt 资源目录。不要将它移入 `tests/`：指标平台会采集该目录作为构建输入，发布校验会拒绝其中的 Python 文件；dbt 的 SQL 数据测试仍保留在 `tests/`。

外层读取路径的方式如下；这里的 `engine` 是加载上述构建产物的 MetricFlowEngine：

```python
for dimension in engine.list_dimensions(metric_names=["demo_purchase_amount"]):
    if dimension.name == "region":
        print(
            dimension.dunder_name,
            [entity.element_name for entity in dimension.entity_links],
            dimension.semantic_model_reference.semantic_model_name,
        )
```

返回两项，顺序不影响语义：

```text
demo_customer__region ['demo_customer'] demo_customers
demo_account__demo_customer__region ['demo_account', 'demo_customer'] demo_customers
```

查询时将选中的完整路径传入 `group_by_names`。同时传入两条路径表示按两个业务角色交叉分组，不表示替不同指标分别指定路径。本示例验证一个指标的多路径能力，不增加跨指标路径映射功能。

## 维度显示值映射示例

`models/examples/value_mapping/` 包含三个独立模拟模型，使用配套 dbt/MetricFlow 的正式 `value_mapping` 协议。示例 SQL 只生成固定数据，不依赖或修改电商原表。

| 模型 | 用途 |
| --- | --- |
| `demo_mapping_orders` | 八笔订单；状态、目标状态和渠道保留原始代码；总金额 182 |
| `demo_mapping_status_codes` | 状态显示 semantic model；200 → 成功，404/502 → 失败 |
| `demo_mapping_channels` | 渠道显示 semantic model；1 → 网页，2 → 应用 |

字典模型的 `code` 列声明为 `raw_value` 维度，`label` 列声明为 `display_value` 维度。业务模型通过名称引用 semantic model，不直接填写物理表名；dbt 构建负责创建这些表。原始键由固定模型数据保证唯一，没有增加字典重复键扫描。

业务维度采用 v2 列配置，完整示例见 [schema.yml](models/examples/value_mapping/schema.yml)：

```yaml
- name: status_code
  description: 原始状态用于筛选、分组和排序；仅最终输出替换显示值。
  dimension:
    type: categorical
    value_mapping:
      semantic_model: demo_mapping_status_codes
      value_dimension: raw_value
      display_dimension: display_value
```

`target_status_code` 复用状态字典，`channel_code` 引用渠道字典。一次查询选中这三个维度时，最终 SQL 有三个独立 LEFT JOIN。映射发生在聚合、排序及 LIMIT 之后，显示名称相同也不能合并结果行。

按原始状态升序查询 `demo_mapping_amount`，过滤原始 NULL 后应得到：

| 原始值（仅作对照） | 实际返回的状态显示值 | 金额 |
| --- | --- | ---: |
| 200 | 成功 | 100 |
| 404 | 失败 | 50 |
| 502 | 失败 | 10 |
| 503 | `503`（字典显示值为 NULL） | 5 |
| 504 | 空字符串 | 6 |
| 599 | `599`（字典无此键） | 4 |

原始 NULL 单独查询仍返回 NULL，金额为 7。用户 20 同时出现在 404 和 502；`demo_mapping_users` 在两行均为 1，`demo_mapping_amount_per_user` 分别为 50 和 10，证明去重计数和比率没有按显示值重算。`DIMENSION_VALUES` 返回原始数字代码，可继续用于筛选。

### 构建与查询验收

在本仓库根目录执行以下 PowerShell 命令。使用已包含该协议扩展和 v2 列解析修复的相邻服务环境；保留项目默认 `target/` 目录供原生 CLI 加载。首次使用修复后的 dbt 应关闭 partial parse，避免复用旧版本丢失映射的缓存。

```powershell
$mappingProfiles = Join-Path $env:TEMP ("metrics-value-mapping-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $mappingProfiles | Out-Null
$env:VALUE_MAPPING_DEMO_DB = Join-Path $mappingProfiles 'demo.duckdb'
@'
ecommerce_metrics:
  target: local
  outputs:
    local:
      type: duckdb
      path: "{{ env_var('VALUE_MAPPING_DEMO_DB') }}"
      schema: main
      threads: 1
'@ | Set-Content -LiteralPath (Join-Path $mappingProfiles 'profiles.yml') -Encoding utf8

$mappingScripts = (Resolve-Path ../dbt-metricflow-service/.venv/Scripts).Path
& (Join-Path $mappingScripts 'dbt.exe') build --no-partial-parse --project-dir . --profiles-dir $mappingProfiles --select path:models/examples/value_mapping
if ($LASTEXITCODE -ne 0) { throw '维值映射示例构建失败' }
& (Join-Path $mappingScripts 'python.exe') scripts/verify_value_mapping.py --profiles-dir $mappingProfiles
if ($LASTEXITCODE -ne 0) { throw '维值映射查询验收失败' }
```

构建应报告 **3 个模型、10 项数据测试通过**。查询脚本调用原生 adapter 配置校验、维度发现和 query/explain，检查映射节点及 SQL，并输出三条 `MAPPING` 和十条 `PASS`。覆盖原始分组、筛选、排序、LIMIT、多维度映射、同字典复用、各类回退、空结果类型、去重计数、比率、原值查询及无映射总额。结果按完整行比较，不按显示标签转成字典，避免错误地覆盖两个“失败”行。

验收脚本仅放在 `scripts/`，不作为 dbt 数据测试发布。上述命令验证 DuckDB 的真实构建和查询。StarRocks 使用前文的独立测试 schema 和连接配置，查询使用服务的 StarRocks adapter。

2026-10-15 在 StarRocks 3.5.19 验证了全量构建（11 个模型、54 项数据测试）、服务查询探针和上述十组映射查询。示例的 NULL 分支必须放在 `UNION ALL` 首位，以便 StarRocks CTAS 正确推断可空列；否则插入 NULL 状态码或显示值会报 `Insert has filtered data`。服务还需包含 MetricFlow 映射校验对 `INT` 数值类型别名的修复，避免将 `INT` 与 `SMALLINT` 误判为不兼容。

