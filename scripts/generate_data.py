"""Generate deterministic synthetic CNY ecommerce data, replacing only requested days."""
import argparse
import datetime as dt
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DAILY_TABLES = {
    'orders': 'order_date', 'order_items': 'order_date',
}


def generate(database: Path, start: dt.date, end: dt.date) -> None:
    if not dt.date(2020, 1, 1) <= start <= end <= dt.date(2027, 12, 31):
        raise ValueError('Date range must be within 2020-01-01..2027-12-31, start <= end')
    database.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database)) as con:
        con.execute('begin transaction')
        con.execute("create schema if not exists raw")
        con.execute("create temp table days as select d::date as dt, datediff('day', date '2020-01-01', d)::bigint as day_index from generate_series(?::date, ?::date, interval 1 day) t(d)", [start, end])
        con.execute((ROOT / 'scripts/sql/reference_data.sql').read_text(encoding='utf-8'))
        con.execute((ROOT / 'scripts/sql/daily_data.sql').read_text(encoding='utf-8'))
        for table, date_col in DAILY_TABLES.items():
            con.execute(f'create table if not exists raw.{table} as select * from incoming_{table} limit 0')
            con.execute(f'delete from raw.{table} where {date_col} between ? and ?', [start, end])
            con.execute(f'insert into raw.{table} select * from incoming_{table}')
        con.execute('commit')
        for table in DAILY_TABLES:
            print(f'raw.{table}: {con.sql(f"select count(*) from raw.{table}").fetchone()[0]:,}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT / 'data/ecommerce.duckdb')
    parser.add_argument('--start-date', type=dt.date.fromisoformat, default=dt.date(2020, 1, 1))
    parser.add_argument('--end-date', type=dt.date.fromisoformat, default=dt.date(2027, 12, 31))
    args = parser.parse_args()
    generate(args.database, args.start_date, args.end_date)
