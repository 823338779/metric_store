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

