# 电商指标 dbt 项目

本仓库根目录是 dbt 项目。原始数据独立存放在 StarRocks 的 `ecommerce_raw` 数据库，由 [raw_bootstrap.sql](raw_bootstrap.sql) 直接创建；dbt 仅通过 `source()` 读取原表并构建维表、事实表和指标，不创建或写入原表。脚本使用 `CREATE TABLE IF NOT EXISTS`，重复执行不会覆盖已有表。首次执行前请确认 `ecommerce_raw` 未用于其他业务。

原始订单覆盖 **2020-01-01 至 2027-12-31** 共 2,922 天，每天 24 笔，每单两条商品明细，总计 70,128 笔订单和 140,256 条明细；另有 1,200 名用户、40 款商品和 8 家店铺。订单状态包含已支付、取消和退款；销售渠道、折扣、客户等级、商品类目与品牌、店铺类型均按确定性规则变化。

`ecommerce_raw.users`、`products`、`shops`、`orders`、`order_items`、`payments`、`refunds` 是 StarRocks 中的七张原表，在 dbt 中声明为 source。`dim_users`、`dim_products`、`dim_shops` 与 `fct_order_items` 提供 MetricFlow 可关联的语义模型，`time_spine` 从订单日期构建时间骨架。指标包括 `revenue`（已支付成交金额）、`gross_amount`（所有订单折后金额）、`refund_amount`（退款金额）、`units_sold`（已支付商品件数）、`order_count`（去重已支付订单数）和 `average_order_value`（平均已支付订单金额）。可按日期、用户地区与等级、商品类目与品牌、店铺类型等维度查询。

数据完全为示例数据，不包含真实业务记录或凭据。先在目标 StarRocks 执行 `raw_bootstrap.sql`，并授予 dbt 运行账号读取 `ecommerce_raw` 和创建运行 schema 的权限。指标平台发布时会从本仓库 `main` 的固定提交读取 dbt 项目，在独立的 StarRocks schema 中执行全量 `dbt build`；原表不属于该构建的管理范围。

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

运行服务的项目绑定使用 `projectId: ecommerce_metrics`、`projectSubdir: .`、`profileBindingId: starrocks`，`remote` 指向本仓库。指标平台的 Git 配置应使用相同的项目和 profile 绑定。先在服务和平台分别完成配置，再启用平台的 Git 订阅与 dbt 运行服务开关。

本地校验可从 `dbt-metricflow-service` 的环境执行 `dbt build --project-dir <本仓库路径> --profiles-dir <profile目录> --target starrocks`。本地运行时需自行设置 `DBT_PLATFORM_SCHEMA` 为专用测试 schema。构建内的 `calendar_coverage` 和 `orders_daily_coverage` 测试会检查日期边界与每日订单数。

