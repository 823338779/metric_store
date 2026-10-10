# 电商 dbt 数据模型

dbt Core 1.11 项目，支持本地 DuckDB 和 Databricks，仅 **5 张核心业务源表**，覆盖 **2020-01-01 至 2027-12-31 全部 2,922 天**（包含两个闰日）。每天随机 100—300 笔订单，每单 1—4 条明细；每天注册 20 个用户。固定种子和锁定依赖保证分批与一次生成结果相同。全部为合成数据，金额 CNY，时间为无时区的本地业务时间，未来日期不代表预测。

## 五张核心表

| 表 | 主要内容 | 关系 |
| --- | --- | --- |
| `raw.users` | 用户、注册日期、省份、会员等级、获客渠道 | `user_id` 主键 |
| `raw.shops` | 店铺、类型、省份、开店日期 | `shop_id` 主键 |
| `raw.products` | SKU、所属店铺、类目、品牌、价格和成本 | `product_id` 主键，关联店铺 |
| `raw.orders` | 用户、店铺、状态、渠道、订单/支付/退款金额及时间 | `order_id` 主键，关联用户及店铺 |
| `raw.order_items` | 订单商品、数量、价格、优惠和成本 | `order_item_id` 主键，关联订单及商品 |

同一订单只含所属店铺商品，用户先注册再下单。商品与店铺为静态目录，用户全集预置 8 年注册记录；订单和明细按指定日期增量写入。支付、退款直接放在订单表，不额外建立业务源表。

## dbt 分层

| 目录 | 模型 |
| --- | --- |
| `models/staging` | 5 个 source 声明和 5 个清洗视图 |
| `models/dimensions` | 用户、店铺、商品、日期 4 个维度 |
| `models/facts` | 订单、订单明细 2 个增量事实表 |
| `models/marts` | 全站日销售、店铺日销售、商品日销售、用户累计交易 4 个汇总表 |
| `models/semantic` | 日时间脊柱，5 个语义模型、24 个指标 |

共 16 个派生 dbt 模型。schema 为 `analytics_staging`、`analytics_dimensions`、`analytics_facts`、`analytics_marts`，时间脊柱在 `analytics`。地理、类目、品牌、渠道等为维度属性。

指标包括下单数、支付金额、退款金额、净收入、毛利、支付用户数、新增用户数、支付件数、客单价、退款率等，见 [指标字典](docs/metrics.md)。使用 dbt 1.11 的 `semantic_models` / `measures` / `metrics` 格式，与依赖版本一起锁定，不混用 1.12+ 新格式。`dbt build` 生成 `target/manifest.json` 和 `target/semantic_manifest.json`，供读取 dbt 元数据的工具使用。未部署托管 Semantic Layer 查询 API；本地直接查询汇总表即可。

## 运行（PowerShell，项目根目录）

当前工作区已初始化。复制项目后或需要重新生成时：

Databricks 中的五张源表也已导入 `cjl.raw`，导入结果和云端适配范围见 [Databricks 导入说明](docs/databricks-import.md)。下面命令针对本地 DuckDB。

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe scripts/generate_data.py
.venv/Scripts/dbt.exe build --profiles-dir .
.venv/Scripts/python.exe scripts/validate_data.py
```

没有 uv 时可用 Python 3.12 的 `python -m venv .venv` 和 `.venv/Scripts/python.exe -m pip install -r requirements.txt`。默认数据库 `data/ecommerce.duckdb`，数据文件及虚拟环境不进入 Git。请勿同时打开写入连接。

生成器在事务内替换指定日期的订单和明细，重复运行不会累加。当前行数和年度汇总见 [数据报告](docs/data-profile.json)。

## 按天追加

用独立示例数据库体验增量，不与已生成的完整数据混用：

```powershell
$env:ECOMMERCE_DB_PATH = Join-Path $PWD 'data/incremental-demo.duckdb'
.venv/Scripts/python.exe scripts/generate_data.py --database $env:ECOMMERCE_DB_PATH --start-date 2020-01-01 --end-date 2020-01-02
.venv/Scripts/dbt.exe build --profiles-dir . --vars "{data_end: '2020-01-02'}"

.venv/Scripts/python.exe scripts/generate_data.py --database $env:ECOMMERCE_DB_PATH --start-date 2020-01-03 --end-date 2020-01-03
.venv/Scripts/dbt.exe build --profiles-dir . --vars "{data_end: '2020-01-03'}"
Remove-Item Env:ECOMMERCE_DB_PATH
```

事实表在 DuckDB 使用 `delete+insert`，在 Databricks 使用 `merge`，均以业务主键去重，重算已有最后一天并追加新日期。维度和汇总重建。指定其他起点时传入 `data_start` 和 `data_end`，源数据须在该范围每天齐全。不要把缩小 `data_end` 当作删除已加载历史的方式。

历史数据更正后，显式回补起点：

```powershell
.venv/Scripts/dbt.exe build --profiles-dir . --vars "{backfill_start: '2023-06-01'}"
```

此命令重算起点至 `data_end` 的事实数据；全量重建忽略回补下界。重新运行生成器会还原该日期的合成订单，覆盖手工更正。删除历史主键、更改造数规则或缩小数据集时，在源数据准备好后用 `dbt build --full-refresh`；常规增量不模拟 CDC 删除。

## 查询与验证

```powershell
.venv/Scripts/python.exe -c "import duckdb; c=duckdb.connect('data/ecommerce.duckdb', read_only=True); c.sql('select * from analytics_marts.mart_daily_sales order by order_date limit 10').show()"
.venv/Scripts/python.exe -m unittest discover -s tests_python -v
.venv/Scripts/dbt.exe docs generate --profiles-dir .
.venv/Scripts/dbt.exe docs serve --profiles-dir . --port 8080
```

dbt 检查每日覆盖、主键唯一性、外键、状态、金额对账和时间关系。Python 集成测试使用临时数据库验证闰日、日期边界、分批一致性、追加、重跑、历史回补与全量重建等价。分析 SQL 在 `analyses/`；原始 example 文件保留但禁用。

## 模拟口径

下单金额含取消单；支付金额为退款前金额；净收入 = 支付 − 退款。取消单不计支付和履约成本。已履约商品成本在退款时不冲回，退款订单可能出现负毛利；毛利不含物流、税费和营销成本。商品销售额为退款前金额，不将订单退款分摊到商品行。

支付退款均在下单当天结束，不模拟跨日状态流转。用户去重数不可跨日相加，比率以聚合分子除以聚合分母计算。
