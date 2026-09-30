"""为 StarRocks 生成随机且可关联的电商模拟原表。"""

from __future__ import annotations

import argparse
import math
import os
import random
import secrets
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import mysql.connector

DATABASE = "ecommerce_raw"
STAGE_SUFFIX = "__python_stage"
START_DAY = date(2020, 1, 1)
END_DAY = date(2027, 12, 31)
DAY_COUNT = (END_DAY - START_DAY).days + 1
CENT = Decimal("0.01")
BATCH_SIZE = 500
TABLE_COLUMNS = {
    "users": ("user_id", "registered_at", "region", "membership_tier", "acquisition_channel"),
    "products": ("product_id", "sku", "category", "brand", "list_price", "listed_at"),
    "shops": ("shop_id", "shop_name", "region", "shop_type", "opened_at"),
    "orders": ("order_id", "ordered_at", "user_id", "shop_id", "order_status", "sales_channel", "discount_rate"),
    "order_items": ("order_item_id", "order_id", "product_id", "quantity", "unit_price", "discount_rate"),
    "payments": ("payment_id", "order_id", "paid_at", "paid_amount", "payment_status", "payment_method"),
    "refunds": ("refund_id", "order_id", "refunded_at", "refund_amount", "refund_reason"),
}
REGIONS = ("East", "North", "South", "West", "Central")
TIERS = ("Bronze", "Silver", "Gold")
CHANNELS = ("Organic", "Search", "Social", "Referral")
CATEGORIES = ("Electronics", "Home", "Food", "Fashion", "Beauty")
BRANDS = ("Aurora", "Cedar", "Harbor", "Summit")
SHOP_TYPES = ("Marketplace", "Flagship", "Direct")
SALES_CHANNELS = ("App", "Web", "MiniProgram")
STATUSES = ("PAID", "CANCELLED", "REFUNDED")
DISCOUNTS = tuple(Decimal(value) for value in ("0", "0.05", "0.10", "0.15", "0.20"))
PAYMENT_METHODS = ("Card", "Wallet", "Bank")
REFUND_REASONS = ("CustomerRequest", "OutOfStock", "Damaged", "LateDelivery")
PRICE_CENTERS = {"Electronics": 220, "Home": 75, "Food": 24, "Fashion": 90, "Beauty": 48}
STATUS_PAID = "PAID"
STATUS_CANCELLED = "CANCELLED"
STATUS_REFUNDED = "REFUNDED"
PAYMENT_SETTLED = "SETTLED"


def pick(rng: random.Random, values: tuple, weights: tuple[int, ...]):
    """按业务权重抽取类别，不让状态和渠道机械轮换。"""
    return rng.choices(values, weights=weights, k=1)[0]


def random_id(rng: random.Random, used: set[int]) -> int:
    """为交易流水生成非连续标识，同时保证单表内唯一。"""
    while True:
        value = rng.randrange(100_000_000_000, 1_000_000_000_000)
        if value not in used:
            used.add(value)
            return value


def dated_entities(rng: random.Random, count: int, early: int, early_start: date) -> list[date]:
    """保留初始存量，并让新增实体随机分布到整个订单日期范围。"""
    dates = [early_start + timedelta(days=rng.randrange((START_DAY - early_start).days)) for _ in range(early)]
    dates.extend(START_DAY + timedelta(days=rng.randrange(DAY_COUNT)) for _ in range(count - early))
    return sorted(dates)


def generate(seed: int) -> dict[str, list[tuple]]:
    """先在内存中生成完整业务链，随后统一写入 StarRocks 临时表。"""
    rng = random.Random(seed)
    rows: dict[str, list[tuple]] = {name: [] for name in TABLE_COLUMNS}
    user_dates = dated_entities(rng, rng.randint(4500, 6500), 900, date(2018, 1, 1))
    product_dates = dated_entities(rng, rng.randint(150, 240), 30, date(2019, 1, 1))
    shop_dates = dated_entities(rng, rng.randint(18, 32), 6, date(2018, 1, 1))

    # 维度属性及商品价格各自抽样；ID 顺序与启用日期一致，便于选取当日可用实体。
    for user_id, registered_at in enumerate(user_dates, 1):
        rows["users"].append((user_id, registered_at, rng.choice(REGIONS),
                              pick(rng, TIERS, (58, 30, 12)), pick(rng, CHANNELS, (32, 31, 24, 13))))
    for product_id, listed_at in enumerate(product_dates, 1):
        category = pick(rng, CATEGORIES, (22, 23, 18, 22, 15))
        price = Decimal(f"{min(999.99, max(8.99, rng.lognormvariate(math.log(PRICE_CENTERS[category]), 0.48))):.2f}")
        rows["products"].append((product_id, f"SKU-{product_id:05d}", category,
                                 rng.choice(BRANDS), price, listed_at))
    for shop_id, opened_at in enumerate(shop_dates, 1):
        rows["shops"].append((shop_id, f"Shop {shop_id:03d}", rng.choice(REGIONS),
                              pick(rng, SHOP_TYPES, (68, 14, 18)), opened_at))

    # 每天独立抽取订单量，再按业务状态产生明细、支付和退款流水。
    used_order_ids: set[int] = set()
    used_item_ids: set[int] = set()
    used_payment_ids: set[int] = set()
    used_refund_ids: set[int] = set()
    active_users = active_products = active_shops = 0
    for day_index in range(DAY_COUNT):
        day = START_DAY + timedelta(days=day_index)
        while active_users < len(user_dates) and user_dates[active_users] <= day:
            active_users += 1
        while active_products < len(product_dates) and product_dates[active_products] <= day:
            active_products += 1
        while active_shops < len(shop_dates) and shop_dates[active_shops] <= day:
            active_shops += 1
        base = rng.uniform(18, 33) * (1.24 if day.weekday() >= 5 else 1)
        base *= 1.22 if day.month in (11, 12) else 1
        base *= rng.uniform(1.2, 1.8) if rng.random() < 0.06 else 1
        daily_orders = max(12, min(100, round(rng.gauss(base, 5))))

        for order_index in range(daily_orders):
            order_id = random_id(rng, used_order_ids)
            status = STATUS_PAID if order_index == 0 else pick(rng, STATUSES, (82, 9, 9))
            discount = pick(rng, DISCOUNTS, (66, 12, 11, 7, 4))
            user_id = rng.randrange(1, active_users + 1)
            shop_id = rng.randrange(1, active_shops + 1)
            rows["orders"].append((order_id, day, user_id, shop_id, status,
                                   pick(rng, SALES_CHANNELS, (55, 32, 13)), discount))

            total = Decimal("0")
            item_count = pick(rng, (1, 2, 3, 4), (20, 49, 23, 8))
            for product_index in rng.sample(range(active_products), item_count):
                product_id = product_index + 1
                quantity = pick(rng, (1, 2, 3, 4, 5), (63, 23, 9, 4, 1))
                unit_price = (rows["products"][product_index][4] *
                              Decimal(str(rng.uniform(0.9, 1.1)))).quantize(CENT)
                rows["order_items"].append((random_id(rng, used_item_ids), order_id,
                                            product_id, quantity, unit_price, discount))
                total += (unit_price * quantity * (1 - discount)).quantize(CENT)

            if status != STATUS_CANCELLED:
                payment_id = random_id(rng, used_payment_ids)
                payment_status = STATUS_REFUNDED if status == STATUS_REFUNDED else PAYMENT_SETTLED
                rows["payments"].append((payment_id, order_id, day, total,
                                         payment_status, pick(rng, PAYMENT_METHODS, (43, 39, 18))))
                if status == STATUS_REFUNDED:
                    rows["refunds"].append((random_id(rng, used_refund_ids), order_id, day,
                                            total, pick(rng, REFUND_REASONS, (59, 18, 13, 10))))
    return rows


def load(cursor, rows: dict[str, list[tuple]]) -> None:
    """加载全部临时表，核实行数和关系后再替换七张正式原表。"""
    ddl = Path(__file__).with_name("raw_bootstrap.sql").read_text(encoding="utf-8")
    statements = "\n".join(line for line in ddl.splitlines() if not line.lstrip().startswith("--"))
    for statement in statements.split(";"):
        if statement.strip():
            cursor.execute(statement)

    # 临时表名称固定且只由本脚本使用；加载失败时正式原表保持原状。
    for name, columns in TABLE_COLUMNS.items():
        stage = f"{name}{STAGE_SUFFIX}"
        cursor.execute(f"drop table if exists {DATABASE}.{stage}")
        cursor.execute(f"create table {DATABASE}.{stage} like {DATABASE}.{name}")
        placeholders = ", ".join(("%s",) * len(columns))
        insert_sql = f"insert into {DATABASE}.{stage} ({', '.join(columns)}) values ({placeholders})"
        for offset in range(0, len(rows[name]), BATCH_SIZE):
            cursor.executemany(insert_sql, rows[name][offset:offset + BATCH_SIZE])
        cursor.execute(f"select count(*) from {DATABASE}.{stage}")
        actual = cursor.fetchone()[0]
        if actual != len(rows[name]):
            raise RuntimeError(f"{name}: expected {len(rows[name])} rows, found {actual}")
        print(f"{name}: {actual} rows")

    # 发布前在 StarRocks 中检查日期覆盖及实体生效时间，防止部分加载污染正式表。
    cursor.execute(f"""select count(*), min(ordered_at), max(ordered_at), min(n), min(paid)
        from (select ordered_at, count(*) n, sum(order_status = 'PAID') paid
              from {DATABASE}.orders{STAGE_SUFFIX} group by ordered_at) daily""")
    days, first_day, last_day, minimum_orders, minimum_paid = cursor.fetchone()
    if (days, first_day, last_day) != (DAY_COUNT, START_DAY, END_DAY) or minimum_orders < 12 or minimum_paid < 1:
        raise RuntimeError("daily order coverage failed")
    cursor.execute(f"""select count(*) from {DATABASE}.orders{STAGE_SUFFIX} o
        left join {DATABASE}.users{STAGE_SUFFIX} u on o.user_id = u.user_id and u.registered_at <= o.ordered_at
        left join {DATABASE}.shops{STAGE_SUFFIX} s on o.shop_id = s.shop_id and s.opened_at <= o.ordered_at
        where u.user_id is null or s.shop_id is null""")
    if cursor.fetchone()[0]:
        raise RuntimeError("order entity relationship failed")
    cursor.execute(f"""select count(*) from {DATABASE}.order_items{STAGE_SUFFIX} i
        left join {DATABASE}.orders{STAGE_SUFFIX} o on i.order_id = o.order_id
        left join {DATABASE}.products{STAGE_SUFFIX} p
          on i.product_id = p.product_id and p.listed_at <= o.ordered_at
        where o.order_id is null or p.product_id is null""")
    if cursor.fetchone()[0]:
        raise RuntimeError("product listing relationship failed")
    cursor.execute(f"""select count(*) from {DATABASE}.payments{STAGE_SUFFIX} p
        left join {DATABASE}.orders{STAGE_SUFFIX} o on p.order_id = o.order_id
        where o.order_id is null or o.order_status = 'CANCELLED'
           or (o.order_status = 'REFUNDED' and p.payment_status <> 'REFUNDED')
           or (o.order_status = 'PAID' and p.payment_status <> 'SETTLED')""")
    if cursor.fetchone()[0]:
        raise RuntimeError("payment status relationship failed")
    cursor.execute(f"""select count(*) from {DATABASE}.refunds{STAGE_SUFFIX} r
        left join {DATABASE}.payments{STAGE_SUFFIX} p on r.order_id = p.order_id
        where p.payment_id is null or p.payment_status <> 'REFUNDED'
           or r.refund_amount <> p.paid_amount""")
    if cursor.fetchone()[0]:
        raise RuntimeError("refund relationship failed")

    # 逐表交换；若某次交换失败，逆序恢复已交换的表。
    swapped = []
    try:
        for name in TABLE_COLUMNS:
            cursor.execute(f"alter table {DATABASE}.{name} swap with {name}{STAGE_SUFFIX}")
            swapped.append(name)
    except Exception:
        for name in reversed(swapped):
            cursor.execute(f"alter table {DATABASE}.{name} swap with {name}{STAGE_SUFFIX}")
        raise
    for name in TABLE_COLUMNS:
        cursor.execute(f"drop table {DATABASE}.{name}{STAGE_SUFFIX}")


def main() -> None:
    parser = argparse.ArgumentParser(description="在 StarRocks 中生成随机电商模拟原表")
    parser.add_argument("--seed", type=int, help="复现某次随机数据；省略时每次使用新种子")
    args = parser.parse_args()
    seed = args.seed if args.seed is not None else secrets.randbits(64)
    rows = generate(seed)
    print(f"seed={seed}")
    connection = mysql.connector.connect(
        host=os.getenv("DBT_STARROCKS_HOST", "127.0.0.1"),
        port=int(os.getenv("DBT_STARROCKS_PORT", "9030")),
        user=os.getenv("DBT_STARROCKS_USER", "root"),
        password=os.getenv("DBT_ENV_SECRET_STARROCKS_PASSWORD", ""),
        autocommit=True,
    )
    try:
        cursor = connection.cursor()
        try:
            load(cursor, rows)
        finally:
            cursor.close()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
