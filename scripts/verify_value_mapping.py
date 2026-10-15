"""使用实际构建产物验证维值映射，不在 Python 中替换查询值。"""

from __future__ import annotations

import argparse
from pathlib import Path

from dbt_metricflow.cli.cli_configuration import CLIConfiguration
from dbt_metricflow.cli.dbt_connectors.value_mapping_validation import validate_value_mapping_data
from metricflow.dataflow.nodes.apply_dimension_value_mappings import ApplyDimensionValueMappingsNode
from metricflow.engine.metricflow_engine import MetricFlowEngine, MetricFlowQueryRequest, MetricFlowQueryType

# 业务指标与维度均限定在本示例，避免访问尚未构建的电商事实模型。
AMOUNT = "demo_mapping_amount"
USERS = "demo_mapping_users"
AMOUNT_PER_USER = "demo_mapping_amount_per_user"
STATUS = "demo_mapping_order__status_code"
TARGET_STATUS = "demo_mapping_order__target_status_code"
CHANNEL = "demo_mapping_order__channel_code"
SOURCE_MODEL = "demo_mapping_orders"
STATUS_MODEL = "demo_mapping_status_codes"
CHANNEL_MODEL = "demo_mapping_channels"
MAPPING_MODELS = {STATUS_MODEL, CHANNEL_MODEL}
EXPECTED_MAPPINGS = {STATUS: STATUS_MODEL, TARGET_STATUS: STATUS_MODEL, CHANNEL: CHANNEL_MODEL}
LEFT_JOIN = "LEFT OUTER JOIN"
SUCCESS = "成功"
FAILURE = "失败"
WEB = "网页"
APP = "应用"
RAW_503 = "503"
RAW_599 = "599"
EMPTY_LABEL = ""
MAPPING_TEMPLATE = "MAPPING: {} -> {}"
PASS_TEMPLATE = "PASS: {} -> {}"

# 筛选与排序声明引用原始维度；期望结果明确保留显示值相同的两行。
NON_NULL_STATUS = "{{ Dimension('demo_mapping_order__status_code') }} IS NOT NULL"
FAILED_CODES = "{{ Dimension('demo_mapping_order__status_code') }} IN (404, 502)"
ONE_CODE = "{{ Dimension('demo_mapping_order__status_code') }} = 502"
FALLBACK_CODES = "{{ Dimension('demo_mapping_order__status_code') }} >= 503"
NULL_CODE = "{{ Dimension('demo_mapping_order__status_code') }} IS NULL"
MISSING_CODE = "{{ Dimension('demo_mapping_order__status_code') }} = 999"
EXPECTED_ALL = ((SUCCESS, 100), (FAILURE, 50), (FAILURE, 10), (RAW_503, 5), (EMPTY_LABEL, 6), (RAW_599, 4))
EXPECTED_MULTIPLE = ((SUCCESS, FAILURE, WEB, 100), (FAILURE, FAILURE, WEB, 50), (FAILURE, SUCCESS, APP, 10))
EXPECTED_RAW = ((200,), (404,), (502,), (503,), (504,), (599,))
CASE_ALL = "原始分组与排序"
CASE_FAILED = "共享用户的去重计数与比率"
CASE_LIMIT = "原始排序与 LIMIT"
CASE_MULTIPLE = "三维度独立 JOIN、同字典复用"
CASE_FALLBACK = "显示 NULL、空字符串及未匹配回退"
CASE_NULL = "原始 NULL"
CASE_EMPTY = "空结果文本列类型"
CASE_RAW = "维度值保留原始代码与类型"
CASE_FILTER = "仅用于筛选的维度不映射"
CASE_TOTAL = "无分组总额不变"


def verify_query(
    engine: MetricFlowEngine,
    name: str,
    request: MetricFlowQueryRequest,
    expected_rows: tuple[tuple[object, ...], ...],
    expected_columns: tuple[str, ...],
    mapping_count: int,
) -> None:
    """核对数据库返回的完整行、输出类型及显式映射计划。"""
    explained = engine.explain(request)
    result = engine.query(request)
    assert result.result_df is not None, name
    table = result.result_df
    assert table.column_names == expected_columns, (name, table.column_names)
    assert table.rows == expected_rows, (name, table.rows, expected_rows)
    assert result.sql == explained.sql_statement.sql, name

    # 从最终 Write 的父节点核对映射个数；原值查询不应出现映射节点。
    boundary = explained.dataflow_plan.sink_nodes[0].parent_nodes[0]
    if mapping_count:
        assert type(boundary) is ApplyDimensionValueMappingsNode, name
        assert len(boundary.mappings) == mapping_count, name
        assert all(column.column_type is str for column in table.column_descriptions[:mapping_count]), name
    else:
        assert type(boundary) is not ApplyDimensionValueMappingsNode, name
        assert STATUS_MODEL not in result.sql and CHANNEL_MODEL not in result.sql, name
    if name == CASE_MULTIPLE:
        assert result.sql.count(LEFT_JOIN) == 3, result.sql
    if name == CASE_RAW:
        assert table.column_descriptions[0].column_type is not str, name
    print(PASS_TEMPLATE.format(name, table.rows))


def main() -> None:
    """读取本项目的 DuckDB 构建产物并执行配置、发现、SQL 和结果验收。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles-dir", required=True, type=Path)
    arguments = parser.parse_args()
    configuration = CLIConfiguration()
    configuration.setup(
        dbt_profiles_path=arguments.profiles_dir,
        dbt_project_path=Path(__file__).resolve().parents[1],
        configure_file_logging=False,
    )
    engine = configuration.mf
    metric_names = {metric.name for metric in engine.list_metrics(include_dimensions=False)}
    assert {AMOUNT, USERS, AMOUNT_PER_USER} <= metric_names, "缺少维值映射示例指标，请先构建示例模型"

    # 只调用原生校验入口，不自行扫描重复键，也不解析一份服务侧映射协议。
    validate_value_mapping_data(configuration.semantic_manifest_lookup, configuration.dbt_artifacts.adapter)
    dimensions = {dimension.dunder_name: dimension for dimension in engine.list_dimensions(metric_names=[AMOUNT])}
    for path, target in EXPECTED_MAPPINGS.items():
        dimension = dimensions[path]
        assert dimension.semantic_model_reference is not None
        assert dimension.semantic_model_reference.semantic_model_name == SOURCE_MODEL
        assert dimension.value_mapping is not None
        assert dimension.value_mapping.semantic_model == target
        print(MAPPING_TEMPLATE.format(path, target))
    assert all(
        dimension.semantic_model_reference is None
        or dimension.semantic_model_reference.semantic_model_name not in MAPPING_MODELS
        for dimension in engine.list_dimensions()
    ), "字典内部维度不应出现在可用计算维度中"

    # 单维度、多个映射、回退和查询模式均执行真实 SQL，结果不转成会覆盖重复标签的字典。
    grouped = MetricFlowQueryRequest.create
    cases = (
        (
            CASE_ALL,
            grouped(
                metric_names=[AMOUNT],
                group_by_names=[STATUS],
                order_by_names=[STATUS],
                where_constraints=[NON_NULL_STATUS],
            ),
            EXPECTED_ALL,
            (STATUS, AMOUNT),
            1,
        ),
        (
            CASE_FAILED,
            grouped(
                metric_names=[USERS, AMOUNT_PER_USER],
                group_by_names=[STATUS],
                order_by_names=[STATUS],
                where_constraints=[FAILED_CODES],
            ),
            ((FAILURE, 1, 50.0), (FAILURE, 1, 10.0)),
            (STATUS, USERS, AMOUNT_PER_USER),
            1,
        ),
        (
            CASE_LIMIT,
            grouped(
                metric_names=[AMOUNT],
                group_by_names=[STATUS],
                order_by_names=[STATUS],
                where_constraints=[NON_NULL_STATUS],
                limit=2,
            ),
            EXPECTED_ALL[:2],
            (STATUS, AMOUNT),
            1,
        ),
        (
            CASE_MULTIPLE,
            grouped(
                metric_names=[AMOUNT],
                group_by_names=[STATUS, TARGET_STATUS, CHANNEL],
                order_by_names=[STATUS],
                where_constraints=[NON_NULL_STATUS],
                limit=3,
            ),
            EXPECTED_MULTIPLE,
            (STATUS, TARGET_STATUS, CHANNEL, AMOUNT),
            3,
        ),
        (
            CASE_FALLBACK,
            grouped(
                metric_names=[AMOUNT],
                group_by_names=[STATUS],
                order_by_names=[STATUS],
                where_constraints=[FALLBACK_CODES],
            ),
            EXPECTED_ALL[3:],
            (STATUS, AMOUNT),
            1,
        ),
        (
            CASE_NULL,
            grouped(metric_names=[AMOUNT], group_by_names=[STATUS], where_constraints=[NULL_CODE]),
            ((None, 7),),
            (STATUS, AMOUNT),
            1,
        ),
        (
            CASE_EMPTY,
            grouped(metric_names=[AMOUNT], group_by_names=[STATUS], where_constraints=[MISSING_CODE]),
            (),
            (STATUS, AMOUNT),
            1,
        ),
        (
            CASE_RAW,
            grouped(
                metric_names=[AMOUNT],
                group_by_names=[STATUS],
                order_by_names=[STATUS],
                where_constraints=[NON_NULL_STATUS],
                query_type=MetricFlowQueryType.DIMENSION_VALUES,
            ),
            EXPECTED_RAW,
            (STATUS,),
            0,
        ),
        (CASE_FILTER, grouped(metric_names=[AMOUNT], where_constraints=[ONE_CODE]), ((10,),), (AMOUNT,), 0),
        (CASE_TOTAL, grouped(metric_names=[AMOUNT]), ((182,),), (AMOUNT,), 0),
    )
    for name, request, rows, columns, count in cases:
        verify_query(engine, name, request, rows, columns, count)


if __name__ == "__main__":
    main()
