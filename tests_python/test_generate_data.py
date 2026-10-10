import datetime as dt
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


class GeneratorTests(unittest.TestCase):
    def generate(self, path, start, end):
        result = subprocess.run(
            [sys.executable, str(ROOT / 'scripts/generate_data.py'),
             '--database', str(path), '--start-date', start, '--end-date', end],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def fingerprint(self, path):
        with duckdb.connect(str(path)) as con:
            tables = con.sql("select table_name from information_schema.tables where table_schema='raw' order by 1").fetchall()
            return {name: con.sql(f'select count(*), bit_xor(hash(t)) from raw.{name} t').fetchone()
                    for (name,) in tables}

    def test_daily_coverage_leap_day_relations_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.duckdb'
            self.generate(path, '2020-02-28', '2020-03-01')
            before = self.fingerprint(path)
            with duckdb.connect(str(path)) as con:
                self.assertEqual(set(before), {'users', 'shops', 'products', 'orders', 'order_items'})
                for table, date_col in [('orders', 'order_date'), ('order_items', 'order_date')]:
                    dates = con.sql(f'select distinct {date_col} from raw.{table} order by 1').fetchall()
                    self.assertEqual(dates, [(dt.date(2020, 2, 28),), (dt.date(2020, 2, 29),), (dt.date(2020, 3, 1),)])
                counts = con.sql('select count(*) from raw.orders group by order_date').fetchall()
                self.assertTrue(all(100 <= n <= 300 for (n,) in counts))
                self.assertEqual(con.sql('select count(*) from raw.orders where refund_amount > paid_amount or paid_amount < 0 or refund_amount < 0').fetchone()[0], 0)
                self.assertEqual(con.sql('select count(*) from raw.orders o left join raw.users u using(user_id) where u.user_id is null or u.registered_date > o.order_date').fetchone()[0], 0)
                self.assertEqual(con.sql('select count(*) from raw.order_items i join raw.orders o using(order_id) join raw.products p using(product_id) where o.shop_id <> p.shop_id').fetchone()[0], 0)
                self.assertEqual(con.sql('select count(*) from raw.orders o join (select order_id,sum(net_amount) amount from raw.order_items group by 1) i using(order_id) where o.order_amount <> i.amount').fetchone()[0], 0)
            self.generate(path, '2020-02-28', '2020-03-01')
            self.assertEqual(before, self.fingerprint(path))

    def test_partitioned_generation_equals_one_shot(self):
        with tempfile.TemporaryDirectory() as tmp:
            full, chunked = Path(tmp) / 'full.duckdb', Path(tmp) / 'chunked.duckdb'
            self.generate(full, '2027-12-29', '2027-12-31')
            self.generate(chunked, '2027-12-29', '2027-12-30')
            self.generate(chunked, '2027-12-31', '2027-12-31')
            self.assertEqual(self.fingerprint(full), self.fingerprint(chunked))

    def test_invalid_range_rejected_before_database_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            for start, end in [('2020-03-01', '2020-02-01'), ('2019-12-31', '2020-01-01'), ('2027-12-31', '2028-01-01')]:
                path = Path(tmp) / 'invalid.duckdb'
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/generate_data.py'), '--database', str(path), '--start-date', start, '--end-date', end], capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
