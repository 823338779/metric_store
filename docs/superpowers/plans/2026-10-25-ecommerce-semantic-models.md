# 电商四模型实施计划

> 执行方式：使用 superpowers:executing-plans 在当前目录连续执行，不创建 worktree；用户已确认方案和直接实施。

**目标：** 用 `ecommerce_dw` 构建四个真实电商语义模型及十二个指标。

**架构：** dbt source → 四个模型，订单明细关联唯一订单头；MetricFlow 使用已有内联语义 YAML 协议，时间骨架独立生成。

**技术：** 当前服务虚拟环境中的 dbt、dbt-starrocks、MetricFlow；不新增依赖。

**设计：** [四模型设计](../specs/2026-10-25-ecommerce-semantic-models-design.md)

## 全局约束

- 源 schema 固定 `ecommerce_dw`，不使用 seed 或固定模拟业务行。
- 只保留 orders/users/products/stores 四个语义模型；time_spine 非语义。
- 成交只统计 COMPLETED，金额来自明细且不含运费。
- 所有字段、模型和指标写中文说明；秘密只存临时 profile，不进入 Git。
- 替换旧示例时同步替换专用验收脚本，保留原有粒度、关联和去重验证强度。
- 不改其他产品，不推送、不发布；计划完成后一个 commit。

## 重点验证

1. 一单多商品：订单去重，金额无扇出，逐单与订单头对账。
2. 非成交状态仍有 paid_amount：成交指标为零、客单价 NULL。
3. 无效关联或重复主键：source 与模型测试必须失败，不默默丢行。
4. 早于源日期表的注册日期：完整骨架覆盖、按月新增指标可查询。
5. 当前维度快照：不提供假历史存量，README 明确时间筛选语义。

## 任务 1：模型、指标、验收整体迁移

**文件：** 新增 `models/ecommerce/{orders,users,products,stores}.sql`、`sources.yml`、`schema.yml`，修改 `models/time_spine.*`，新增 `tests/ecommerce_*.sql` 和 `scripts/verify_ecommerce.py`，更新 README，删除 `models/order_business/`、`models/multi_fact/` 及三份旧专用验收脚本。

**接口：** 读取五张已核实 source 表；输出设计中的四模型、十二指标和 user/product/store 维度路径。

- [x] 先编写验收脚本：断言 manifest 只包含四个语义模型和十二个指标，对现有 manifest 执行并确认失败。
- [x] 编写 source、四个 SQL 和内联语义 YAML；补主键/关系/非空和逐单对账、日期覆盖测试。
- [x] 用临时 profile 在独立 schema 执行 README 中的 dbt build，所有数据测试通过。
- [x] 通过真实 MetricFlow QUERY/EXPLAIN 与源 SQL 逐行比较总额、状态、商品、用户、店铺组合及月度指标。
- [x] 更新 README 的数据来源、指标口径、支持命令与发布说明。
- [x] 运行最终测试、独立审查、检查根仓库和产品仓库差异，再提交本计划变更一次。

## 执行记录

已确认源表主键唯一，订单明细的订单/用户/商品/店铺引用无缺失；全量逐单 gross、paid（扣运费）、quantity 对账均无差异。


完成证据：契约脚本在旧 manifest 上因旧模型集合而失败；新构建识别 5 个物理模型、4 个语义模型、12 个指标，45 项数据测试全部通过。14 组 MetricFlow QUERY 与 EXPLAIN SQL 均与源 SQL 完整结果一致。独立只读审查未发现 Critical/Important 问题。

执行调整：上游 MetricFlow CLI 不识别 StarRocks，且硬编码加载工程 target。验收脚本采用与既有服务一致的 SQL renderer，通过 dbt adapter 执行，显式加载本次指定 manifest 旁的 semantic_manifest；不修改依赖或导入相邻服务实现。此验收不代替 HTTP 发布链路测试。

交付范围：仅 metrics_store 本地提交；不推送、不发布、不清理历史数据库表。真实构建使用独立验收 schema，ecommerce_dw 仅只读。
