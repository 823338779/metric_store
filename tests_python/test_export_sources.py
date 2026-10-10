import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


class ExportTests(unittest.TestCase):
    def test_parquet_preserves_all_five_tables_types_and_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / 'source.duckdb'
            output = Path(tmp) / "export's data"
            subprocess.run([sys.executable, str(ROOT / 'scripts/generate_data.py'),
                            '--database', str(database), '--start-date', '2020-02-28',
                            '--end-date', '2020-03-01'], check=True, capture_output=True)
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/export_sources.py'),
                                     '--database', str(database), '--output', str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            names = {'users', 'shops', 'products', 'orders', 'order_items'}
            self.assertEqual({p.stem for p in output.glob('*.parquet')}, names)
            with duckdb.connect(str(database), read_only=True) as con:
                for name in names:
                    imported = con.read_parquet(str(output / f'{name}.parquet'))
                    original = con.table(f'raw.{name}')
                    self.assertEqual(imported.columns, original.columns)
                    self.assertEqual(imported.types, original.types)
                    expected = con.sql(f'select count(*), bit_xor(hash(t)) from raw.{name} t').fetchone()
                    actual = imported.query('t', 'select count(*), bit_xor(hash(t)) from t').fetchone()
                    self.assertEqual(actual, expected, name)


if __name__ == '__main__':
    unittest.main()
