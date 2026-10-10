"""Validate full eight-year coverage and write the measured data profile."""
import argparse
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def validate(database: Path) -> dict:
    with duckdb.connect(str(database), read_only=True) as con:
        names = {row[0] for row in con.sql("select table_name from information_schema.tables where table_schema='raw'").fetchall()}
        expected = {'users', 'shops', 'products', 'orders', 'order_items'}
        if names != expected:
            raise ValueError(f'Expected exactly five core tables; got {sorted(names)}')
        counts = {name: con.sql(f'select count(*) from raw.{name}').fetchone()[0] for name in sorted(names)}
        coverage = {}
        for name, column in [('orders', 'order_date'), ('order_items', 'order_date'), ('users', 'registered_date')]:
            first, last, days, minimum, maximum = con.sql(f'''
                select min(d), max(d), count(*), min(n), max(n)
                from (select {column} as d, count(*) as n from raw.{name} group by 1)
            ''').fetchone()
            if (str(first), str(last), days) != ('2020-01-01', '2027-12-31', 2922):
                raise ValueError(f'{name} has incomplete date coverage')
            if name == 'orders' and not (100 <= minimum <= maximum <= 300):
                raise ValueError('Daily order volume outside 100..300')
            coverage[name] = {'start': str(first), 'end': str(last), 'days': days,
                              'min_rows_per_day': minimum, 'max_rows_per_day': maximum}
        years = con.sql('''
            select year(order_date) as year, count(*) as order_count,
                   sum(paid_amount) as paid_amount, sum(refund_amount) as refund_amount,
                   sum(paid_amount - refund_amount) as net_revenue
            from raw.orders group by 1 order by 1
        ''')
        yearly = [dict(zip([c[0] for c in years.description], row)) for row in years.fetchall()]
        return {'synthetic': True, 'currency': 'CNY', 'raw_tables': counts,
                'total_raw_rows': sum(counts.values()), 'daily_coverage': coverage, 'yearly_sales': yearly}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT / 'data/ecommerce.duckdb')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/data-profile.json')
    args = parser.parse_args()
    result = validate(args.database)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True, indent=2, default=str))
