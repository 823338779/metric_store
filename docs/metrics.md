# 电商指标字典

定义采用 dbt Core 1.12 / dbt v2 的新版 YAML：`models/schema.yml` 包含 5 个内嵌语义模型及 17 个简单指标，`models/semantic/metrics.yml` 包含 7 个比率指标。实体和维度定义在模型列上，原 measure 的聚合表达式直接写入简单指标；指标名称和业务口径保持不变。解析产物为 `target/semantic_manifest.json` 和 `target/osi_document.json`。DuckDB 本地汇总查询及 dbt 平台指标部署步骤见 README。

所有金额为 CNY。下单金额含取消单，支付金额是退款前实收，净收入为支付减退款。毛利扣除已履约商品成本，退款不冲回成本；不含物流、税费、营销费。商品指标为退款前金额，不将订单退款分摊到商品，避免产生未定义口径。

| 指标名 | 含义 | 聚合口径 |
| --- | --- | --- |
| total_orders | 下单数 | sum(order_count) |
| paid_orders | 支付订单数 | sum(paid_order_count) |
| cancelled_orders | 取消订单数 | sum(cancelled_order_count) |
| refunded_orders | 退款订单数 | sum(refunded_order_count) |
| gross_order_value | 下单原价金额，含取消 | sum(gross_amount) |
| ordered_amount | 下单折后金额，含取消 | sum(order_amount) |
| order_discounts | 下单优惠金额，含取消 | sum(discount_amount) |
| paid_revenue | 支付金额，退款前 | sum(paid_amount) |
| refund_amount | 退款金额 | sum(refund_amount) |
| net_revenue | 支付减退款 | sum(net_revenue) |
| fulfilled_cost | 已履约商品成本，退款不冲回 | sum(fulfilled_cost) |
| gross_profit | 净收入减履约商品成本 | sum(gross_profit) |
| paying_users | 去重支付用户数 | count_distinct(case when paid_order_count = 1 then user_id end) |
| ordered_units | 下单件数，含取消 | sum(quantity) |
| paid_units | 已支付件数，退货前 | sum(paid_quantity) |
| paid_item_revenue | 商品支付金额，退款前 | sum(paid_item_amount) |
| new_users | 新增用户数 | sum(1)，按注册日 |
| average_order_value | 支付客单价 | paid_revenue / paid_orders |
| cancellation_rate | 取消率 | cancelled_orders / total_orders |
| refund_order_rate | 支付订单退款率 | refunded_orders / paid_orders |
| refund_amount_rate | 支付金额退款率 | refund_amount / paid_revenue |
| gross_margin_rate | 毛利率 | gross_profit / net_revenue |
| revenue_per_paying_user | 支付用户人均净收入 | net_revenue / paying_users |
| units_per_paid_order | 每支付订单件数 | paid_units / paid_orders |

比率使用聚合分子 / 聚合分母，不对每日比率求平均。去重支付用户数不可将每日去重人数相加。订单指标按下单日期统计；新增用户按注册日期统计。所有表为合成数据，不代表预测。
