select
    d::date as date_day,
    cast(year(d) * 10000 + month(d) * 100 + day(d) as integer) as date_key,
    year(d) as year_number,
    quarter(d) as quarter_number,
    month(d) as month_number,
    {% if target.type == 'databricks' %}
    weekofyear(d) as iso_week_number,
    year(date_add(d, 3 - weekday(d))) as iso_year_number,
    {% else %}
    week(d) as iso_week_number,
    isoyear(d) as iso_year_number,
    {% endif %}
    day(d) as day_of_month,
    {% if target.type == 'databricks' %}
    weekday(d) + 1 as day_of_week,
    weekday(d) in (5, 6) as is_weekend,
    {% else %}
    isodow(d) as day_of_week,
    isodow(d) in (6, 7) as is_weekend,
    {% endif %}
    (month(d) = 6 and day(d) = 18) or (month(d) = 11 and day(d) = 11) as is_shopping_festival
from ({{ calendar_dates('2020-01-01', '2027-12-31') }}) dates
