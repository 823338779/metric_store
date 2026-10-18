"""通过 dbt-service 的公开 HTTP API 验收固定构建、发布指针和订单查询。"""

from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# 固定本示例资源及维度展示身份；optionId 始终从当前构建实时发现。
AMOUNT = "order_demo_order_amount"
PAID = "order_demo_paid_amount"
ORDERS = "order_demo_paid_order_count"
BUYERS = "order_demo_paid_buyer_count"
AVERAGE = "order_demo_average_order_value"
BUYER = "region_code（order_demo_customer）"
OWNER = "region_code（order_demo_account → order_demo_customer）"
STATUS = "status_code（order_demo_order）"
CHANNEL = "channel_code（order_demo_order）"
ORDER_MODEL = "order_demo_orders"
TOKEN_ENV = "SERVICE_TOKEN"
UTF8 = "utf-8"
SERVICE_OPTION, BUILD_OPTION = "--service-url", "--build-id"
QUERY, EXPLAIN, PREVIEW, VALUES = "QUERY", "EXPLAIN", "PREVIEW", "DIMENSION_VALUES"
METRIC_KIND, TABLE_KIND = "METRIC", "TABLE"
PASS_MESSAGE = "PASS: {} -> {}"
EAST, NORTH, SOUTH = "华东", "华北", "华南"
PAID_LABEL, COMPLETED, CLOSED = "已支付", "已完成", "已关闭"
WEB, APP, UNKNOWN_CHANNEL = "网页", "应用", "99"
DECIMAL_TYPE = "Decimal"
CROSS_METRICS = ("metric_a", "metric_b")
CONSUMER_OPTION = "dima（consumer）"
ACCOUNT_OPTION = "dimb（account）"
OWNER_OPTION = "dima（account → consumer）"
CONSUMER_COLUMN = "consumer__dima"
ACCOUNT_COLUMN = "account__dimb"
OWNER_COLUMN = "account__consumer__dima"
ENTERPRISE, PARTNER = "企业账户", "渠道账户"


def main() -> None:
    """凭据只从环境读取，所有断言使用真实 HTTP 返回的列和值。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(SERVICE_OPTION, default="http://127.0.0.1:8000")
    parser.add_argument(BUILD_OPTION, required=True)
    args = parser.parse_args()
    headers = {"Authorization": f"Bearer {os.environ[TOKEN_ENV]}", "Content-Type": "application/json"}

    def call(path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode(UTF8)
        with urlopen(Request(args.service_url.rstrip("/") + path, data=payload, headers=headers), timeout=1860) as response:
            return json.load(response, parse_float=Decimal)

    # 构建和发布分别核对，不能把构建成功当成已发布。
    build_path = f"/builds/{args.build_id}"
    build = call(build_path)
    assert build["buildStatus"] == "SUCCEEDED" and build["queryAvailable"], build
    key = urlencode({"repository": build["repository"], "environmentId": build["execution"]["environmentId"],
                     "branchName": build["branchName"]})
    deployment = call(f"/deployments/current?{key}")
    assert deployment["activeBuildId"] == args.build_id, deployment
    assert deployment["activeCommitSha"] == build["commitSha"], deployment
    print(PASS_MESSAGE.format("发布指针与固定源码一致", args.build_id))

    # 目录严格包含五个原订单指标和两个跨事实表指标，不允许旧电商业务残留。
    catalog = call(build_path + "/catalog?limit=200")
    assert catalog["nextCursor"] is None, "示例目录不应超过一页"
    metrics = {item["name"]: item["resourceId"] for item in catalog["items"] if item["kind"] == METRIC_KIND}
    assert set(metrics) == {AMOUNT, PAID, ORDERS, BUYERS, AVERAGE, *CROSS_METRICS}, metrics
    metric_ids = [metrics[name] for name in (AMOUNT, PAID, ORDERS, BUYERS, AVERAGE)]
    suffix = "?" + urlencode({"build_id": args.build_id})
    available = call("/query/available-dimensions" + suffix, {"metricResourceIds": metric_ids})
    options = {item["displayName"]: item for item in available["dimensions"]}
    assert {BUYER, OWNER, STATUS, CHANNEL} <= options.keys(), options
    assert options[BUYER]["optionId"] != options[OWNER]["optionId"]
    assert options[BUYER]["resourceId"] == options[OWNER]["resourceId"] is not None

    def query(groups: tuple[str, ...] = (), **extra: Any) -> dict[str, Any]:
        return call("/query" + suffix, {
            "mode": QUERY, "metricResourceIds": metric_ids,
            "groupBy": [{"optionId": options[name]["optionId"]} for name in groups], **extra,
        })

    def check(name: str, result: dict[str, Any], columns: tuple[str, ...], expected: list[tuple[Any, ...]]) -> None:
        names = [column["name"] for column in result["columns"]]
        indexes = [names.index(column) for column in columns]
        # 服务将 Decimal 编码为 JSON 字符串；只按列类型还原数值，保留渠道文本 99。
        rows = [tuple(Decimal(row[index]) if row[index] is not None
                      and result["columns"][index]["type"] == DECIMAL_TYPE else row[index]
                      for index in indexes) for row in result["rows"]]
        # 无排序查询以完整行排序比较，绝不按显示名称转成会丢失重复分组的字典。
        assert sorted(rows) == sorted(expected), (name, rows, expected)
        assert result["buildId"] == args.build_id and result["commitSha"] == build["commitSha"]
        print(PASS_MESSAGE.format(name, rows))

    buyer_column = "order_demo_customer__region_code"
    owner_column = "order_demo_account__order_demo_customer__region_code"
    status_column = "order_demo_order__status_code"
    channel_column = "order_demo_order__channel_code"
    check("五项指标", query(), (AMOUNT, PAID, ORDERS, BUYERS, AVERAGE), [(800, 500, 4, 3, 125)])
    check("采购人地区", query((BUYER,)), (buyer_column, PAID), [(EAST, 300), (NORTH, 50), (SOUTH, 150)])
    check("负责人地区", query((OWNER,)), (owner_column, PAID), [(NORTH, 300), (SOUTH, 200)])
    check("双路径交叉", query((BUYER, OWNER)), (buyer_column, owner_column, PAID),
          [(EAST, NORTH, 100), (EAST, SOUTH, 200), (NORTH, NORTH, 50), (SOUTH, NORTH, 150)])
    check("四维映射", query((BUYER, OWNER, STATUS, CHANNEL)),
          (buyer_column, owner_column, status_column, channel_column, AMOUNT),
          [(EAST, NORTH, PAID_LABEL, WEB, 100), (NORTH, NORTH, PAID_LABEL, WEB, 50),
           (EAST, SOUTH, COMPLETED, APP, 200), (SOUTH, NORTH, COMPLETED, APP, 150),
           (EAST, SOUTH, CLOSED, WEB, 120), (SOUTH, NORTH, CLOSED, UNKNOWN_CHANNEL, 180)])
    check("同名状态不合并", query((STATUS,)), (status_column, AMOUNT),
          [(PAID_LABEL, 150), (COMPLETED, 350), (CLOSED, 120), (CLOSED, 180)])
    check("原始代码筛选", query((STATUS,), filters=[{"optionId": options[STATUS]["optionId"], "operator": "=", "value": 40}]),
          (status_column, AMOUNT), [(CLOSED, 120)])
    check("无已支付订单时客单价为空", query(filters=[{"optionId": options[STATUS]["optionId"], "operator": "=", "value": 40}]),
          (PAID, ORDERS, BUYERS, AVERAGE), [(0, 0, 0, None)])
    check("排序与 LIMIT", query((STATUS,), orderBy=[{"fieldId": options[STATUS]["optionId"], "direction": "ASC"}], limit=3),
          (status_column, AMOUNT), [(PAID_LABEL, 150), (COMPLETED, 350), (CLOSED, 120)])

    # 其余三种公开模式也使用相同固定构建，原值查询必须保留数字代码。
    raw = query(mode=VALUES, dimensionOptionId=options[STATUS]["optionId"])
    check("原始维值", raw, (status_column,), [(20,), (30,), (40,), (41,)])
    explained = query((BUYER, OWNER, STATUS, CHANNEL), mode=EXPLAIN)
    assert explained["sql"] and all(model in explained["sql"] for model in
                                    ("order_demo_regions", "order_demo_statuses", "order_demo_channels"))
    dataset = next(item["resourceId"] for item in catalog["items"]
                   if item["kind"] == TABLE_KIND and item["name"] == ORDER_MODEL and PREVIEW in item["capabilities"])
    preview = call("/query" + suffix, {"mode": PREVIEW, "datasetResourceId": dataset, "limit": 10})
    check("订单预览", preview, ("order_id", "amount"), [(1001, 100), (1002, 200), (1003, 50), (1004, 150), (1005, 120), (1006, 180)])
    print(PASS_MESSAGE.format("EXPLAIN", "包含地区、状态、渠道的映射 SQL"))

    # 共同维度必须以双指标集合重新发现；同一资源的不同角色路径有不同 optionId。
    cross_ids = [metrics[name] for name in CROSS_METRICS]
    cross_available = call("/query/available-dimensions" + suffix, {"metricResourceIds": cross_ids})
    cross_options = {item["displayName"]: item for item in cross_available["dimensions"]}
    assert {CONSUMER_OPTION, ACCOUNT_OPTION, OWNER_OPTION} <= cross_options.keys(), cross_options
    assert cross_options[CONSUMER_OPTION]["optionId"] != cross_options[OWNER_OPTION]["optionId"]
    assert cross_options[CONSUMER_OPTION]["resourceId"] == cross_options[OWNER_OPTION]["resourceId"] is not None

    def cross_query(groups: tuple[str, ...] = (), **extra: Any) -> dict[str, Any]:
        return call("/query" + suffix, {
            "mode": QUERY, "metricResourceIds": cross_ids,
            "groupBy": [{"optionId": cross_options[name]["optionId"]} for name in groups], **extra,
        })

    check("跨事实表总额", cross_query(), CROSS_METRICS, [(800, 155)])
    check("跨事实表购买人及账户类型", cross_query((CONSUMER_OPTION, ACCOUNT_OPTION)),
          (CONSUMER_COLUMN, ACCOUNT_COLUMN, *CROSS_METRICS),
          [(EAST, ENTERPRISE, 100, 50), (EAST, PARTNER, 320, 80),
           (NORTH, ENTERPRISE, 50, None), (SOUTH, ENTERPRISE, 330, 25)])
    check("跨事实表客户双路径", cross_query((CONSUMER_OPTION, OWNER_OPTION)),
          (CONSUMER_COLUMN, OWNER_COLUMN, *CROSS_METRICS),
          [(EAST, NORTH, 100, 50), (EAST, SOUTH, 320, 80), (NORTH, NORTH, 50, None), (SOUTH, NORTH, 330, 25)])
    check("跨事实表三维映射", cross_query((CONSUMER_OPTION, ACCOUNT_OPTION, OWNER_OPTION)),
          (CONSUMER_COLUMN, ACCOUNT_COLUMN, OWNER_COLUMN, *CROSS_METRICS),
          [(EAST, ENTERPRISE, NORTH, 100, 50), (EAST, PARTNER, SOUTH, 320, 80),
           (NORTH, ENTERPRISE, NORTH, 50, None), (SOUTH, ENTERPRISE, NORTH, 330, 25)])
    check("跨事实表双路径原码筛选", cross_query(filters=[
        {"optionId": cross_options[CONSUMER_OPTION]["optionId"], "operator": "=", "value": "EAST"},
        {"optionId": cross_options[OWNER_OPTION]["optionId"], "operator": "=", "value": "NORTH"},
    ]), CROSS_METRICS, [(100, 50)])
    check("跨事实表维值保留原码", cross_query(mode=VALUES, dimensionOptionId=cross_options[CONSUMER_OPTION]["optionId"]),
          (CONSUMER_COLUMN,), [("EAST",), ("NORTH",), ("SOUTH",)])
    cross_explained = cross_query((CONSUMER_OPTION, ACCOUNT_OPTION, OWNER_OPTION), mode=EXPLAIN)
    assert all(model in cross_explained["sql"] for model in
               ("multi_fact_orders", "multi_fact_refunds", "order_demo_regions", "multi_fact_account_types"))
    print(PASS_MESSAGE.format("跨事实表 EXPLAIN", "两张事实表及两份显示字典均参与查询"))


if __name__ == "__main__":
    main()
