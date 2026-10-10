"""Export the five raw tables to typed Parquet files for Databricks ingestion."""
import argparse
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('users', 'shops', 'products', 'orders', 'order_items')


def export(database: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with duckdb.connect(str(database), read_only=True) as con:
        for name in TABLES:
            path = output / f'{name}.parquet'
            sql_path = str(path.resolve()).replace("'", "''")
            con.execute(f"copy raw.{name} to '{sql_path}' (format parquet, compression snappy)")
            manifest[name] = {'file': path.name, 'rows': con.sql(f'select count(*) from raw.{name}').fetchone()[0],
                              'bytes': path.stat().st_size}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT / 'data/ecommerce.duckdb')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/databricks-import')
    args = parser.parse_args()
    print(json.dumps(export(args.database, args.output), indent=2))
