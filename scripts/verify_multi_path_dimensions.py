"""验证同一指标到同一地区维度的两条路径及其真实聚合结果。"""

from __future__ import annotations

import argparse
from pathlib import Path

from dbt_metricflow.cli.cli_configuration import CLIConfiguration
from metricflow.engine.metricflow_engine import MetricFlowQueryRequest

METRIC_NAME = "demo_purchase_amount"
DIMENSION_NAME = "region"
CUSTOMER_MODEL = "demo_customers"
BUYER_PATH = "demo_customer__region"
OWNER_PATH = "demo_account__demo_customer__region"
EXPECTED_BY_PATH = {
    BUYER_PATH: {("EAST",): 300, ("NORTH",): 50, ("SOUTH",): 150},
    OWNER_PATH: {("NORTH",): 300, ("SOUTH",): 200},
}
EXPECTED_BY_BOTH = {
    ("EAST", "NORTH"): 100,
    ("EAST", "SOUTH"): 200,
    ("NORTH", "NORTH"): 50,
    ("SOUTH", "NORTH"): 150,
}


def main() -> None:
    """读取本项目构建产物，使用 DuckDB profile 验证路径发现和查询。"""
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

    # 先检查指标存在，再确认两条路径指向同一模型中的同一维度。
    metric_names = {metric.name for metric in engine.list_metrics(include_dimensions=False)}
    assert METRIC_NAME in metric_names, f"Missing demo metric: {METRIC_NAME}"
    dimensions = {
        dimension.dunder_name: dimension
        for dimension in engine.list_dimensions(metric_names=[METRIC_NAME])
        if dimension.name == DIMENSION_NAME
    }
    for path in EXPECTED_BY_PATH:
        assert path in dimensions, (path, sorted(dimensions))
        dimension = dimensions[path]
        assert dimension.semantic_model_reference.semantic_model_name == CUSTOMER_MODEL
        assert [entity.element_name for entity in dimension.entity_links] == path.split("__")[:-1]
        print(f"PATH: {path} -> {CUSTOMER_MODEL}.{DIMENSION_NAME}")

    # 核对不同业务角色的分组结果；同一地区终点不意味着相同统计口径。
    cases = [([path], expected) for path, expected in EXPECTED_BY_PATH.items()]
    cases.append(([BUYER_PATH, OWNER_PATH], EXPECTED_BY_BOTH))
    for paths, expected in cases:
        result = engine.query(MetricFlowQueryRequest.create(metric_names=[METRIC_NAME], group_by_names=paths))
        assert result.result_df is not None
        table = result.result_df
        columns = [column.column_name for column in table.column_descriptions]
        dimension_indexes = [columns.index(path) for path in paths]
        metric_index = columns.index(METRIC_NAME)
        actual = {tuple(row[index] for index in dimension_indexes): row[metric_index] for row in table.rows}
        assert len(table.rows) == len(expected), (paths, table.rows)
        assert actual == expected, (paths, actual, expected)
        print(f"PASS: {paths} -> {actual}")


if __name__ == "__main__":
    main()
