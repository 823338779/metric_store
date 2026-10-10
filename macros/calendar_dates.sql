{% macro calendar_dates(start_date, end_date) %}
    {% if target.type == 'databricks' %}
        select explode(sequence(cast('{{ start_date }}' as date),
                                cast('{{ end_date }}' as date), interval 1 day)) as d
    {% else %}
        select cast(d as date) as d
        from generate_series(cast('{{ start_date }}' as date),
                             cast('{{ end_date }}' as date), interval 1 day) t(d)
    {% endif %}
{% endmacro %}
