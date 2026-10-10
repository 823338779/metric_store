select
    d::date as date_day,
    strftime(d, '%Y%m%d')::integer as date_key,
    year(d) as year_number,
    quarter(d) as quarter_number,
    month(d) as month_number,
    week(d) as iso_week_number,
    isoyear(d) as iso_year_number,
    day(d) as day_of_month,
    isodow(d) as day_of_week,
    isodow(d) in (6, 7) as is_weekend,
    (month(d) = 6 and day(d) = 18) or (month(d) = 11 and day(d) = 11) as is_shopping_festival
from generate_series(date '2020-01-01', date '2027-12-31', interval 1 day) t(d)
