import datetime as dt
import unittest
from pathlib import Path
from types import SimpleNamespace

import duckdb
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]


def render_calendar(adapter):
    macro = ROOT / 'macros/calendar_dates.sql'
    env = Environment(undefined=StrictUndefined)
    env.globals['target'] = SimpleNamespace(type=adapter)
    env.globals.update(env.from_string(macro.read_text(encoding='utf-8')).module.__dict__)
    return env.from_string((ROOT / 'models/dimensions/dim_date.sql').read_text(encoding='utf-8')).render()


class CalendarTests(unittest.TestCase):
    def test_complete_calendar_and_iso_year_boundaries(self):
        self.assertTrue((ROOT / 'macros/calendar_dates.sql').exists(), 'Shared adapter-aware date sequence is missing')
        with duckdb.connect() as con:
            con.execute('create table calendar as ' + render_calendar('duckdb'))
            self.assertEqual(con.sql('select count(*),count(distinct date_day) from calendar').fetchone(), (2922, 2922))
            self.assertEqual(con.sql("select count(*) from calendar where date_day in (date '2020-02-29', date '2024-02-29')").fetchone()[0], 2)
            self.assertEqual(con.sql("select date_key,iso_year_number,iso_week_number,day_of_week,is_weekend from calendar where date_day=date '2021-01-01'").fetchone(), (20210101, 2020, 53, 5, False))
            self.assertEqual(con.sql("select iso_year_number,iso_week_number,day_of_week from calendar where date_day=date '2024-12-30'").fetchone(), (2025, 1, 1))
            self.assertEqual(con.sql('select min(date_day),max(date_day) from calendar').fetchone(), (dt.date(2020, 1, 1), dt.date(2027, 12, 31)))


if __name__ == '__main__':
    unittest.main()
