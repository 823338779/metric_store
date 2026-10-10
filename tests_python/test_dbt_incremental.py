"""Exercise real dbt append, replay and historical correction against DuckDB."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DBT = Path(sys.executable).parent / ('dbt.exe' if os.name == 'nt' else 'dbt')


class IncrementalTests(unittest.TestCase):
    def command(self, args, env=None):
        result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 0, result.stdout[-18000:] + result.stderr)

    def snapshot(self, path):
        with duckdb.connect(str(path)) as con:
            # Adapter-internal full-refresh backup tables are not dbt models.
            tables = con.sql("select table_schema, table_name from information_schema.tables where table_schema in ('analytics_facts','analytics_marts') and not ends_with(table_name, '__dbt_backup') order by 1,2").fetchall()
            self.assertEqual(len(tables), 6, tables)
            return {f'{schema}.{table}': con.sql(f'select count(*), bit_xor(hash(t)) from {schema}.{table} t').fetchone()
                    for schema, table in tables}

    def test_append_replay_backfill_equals_full_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'incremental.duckdb'
            env = dict(os.environ, ECOMMERCE_DB_PATH=str(path), PYTHONIOENCODING='utf-8', DBT_SEND_ANONYMOUS_USAGE_STATS='false')

            def generate(start, end):
                self.command([sys.executable, 'scripts/generate_data.py', '--database', str(path), '--start-date', start, '--end-date', end], env)

            def build(end, backfill=None, full=False):
                variables = {'data_end': end}
                if backfill:
                    variables['backfill_start'] = backfill
                args = [str(DBT), 'build', '--profiles-dir', '.', '--target-path', str(Path(tmp) / 'target'), '--log-path', str(Path(tmp) / 'logs'), '--vars', json.dumps(variables)]
                if full:
                    args.append('--full-refresh')
                self.command(args, env)

            generate('2020-01-01', '2020-01-02')
            build('2020-01-02', backfill='2020-01-02')
            initial_count = self.snapshot(path)['analytics_facts.fct_orders'][0]
            generate('2020-01-03', '2020-01-03')
            build('2020-01-03')
            appended = self.snapshot(path)
            self.assertGreater(appended['analytics_facts.fct_orders'][0], initial_count)
            generate('2020-01-03', '2020-01-03')
            build('2020-01-03')
            self.assertEqual(appended, self.snapshot(path))

            with duckdb.connect(str(path)) as con:
                order_id = con.sql("select min(order_id) from raw.orders where order_date = date '2020-01-01' and order_status = 'completed'").fetchone()[0]
                con.execute("update raw.orders set order_status='partially_refunded', refund_amount=round(paid_amount * 0.25, 2), refunded_at=order_date::timestamp + interval 18 hour where order_id=?", [order_id])
            build('2020-01-03', backfill='2020-01-01')
            corrected = self.snapshot(path)
            self.assertNotEqual(appended['analytics_facts.fct_orders'], corrected['analytics_facts.fct_orders'])
            self.assertNotEqual(appended['analytics_marts.mart_daily_sales'], corrected['analytics_marts.mart_daily_sales'])
            build('2020-01-03', backfill='2020-01-02', full=True)
            self.assertEqual(corrected, self.snapshot(path))


if __name__ == '__main__':
    unittest.main()
