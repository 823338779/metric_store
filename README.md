# 企业采购订单指标示例

本仓库是独立 dbt 工程，只保留企业采购订单业务。六笔固定模拟订单及四笔退款不依赖任何原始数据库。旧电商模型、原始数据生成脚本及两套独立示例已移除；保留 `ecommerce_metrics` 工程名和 profile 名以兼容现有运行绑定。

## 模型与指标

[业务 YAML](models/order_business/schema.yml) 定义六个语义模型、五个指标及数据测试。同目录 SQL 生成固定模拟数据；另有一个日粒度 `time_spine` 模型。

| 模型 | 粒度与用途 |
| --- | --- |
| order_demo_orders | 一行一笔订单，金额使用 decimal(18, 2) |
| order_demo_customers | 一行一个客户，采购人与负责人共用地区维度 |
| order_demo_accounts | 一行一个账户，每个账户只有一位负责人 |
| order_demo_regions | 地区原值到中文显示值的唯一字典 |
| order_demo_statuses | 状态原值到中文显示值的唯一字典 |
| order_demo_channels | 渠道原值到中文显示值的唯一字典 |

订单日期均为 **2026-10-01**。客户 1、2、3 分别属于 EAST、NORTH、SOUTH；账户 10、20 的负责人分别为客户 2、3。

| 订单 | 采购人 | 账户 | 状态 | 渠道 | 金额（元） |
| --- | --- | --- | --- | --- | ---: |
| 1001 | 1 | 10 | 20 | 1 | 100 |
| 1002 | 1 | 20 | 30 | 2 | 200 |
| 1003 | 2 | 10 | 20 | 1 | 50 |
| 1004 | 3 | 10 | 30 | 2 | 150 |
| 1005 | 1 | 20 | 40 | 1 | 120 |
| 1006 | 3 | 10 | 41 | 99 | 180 |

| 指标 | 口径 | 总体预期 |
| --- | --- | ---: |
| order_demo_order_amount | 所有订单金额合计 | 800 |
| order_demo_paid_amount | 状态 20、30 的订单金额合计 | 500 |
| order_demo_paid_order_count | 状态 20、30 的订单 ID 去重数 | 4 |
| order_demo_paid_buyer_count | 状态 20、30 的采购人 ID 去重数 | 3 |
| order_demo_average_order_value | 已支付金额 ÷ 已支付订单数 | 125 |

无已支付订单的分组中，已支付金额与两个计数为 0，客单价为 NULL。上述五个原订单指标不扣减退款；退款金额由下文 metric_b 单独统计。

## 多通路与维值映射

两条完整地区路径访问相同客户模型中的 `region_code`：

- `order_demo_customer__region_code`：采购人所在地区。
- `order_demo_account__order_demo_customer__region_code`：账户负责人所在地区。

所有关联为 foreign → primary；客户、账户和字典原始键均有唯一性测试。两条路径同时分组表示角色交叉分析。

| 地区 | 采购人已支付金额 | 负责人已支付金额 |
| --- | ---: | ---: |
| 华东 | 300 | 无分组行 |
| 华北 | 50 | 300 |
| 华南 | 150 | 200 |

`value_mapping` 使用配套 dbt/MetricFlow 扩展协议，在原始筛选、聚合、排序和 LIMIT 之后映射：

- EAST/NORTH/SOUTH 显示为华东/华北/华南；两个路径复用字典，独立映射。
- 20/30 显示为已支付/已完成；40 用户取消和 41 超时关闭都显示已关闭，仍保留金额 120、180 两行。
- 1/2 显示为网页/应用；99 无映射时回退为文本 99。
- `DIMENSION_VALUES` 返回原值，状态仍是数字 20、30、40、41。

## 本地构建与验收

在本仓库执行，使用相邻服务的已有环境。profile 与 DuckDB 放在系统临时目录，构建产物放在 Git 忽略的 `target/`。

```powershell
$orderProfiles = Join-Path $env:TEMP ("order-business-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $orderProfiles | Out-Null
$env:ORDER_DEMO_DB = Join-Path $orderProfiles 'demo.duckdb'
```

在 `$orderProfiles/profiles.yml` 写入：

```yaml
ecommerce_metrics:
  target: local
  outputs:
    local:
      type: duckdb
      path: "{{ env_var('ORDER_DEMO_DB') }}"
      schema: main
      threads: 1
```

```powershell
$orderScripts = (Resolve-Path ../dbt-metricflow-service/.venv/Scripts).Path
& (Join-Path $orderScripts 'dbt.exe') build --no-partial-parse --project-dir . --profiles-dir $orderProfiles
if ($LASTEXITCODE -ne 0) { throw '订单工程构建失败' }
& (Join-Path $orderScripts 'python.exe') scripts/verify_order_business.py --profiles-dir $orderProfiles
if ($LASTEXITCODE -ne 0) { throw '订单组合查询验收失败' }
```

完整构建包含 **12 个模型、57 项数据测试、7 个指标**。原订单验收包含路径发现和十组真实查询，同时执行 EXPLAIN 生成的 SQL，并检查最外层映射节点。按完整行比较，避免覆盖同名状态。

## 跨事实表双指标与多通路查询

[跨表业务 YAML](models/multi_fact/schema.yml) 额外定义五个语义模型，复用原有六笔订单和地区字典。

| 对象 | 物理来源或路径 | 含义 |
| --- | --- | --- |
| metric_a | multi_fact_orders | 订单金额，六笔合计 800 元 |
| metric_b | multi_fact_refunds | 退款金额，四笔合计 155 元 |
| consumer__dima | 事实表 → multi_fact_consumers | 购买人地区 |
| account__dimb | 事实表 → multi_fact_accounts | 账户类型 |
| account__consumer__dima | 事实表 → multi_fact_accounts → multi_fact_consumers | 账户负责人地区 |

退款 9001/9002 分别对应订单 1001 的 20/30 元退款，9003 对应订单 1002 的 80 元退款，9004 对应订单 1004 的 25 元退款。退款模型只从唯一订单键取得购买人与账户，不引入订单金额。语义查询分别聚合订单事实和退款事实，再按共同维度组合；一单多笔退款不会放大订单金额。无退款的组合保留 NULL，不伪装成有退款记录的零元。

两个指标同时按 `consumer__dima, account__dimb` 分组的预期结果：

| consumer__dima | account__dimb | metric_a | metric_b |
| --- | --- | ---: | ---: |
| 华东 | 企业账户 | 100 | 50 |
| 华东 | 渠道账户 | 320 | 80 |
| 华北 | 企业账户 | 50 | NULL |
| 华南 | 企业账户 | 330 | 25 |

三个分组字段也可同时使用；账户 10 的负责人来自华北，账户 20 的负责人来自华南。地区及账户类型均在聚合后映射成中文，筛选和 DIMENSION_VALUES 使用原码。两个客户路径共享同一个维度资源，但 optionId 不同；必须用同时选中 metric_a、metric_b 后发现的共同维度选项。

订单日期为 2026-10-01，退款日期为 2026-10-02。按聚合时间查询时，各指标按自己的业务发生日期计入，不能将当日退款金额解释成当日订单的退款金额。

```powershell
& (Join-Path $orderScripts 'python.exe') scripts/verify_multi_fact_business.py --profiles-dir $orderProfiles
if ($LASTEXITCODE -ne 0) { throw '跨事实表多通路验收失败' }
```

本地额外验收五组查询及对应 EXPLAIN SQL，包含总额、购买人加账户类型、双客户路径、三维显示映射和双路径原码筛选。

## 通过 dbt-service 构建、发布与查询

服务必须已初始化并配置可信 StarRocks 实例、凭据引用和 SERVICE_TOKEN，启动与配置见相邻服务 README。使用独立演示 schema；删除 Git 模型不会自动删除历史数据库表。

1. 将工程提交并推送到所选远端分支；服务只读取远端 Git，不读取本地未提交文件。
2. 向 `POST /builds` 提交以下完整执行快照，将占位符替换为实际值。重复同一次请求时保留幂等键。
3. 读取 `GET /builds/{buildId}`，等待 `buildStatus=SUCCEEDED`；失败时读取 `/logs`。
4. `ON_SUCCESS` 在构建成功后尝试发布；还需读取 `GET /deployments/current?repository=...&environmentId=...&branchName=...`，确认 `activeBuildId` 等于本次 buildId。构建成功不等于发布成功。

```json
{
  "repository": "http://127.0.0.1:3000/agent-admin/metrics.git",
  "branchName": "main",
  "commitSha": "<完整远端提交 SHA>",
  "execution": {
    "environmentId": "<独立演示环境 UUID>",
    "configVersion": 1,
    "connection": {
      "type": "starrocks",
      "instanceId": "warehouse",
      "host": "127.0.0.1",
      "port": 9030
    },
    "credentialRef": "warehouse-readwrite",
    "catalog": "default_catalog",
    "schema": "<独立演示 schema>",
    "threads": 1,
    "businessTimezone": "Asia/Shanghai"
  },
  "deploymentPolicy": "ON_SUCCESS",
  "idempotencyKey": "<本次构建唯一请求键>"
}
```

POST 使用 `Authorization: Bearer <SERVICE_TOKEN>`。凭据只通过运行环境提供，不写入工程。

发布后，先从目录读取资源 ID，再按所选指标集合调用 `POST /query/available-dimensions?build_id={buildId}` 获取 optionId。两个地区选项的 resourceId 相同、optionId 不同；displayName 包含角色路径。查询必须使用该 buildId 和同一指标集合的 optionId，不能跨构建复用。

```powershell
# SERVICE_TOKEN 由当前终端的受保护环境注入。
& (Join-Path $orderScripts 'python.exe') scripts/verify_order_service.py --service-url http://127.0.0.1:8000 --build-id <buildId>
if ($LASTEXITCODE -ne 0) { throw '服务发布与查询验收失败' }
```

服务脚本核对发布指针、目录严格包含七个指标，并通过 HTTP 验证 QUERY、EXPLAIN、PREVIEW、DIMENSION_VALUES。除原有双路径、四维显示映射、原始状态筛选、排序与 LIMIT、同名分组和缺失映射回退外，也验收跨事实表的共同维度发现、双路径和三维组合、双路径原码筛选及维值查询。

本地 MetricFlow 的多跳过滤使用 `Dimension('consumer__dima', entity_path=['account'])`，与分组的完整路径写法不同。HTTP 过滤通过当前指标集合发现的 optionId 指定完整路径；服务脚本同时验收购买人地区和账户负责人地区的原码筛选。

`scripts/` 中的 Python 仅用于手动验收，不能放入 dbt 模型或测试资源目录，服务发布不封存这些脚本。
