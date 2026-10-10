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
