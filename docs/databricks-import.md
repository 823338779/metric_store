# Databricks 源数据导入

已于 2026-10-10 使用 IDEA 中配置的 Databricks 数据源连接，将本地 DuckDB 的五张原始表导入该工作区的 `cjl.raw`。源表最初不存在，因此创建了新的 Delta 表，没有替换已有业务表。

| Delta 表 | 行数 |
| --- | ---: |
| `cjl.raw.users` | 58,440 |
| `cjl.raw.shops` | 30 |
| `cjl.raw.products` | 300 |
| `cjl.raw.orders` | 585,732 |
| `cjl.raw.order_items` | 1,462,882 |

订单、明细和用户注册日期覆盖 2020-01-01 至 2027-12-31，共 2,922 天。订单每天 100—300 笔。云端主键唯一性、用户注册时间、店铺/商品/订单关联、支付退款关系和明细金额对账通过；三项订单金额汇总与本地完全一致。实测结果见 [导入报告](databricks-import-report.json)。

导入过程：使用 `scripts/export_sources.py` 导出保留日期、时间戳和定点金额类型的 Parquet 文件；通过已有工作区凭据上传到 Unity Catalog volume；再通过 `CREATE TABLE ... USING DELTA AS SELECT * FROM parquet...` 建立托管表。连接凭据没有写入项目代码或报告。

本地文件位于 `data/databricks-import/`，可以重新导出：

```powershell
.venv/Scripts/python.exe scripts/export_sources.py
```

云端导入文件保存在 `/Volumes/cjl/raw/metric_store_import/load_01a1256c_20261010/`，不需要重新上传或重复插入。五张业务表已经独立落地。

导入解决了 `cjl.raw.orders` 缺失及其他四张源表未加载的问题。后续已补充 Databricks 方言适配：日期测试与日期维度共用 `macros/calendar_dates.sql`，Databricks 使用 `explode(sequence(...))`，DuckDB 保留 `generate_series`；日期维度按适配器选择 ISO 周函数；Databricks 的增量策略改为 `merge`。

将以下四个文件一起同步至 dbt 平台使用的代码分支，再重跑 `dbt build`：

- `macros/calendar_dates.sql`（新增，不能漏传）
- `macros/test_daily_coverage.sql`
- `models/dimensions/dim_date.sql`
- `dbt_project.yml`

云端连接的 catalog 应为 `cjl`，source schema 为 `raw`。本地 Databricks 验证使用独立环境 `.venv-databricks` 和 `requirements-databricks.txt`，没有更改默认 DuckDB profile。dbt 平台使用自身的连接设置，不使用本地 DuckDB 数据库路径。凭据不存入项目。

参考：[Databricks Files API](https://docs.databricks.com/api/files/v2/upload-file)、[Unity Catalog volumes](https://docs.databricks.com/aws/en/volumes/volume-files)。
