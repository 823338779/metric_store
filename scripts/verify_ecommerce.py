"""校验电商四模型契约，并将真实 MetricFlow 查询与源数据 SQL 对账。"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
from decimal import Decimal
from pathlib import Path

# 固定公开模型和指标集合，禁止残留旧模拟业务或额外语义模型。
MODELS = {"orders", "users", "products", "stores"}
METRICS = {
    "order_count", "completed_order_count", "sales_amount", "sales_quantity",
    "buyer_count", "average_order_value", "user_count", "new_user_count",
    "product_count", "active_product_count", "store_count", "new_store_count",
}
ORDER_METRICS = (
    "order_count", "completed_order_count", "sales_amount", "sales_quantity",
    "buyer_count", "average_order_value",
)
ORDER_EXPRESSIONS = """
count(distinct o.order_id) as order_count,
count(distinct case when o.order_status = 'COMPLETED' then o.order_id end) as completed_order_count,
sum(case when o.order_status = 'COMPLETED' then i.item_paid_amount else 0 end) as sales_amount,
sum(case when o.order_status = 'COMPLETED' then i.quantity else 0 end) as sales_quantity,
count(distinct case when o.order_status = 'COMPLETED' then o.customer_key end) as buyer_count,
sum(case when o.order_status = 'COMPLETED' then i.item_paid_amount else 0 end)
 / nullif(count(distinct case when o.order_status = 'COMPLETED' then o.order_id end), 0)
 as average_order_value
"""
ORDER_FROM = """
from ecommerce_dw.fact_order_items i
join ecommerce_dw.fact_orders o on i.order_id = o.order_id
join ecommerce_dw.dim_customer u on o.customer_key = u.customer_key
join ecommerce_dw.dim_product p on i.product_key = p.product_key
join ecommerce_dw.dim_store s on o.store_key = s.store_key
"""
HEADER_SQL = """
select count(distinct order_id) as order_count,
count(distinct case when order_status = 'COMPLETED' then order_id end) as completed_order_count,
sum(case when order_status = 'COMPLETED' then paid_amount - shipping_amount else 0 end) as sales_amount,
sum(case when order_status = 'COMPLETED' then total_items else 0 end) as sales_quantity,
count(distinct case when order_status = 'COMPLETED' then customer_key end) as buyer_count,
sum(case when order_status = 'COMPLETED' then paid_amount - shipping_amount else 0 end)
 / nullif(count(distinct case when order_status = 'COMPLETED' then order_id end), 0)
 as average_order_value
from ecommerce_dw.fact_orders
"""
USER_SQL = """
select count(distinct customer_key) as user_count, count(distinct customer_key) as new_user_count
from ecommerce_dw.dim_customer
"""
PRODUCT_SQL = """
select count(distinct product_key) as product_count,
count(distinct case when is_active = 1 then product_key end) as active_product_count
from ecommerce_dw.dim_product
"""
STORE_SQL = """
select count(distinct store_key) as store_count, count(distinct store_key) as new_store_count
from ecommerce_dw.dim_store
"""
EARLY_USERS_SQL = """
select date_trunc('month', register_date) as metric_time__month,
count(distinct customer_key) as new_user_count
from ecommerce_dw.dim_customer
where register_date >= cast('2019-01-01' as date) and register_date < cast('2020-01-01' as date)
group by date_trunc('month', register_date)
"""
SOURCE_STATE_FILTER = "o.order_status = 'CANCELLED'"
SEMANTIC_STATE_FILTER = "{{ Dimension('order_item__order_status') }} = 'CANCELLED'"
TARGET_ENV = "DBT_TARGET_PATH"
NUMERIC_TYPES = (int, float, Decimal)


def verify_manifest(path: Path) -> None:
    """从 dbt 实际产物验证对外契约，而非只匹配 YAML 文本。"""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    models = {model["name"] for model in manifest["semantic_models"].values()}
    metrics = {metric["name"] for metric in manifest["metrics"].values()}
    assert models == MODELS, f"语义模型不符：{models}"
    assert metrics == METRICS, f"指标不符：{metrics}"
    assert not any(node["resource_type"] == "seed" for node in manifest["nodes"].values())
    print("PASS: 四个语义模型、十二个指标，无 seed")


def compare_tables(actual, expected, columns: tuple[str, ...], name: str) -> None:
    """按完整行比较，日期统一为 ISO，金额与比率只容忍浮点舍入。"""
    def ordered(table):
        assert set(table.column_names) == set(columns), (name, table.column_names)
        indexes = [table.column_names.index(column) for column in columns]
        rows = [tuple(row[index] for index in indexes) for row in table.rows]
        return sorted(rows, key=lambda row: tuple(str(value) for value in row))

    left, right = ordered(actual), ordered(expected)
    assert len(left) == len(right), (name, len(left), len(right))
    for arow, erow in zip(left, right):
        for a, e in zip(arow, erow):
            if isinstance(a, NUMERIC_TYPES) and isinstance(e, NUMERIC_TYPES):
                assert math.isclose(float(a), float(e), rel_tol=1e-10, abs_tol=1e-6), (name, a, e)
            elif isinstance(a, (datetime.date, datetime.datetime)) and isinstance(e, (datetime.date, datetime.datetime)):
                assert a.isoformat()[:10] == e.isoformat()[:10], (name, a, e)
            else:
                assert a == e, (name, a, e)


def verify_queries(profiles: Path, manifest: Path) -> None:
    """每组真实查询和 EXPLAIN SQL 都与独立源查询比较，不固定数据总量。"""
    from dbt_metricflow.cli.cli_configuration import CLIConfiguration
    from dbt.adapters.factory import get_adapter_by_type
    from dbt_metricflow.cli.dbt_connectors.adapter_backed_client import AdapterBackedSqlClient
    from metricflow.engine.metricflow_engine import MetricFlowEngine, MetricFlowQueryRequest, MetricFlowQueryType
    from metricflow.protocols.sql_client import SqlEngine
    from metricflow.sql.render.duckdb_renderer import DuckDbSqlPlanRenderer
    from metricflow_semantics.model.semantic_manifest_lookup import SemanticManifestLookup
    from metricflow_semantics.model.dbt_manifest_parser import parse_manifest_from_dbt_generated_manifest

    # 上游 CLI 未枚举 StarRocks；验收与现有服务一样使用标准聚合渲染及 dbt adapter 执行。
    class ValidationSqlClient(AdapterBackedSqlClient):
        def __init__(self, adapter):
            self._adapter = adapter
            self._sql_engine_type = SqlEngine.DUCKDB
            self._sql_plan_renderer = DuckDbSqlPlanRenderer()

    os.environ[TARGET_ENV] = str(manifest.resolve().parent)
    configuration = CLIConfiguration()
    configuration.setup(dbt_profiles_path=profiles,
                        dbt_project_path=Path(__file__).resolve().parents[1], configure_file_logging=False)
    client = ValidationSqlClient(get_adapter_by_type(configuration.dbt_project_metadata.profile.credentials.type))
    # CLI 默认硬编码 target；显式加载同一次构建的语义产物，避免误读旧模拟模型。
    semantic_manifest = parse_manifest_from_dbt_generated_manifest(
        manifest.with_name("semantic_manifest.json").read_text(encoding="utf-8")
    )
    engine = MetricFlowEngine(semantic_manifest_lookup=SemanticManifestLookup(semantic_manifest), sql_client=client)
    dimensions = {item.dunder_name for item in engine.list_dimensions(metric_names=list(ORDER_METRICS))}
    assert {"user__member_level", "product__brand_name", "store__store_type"} <= dimensions
    request = MetricFlowQueryRequest.create

    def check(name, query, source_sql, columns):
        expected = client.query(source_sql)
        actual = engine.query(query).result_df
        assert actual is not None, name
        compare_tables(actual, expected, columns, name)
        explained = client.query(engine.explain(query).sql_statement.sql)
        compare_tables(explained, expected, columns, name)
        print(f"PASS: {name}，{len(expected.rows)} 组，QUERY / EXPLAIN 与源 SQL 一致")

    # 总额基准来自订单头，独立于模型的明细聚合，能发现一单多商品导致的扇出。
    check("订单全部指标与订单头对账", request(metric_names=list(ORDER_METRICS)), HEADER_SQL, ORDER_METRICS)
    for name, metrics, sql in (
        ("用户总数", ("user_count", "new_user_count"), USER_SQL),
        ("商品及在售总数", ("product_count", "active_product_count"), PRODUCT_SQL),
        ("店铺总数", ("store_count", "new_store_count"), STORE_SQL),
    ):
        check(name, request(metric_names=list(metrics)), sql, metrics)

    # 路径组合覆盖事实自身、三张维表、同名省份字段和聚合时间。
    for name, paths, expressions in (
        ("订单状态与零成交比率", ("order_item__order_status",), ("o.order_status",)),
        ("商品类目及品牌", ("product__category_level1", "product__brand_name"), ("p.category_level1", "p.brand_name")),
        ("用户会员等级", ("user__member_level",), ("u.member_level",)),
        ("店铺类型", ("store__store_type",), ("s.store_type",)),
        ("用户与店铺省份交叉", ("user__province", "store__province"), ("u.province", "s.province")),
        ("三个维表同时关联", ("user__member_level", "product__brand_name", "store__store_type"), ("u.member_level", "p.brand_name", "s.store_type")),
        ("按月成交", ("metric_time__month",), ("date_trunc('month', o.order_date)",)),
    ):
        select = ", ".join(f"{expr} as {path}" for path, expr in zip(paths, expressions))
        sql = f"select {select}, {ORDER_EXPRESSIONS} {ORDER_FROM} group by {', '.join(expressions)}"
        check(name, request(metric_names=list(ORDER_METRICS), group_by_names=list(paths)), sql, (*paths, *ORDER_METRICS))

    check("取消订单筛选", request(metric_names=list(ORDER_METRICS), where_constraints=[SEMANTIC_STATE_FILTER]),
          f"select {ORDER_EXPRESSIONS} {ORDER_FROM} where {SOURCE_STATE_FILTER}", ORDER_METRICS)
    check("2019 年注册月份", request(metric_names=["new_user_count"], group_by_names=["metric_time__month"],
          time_constraint_start=datetime.datetime(2019, 1, 1), time_constraint_end=datetime.datetime(2019, 12, 31)),
          EARLY_USERS_SQL, ("metric_time__month", "new_user_count"))
    check("订单状态维值", request(metric_names=["sales_amount"], group_by_names=["order_item__order_status"],
          query_type=MetricFlowQueryType.DIMENSION_VALUES),
          "select distinct order_status as order_item__order_status from ecommerce_dw.fact_orders",
          ("order_item__order_status",))


def main() -> None:
    """先检查契约，实际查询验收在提供 profile 时执行。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("target/manifest.json"))
    parser.add_argument("--profiles-dir", type=Path)
    args = parser.parse_args()
    verify_manifest(args.manifest)
    if args.profiles_dir:
        verify_queries(args.profiles_dir, args.manifest)


if __name__ == "__main__":
    main()
