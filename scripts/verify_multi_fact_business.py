"""验收两个事实表分别聚合、多通路分组及聚合后的维值映射。"""

from __future__ import annotations

import argparse
from pathlib import Path

from dbt_metricflow.cli.cli_configuration import CLIConfiguration
from metricflow.engine.metricflow_engine import MetricFlowQueryRequest

from verify_order_business import verify_query

# 一单两笔退款必须只贡献一次订单金额；没有退款的分组保留 NULL。
METRICS = ("metric_a", "metric_b")
CONSUMER = "consumer__dima"
ACCOUNT = "account__dimb"
OWNER = "account__consumer__dima"
EAST, NORTH, SOUTH = "华东", "华北", "华南"
ENTERPRISE, PARTNER = "企业账户", "渠道账户"
PROFILE_OPTION = "--profiles-dir"
RAW_FILTER = "{{ Dimension('consumer__dima') }} = 'EAST'"
OWNER_FILTER = "{{ Dimension('consumer__dima', entity_path=['account']) }} = 'NORTH'"


def main() -> None:
    """真实执行 SQL，并逐行核对跨事实表的共同维度和角色路径。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(PROFILE_OPTION, required=True, type=Path)
    args = parser.parse_args()
    configuration = CLIConfiguration()
    configuration.setup(dbt_profiles_path=args.profiles_dir,
                        dbt_project_path=Path(__file__).resolve().parents[1], configure_file_logging=False)
    engine = configuration.mf
    names = {metric.name for metric in engine.list_metrics(include_dimensions=False)}
    assert set(METRICS) <= names, "缺少来自不同事实表的 metric_a / metric_b"
    dimensions = {dimension.dunder_name: dimension for dimension in engine.list_dimensions(metric_names=list(METRICS))}
    assert {CONSUMER, ACCOUNT, OWNER} <= dimensions.keys(), dimensions.keys()
    assert dimensions[CONSUMER].semantic_model_reference == dimensions[OWNER].semantic_model_reference
    assert dimensions[CONSUMER].entity_links != dimensions[OWNER].entity_links
    assert all(dimensions[path].value_mapping is not None for path in (CONSUMER, ACCOUNT, OWNER))

    # 三个维度均为双指标共同可达维度；SQL 结果同时验证关联不会放大金额。
    request = MetricFlowQueryRequest.create
    cases = (
        ("双事实总额", request(metric_names=list(METRICS)), ((800, 155),), METRICS, 0),
        ("购买人及账户类型", request(metric_names=list(METRICS), group_by_names=[CONSUMER, ACCOUNT],
                              order_by_names=[CONSUMER, ACCOUNT]),
         ((EAST, ENTERPRISE, 100, 50), (EAST, PARTNER, 320, 80),
          (NORTH, ENTERPRISE, 50, None), (SOUTH, ENTERPRISE, 330, 25)), (CONSUMER, ACCOUNT, *METRICS), 2),
        ("客户双路径", request(metric_names=list(METRICS), group_by_names=[CONSUMER, OWNER],
                          order_by_names=[CONSUMER, OWNER]),
         ((EAST, NORTH, 100, 50), (EAST, SOUTH, 320, 80),
          (NORTH, NORTH, 50, None), (SOUTH, NORTH, 330, 25)), (CONSUMER, OWNER, *METRICS), 2),
        ("三维同时映射", request(metric_names=list(METRICS), group_by_names=[CONSUMER, ACCOUNT, OWNER],
                           order_by_names=[CONSUMER, ACCOUNT, OWNER]),
         ((EAST, ENTERPRISE, NORTH, 100, 50), (EAST, PARTNER, SOUTH, 320, 80),
          (NORTH, ENTERPRISE, NORTH, 50, None), (SOUTH, ENTERPRISE, NORTH, 330, 25)),
         (CONSUMER, ACCOUNT, OWNER, *METRICS), 3),
        ("双路径原值筛选", request(metric_names=list(METRICS), where_constraints=[RAW_FILTER, OWNER_FILTER]),
         ((100, 50),), METRICS, 0),
    )
    for name, query, rows, columns, count in cases:
        verify_query(engine, configuration.sql_client, name, query, rows, columns, count)


if __name__ == "__main__":
    main()
