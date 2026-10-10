{% test daily_coverage(model, column_name) %}
with expected as (
    select d::date as business_date
    from generate_series(cast('{{ var("data_start") }}' as date),
                         cast('{{ var("data_end") }}' as date), interval 1 day) t(d)
), actual as (
    select distinct {{ column_name }} as business_date from {{ model }}
)
select expected.business_date from expected
left join actual using (business_date)
where actual.business_date is null
{% endtest %}
