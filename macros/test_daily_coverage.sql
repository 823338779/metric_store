{% test daily_coverage(model, column_name) %}
with expected as (
    select d as business_date
    from ({{ calendar_dates(var('data_start'), var('data_end')) }}) dates
), actual as (
    select distinct {{ column_name }} as business_date from {{ model }}
)
select expected.business_date from expected
left join actual using (business_date)
where actual.business_date is null
{% endtest %}
