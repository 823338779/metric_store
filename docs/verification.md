# 初始化验证结果

验证日期：2026-10-10。全部基于实际运行，合成业务日期为 2020—2027。

- dbt Core 1.11.15，dbt-duckdb 1.10.1，DuckDB 1.5.6，Python 3.12。
- `dbt build --profiles-dir .`：16 个模型、59 项数据测试，PASS=75，WARN=0，ERROR=0。
- `python -m unittest discover -s tests_python -v`：4 项集成测试通过。
- `dbt docs generate --profiles-dir .`：文档目录生成成功。
- `python scripts/validate_data.py`：五张业务源表共 2,107,384 行，订单和明细覆盖全部 2,922 天，每天订单 100—300 笔。
- 源表数 5，语义模型数 5，指标数 24。用户 58,440，店铺 30，商品 300，订单 585,732，订单明细 1,462,882。

验证内容包括闰日与日期边界、主外键、商品店铺归属、订单与明细金额、退款不超过支付，以及逐日追加/重复运行/历史更正回补与全量重建的数据指纹一致性。独立只读审查发现并修复了全量重建错误应用回补下界的问题，回归测试涵盖首次建表与全量重建两种场景。

适配器全量刷新可能保留 `__dbt_backup` 内部备份表；集成测试排除这些内部关系，比较两张事实表和四张汇总表的全部内容。它们不是新增核心业务表。

本地生成物：`data/ecommerce.duckdb`、`target/manifest.json`、`target/semantic_manifest.json`、`target/catalog.json`、`target/index.html`。数据库、运行日志、虚拟环境与 target 由 Git 忽略，源代码和依赖锁文件可以复现。

## Databricks 方言修复验证（2026-10-10）

在实际 Databricks SQL warehouse 复现 `generate_series` 无法解析的错误后，日期序列改为按适配器生成。Databricks 使用 `explode(sequence(...))`；日期维度使用对应 ISO 周表达式，日期键改用年月日整数计算；增量策略使用 `merge`。DuckDB 分支保留原有行为。

- 使用 dbt Core 1.11.8 + dbt-databricks 1.11.8，通过现有工作区连接在 `cjl.metric_store_verify*` 独立 schema 执行完整 `dbt build`：16 个模型和 59 项测试全部通过，PASS=75，WARN=0，ERROR=0。
- 在 Databricks 上直接验证日历共 2,922 天；2021-01-01 属于 ISO 2020 年第 53 周，2024-12-30 属于 ISO 2025 年第 1 周；原订单源表每日覆盖检查返回 0 个缺失日期。
- 本地 Python 完整测试套件现为 6 项，全部通过，包含日历边界、Parquet 无损导出和原有增量/回补测试。
- Databricks 上再次构建两张增量事实表：2 个模型和 20 项关联测试通过，PASS=22。重跑前后订单 585,732 行、明细 1,462,882 行，主键去重数及完整行哈希指纹一致，验证了 `merge` 幂等性；日志为 `data/databricks-merge.log`。
- 本次通过本地 dbt CLI 连接真实 Databricks 验证；用户的 dbt 平台 Job 需要同步修改后的 Git 分支再运行。没有自动推送代码或触发平台 Job。

复现环境依赖见 `requirements-databricks.txt`，本地日志在 `data/databricks-build.log`。令牌仅通过进程环境传递，并使用 dbt 的 secret 环境变量命名；没有写入 profile 文件。
