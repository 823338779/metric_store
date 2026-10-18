"""通过真实 MetricFlow 查询验收订单多路径与显示映射的组合行为。"""

from __future__ import annotations

import argparse
from pathlib import Path

from dbt_metricflow.cli.cli_configuration import CLIConfiguration
from metricflow.dataflow.nodes.apply_dimension_value_mappings import ApplyDimensionValueMappingsNode
from metricflow.engine.metricflow_engine import MetricFlowEngine, MetricFlowQueryRequest, MetricFlowQueryType
from metricflow.protocols.sql_client import SqlClient

# 固定业务身份与展示值，期望金额来自六笔订单的人工核算。
AMOUNT = "order_demo_order_amount"
PAID = "order_demo_paid_amount"
ORDERS = "order_demo_paid_order_count"
BUYERS = "order_demo_paid_buyer_count"
AVERAGE = "order_demo_average_order_value"
BUYER = "order_demo_customer__region_code"
OWNER = "order_demo_account__order_demo_customer__region_code"
STATUS = "order_demo_order__status_code"
CHANNEL = "order_demo_order__channel_code"
REGION = "region_code"
CUSTOMERS = "order_demo_customers"
REGIONS = "order_demo_regions"
EAST, NORTH, SOUTH = "华东", "华北", "华南"
PAID_LABEL, COMPLETED, CLOSED = "已支付", "已完成", "已关闭"
WEB, APP, UNKNOWN_CHANNEL = "网页", "应用", "99"
STATUS_FILTER = "{{ Dimension('order_demo_order__status_code') }} = 40"
BUYER_FILTER = "{{ Dimension('order_demo_customer__region_code') }} = 'EAST'"
OWNER_FILTER = "{{ Dimension('order_demo_customer__region_code', entity_path=['order_demo_account']) }} = 'NORTH'"
PROFILE_OPTION = "--profiles-dir"
PATH_SEPARATOR = "__"
PASS_PATH = "PASS: 两条路径指向同一地区维度，且都携带显示映射"
PASS_QUERY = "PASS: {} -> {}"


def verify_query(
    engine: MetricFlowEngine,
    sql_client: SqlClient,
    name: str,
    request: MetricFlowQueryRequest,
    expected_rows: tuple[tuple[object, ...], ...],
    expected_columns: tuple[str, ...],
    mapping_count: int,
) -> None:
    """核对完整结果与映射计划，避免同名标签覆盖结果行。"""
    explained = engine.explain(request)
    result = engine.query(request)
    table = result.result_df
    assert table is not None, name
    # 引擎按实体规划输出列顺序；按完整列名取值，仍严格比较全部行与重复标签。
    assert set(table.column_names) == set(expected_columns), (name, table.column_names)
    indexes = [table.column_names.index(column) for column in expected_columns]
    rows = tuple(tuple(row[index] for index in indexes) for row in table.rows)
    assert rows == expected_rows, (name, rows, expected_rows)
    # 多跳规划的临时别名可能不同；直接执行 EXPLAIN 的 SQL 验证语义等价。
    explained_table = sql_client.query(explained.sql_statement.sql)
    assert set(explained_table.column_names) == set(expected_columns), name
    explained_indexes = [explained_table.column_names.index(column) for column in expected_columns]
    explained_rows = tuple(tuple(row[index] for index in explained_indexes) for row in explained_table.rows)
    assert explained_rows == expected_rows, (name, explained_rows)
    # 两条地区路径和两个订单维度必须在最外层分别映射。
    boundary = explained.dataflow_plan.sink_nodes[0].parent_nodes[0]
    if mapping_count:
        assert isinstance(boundary, ApplyDimensionValueMappingsNode), name
        assert len(boundary.mappings) == mapping_count, name
        assert all(column.column_type is str for column in table.column_descriptions[:mapping_count]), name
    else:
        assert not isinstance(boundary, ApplyDimensionValueMappingsNode), name
    print(PASS_QUERY.format(name, rows))


def main() -> None:
    """加载构建产物，验证路径、指标口径、映射节点和真实结果。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(PROFILE_OPTION, required=True, type=Path)
    args = parser.parse_args()
    configuration = CLIConfiguration()
    configuration.setup(
        dbt_profiles_path=args.profiles_dir,
        dbt_project_path=Path(__file__).resolve().parents[1],
        configure_file_logging=False,
    )
    engine = configuration.mf

    # 缺少指标、角色路径或地区映射时立即失败，不允许仅凭 YAML 文本通过验收。
    names = {metric.name for metric in engine.list_metrics(include_dimensions=False)}
    assert {AMOUNT, PAID, ORDERS, BUYERS, AVERAGE} <= names, "缺少订单业务指标"
    dimensions = {item.dunder_name: item for item in engine.list_dimensions(metric_names=[PAID])}
    for path in (BUYER, OWNER):
        dimension = dimensions[path]
        assert dimension.name == REGION
        assert dimension.semantic_model_reference.semantic_model_name == CUSTOMERS
        assert [link.element_name for link in dimension.entity_links] == path.split(PATH_SEPARATOR)[:-1]
        assert dimension.value_mapping.semantic_model == REGIONS
    print(PASS_PATH)

    # 全部结果逐行比较，保留两个同名“已关闭”分组；排序始终使用原始代码。
    request = MetricFlowQueryRequest.create
    cases = (
        ("全部指标口径", request(metric_names=[AMOUNT, PAID, ORDERS, BUYERS, AVERAGE]),
         ((800, 500, 4, 3, 125),), (AMOUNT, PAID, ORDERS, BUYERS, AVERAGE), 0),
        ("采购人地区", request(metric_names=[PAID], group_by_names=[BUYER], order_by_names=[BUYER]),
         ((EAST, 300), (NORTH, 50), (SOUTH, 150)), (BUYER, PAID), 1),
        ("负责人地区", request(metric_names=[PAID], group_by_names=[OWNER], order_by_names=[OWNER]),
         ((NORTH, 300), (SOUTH, 200)), (OWNER, PAID), 1),
        ("双路径交叉", request(metric_names=[PAID], group_by_names=[BUYER, OWNER], order_by_names=[BUYER, OWNER]),
         ((EAST, NORTH, 100), (EAST, SOUTH, 200), (NORTH, NORTH, 50), (SOUTH, NORTH, 150)),
         (BUYER, OWNER, PAID), 2),
        ("四维度映射与渠道回退", request(metric_names=[AMOUNT], group_by_names=[BUYER, OWNER, STATUS, CHANNEL],
                                 order_by_names=[STATUS, BUYER]),
         ((EAST, NORTH, PAID_LABEL, WEB, 100), (NORTH, NORTH, PAID_LABEL, WEB, 50),
          (EAST, SOUTH, COMPLETED, APP, 200), (SOUTH, NORTH, COMPLETED, APP, 150),
          (EAST, SOUTH, CLOSED, WEB, 120), (SOUTH, NORTH, CLOSED, UNKNOWN_CHANNEL, 180)),
         (BUYER, OWNER, STATUS, CHANNEL, AMOUNT), 4),
        ("同名状态不合并", request(metric_names=[AMOUNT], group_by_names=[STATUS], order_by_names=[STATUS]),
         ((PAID_LABEL, 150), (COMPLETED, 350), (CLOSED, 120), (CLOSED, 180)), (STATUS, AMOUNT), 1),
        ("原值状态筛选", request(metric_names=[AMOUNT], group_by_names=[STATUS], where_constraints=[STATUS_FILTER]),
         ((CLOSED, 120),), (STATUS, AMOUNT), 1),
        ("双路径原值筛选", request(metric_names=[PAID], where_constraints=[BUYER_FILTER, OWNER_FILTER]),
         ((100,),), (PAID,), 0),
        ("映射前排序与限制", request(metric_names=[AMOUNT], group_by_names=[STATUS], order_by_names=[STATUS], limit=3),
         ((PAID_LABEL, 150), (COMPLETED, 350), (CLOSED, 120)), (STATUS, AMOUNT), 1),
        ("维值查询保留原码", request(metric_names=[AMOUNT], group_by_names=[STATUS], order_by_names=[STATUS],
                            query_type=MetricFlowQueryType.DIMENSION_VALUES),
         ((20,), (30,), (40,), (41,)), (STATUS,), 0),
    )
    for name, query, rows, columns, mapping_count in cases:
        verify_query(engine, configuration.sql_client, name, query, rows, columns, mapping_count)


if __name__ == "__main__":
    main()
