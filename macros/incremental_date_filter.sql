{% macro incremental_date_filter(column_name) %}
    {{ column_name }} between cast('{{ var("data_start") }}' as date)
                         and cast('{{ var("data_end") }}' as date)
    {% if is_incremental() and var('backfill_start', none) is not none %}
        and {{ column_name }} >= cast('{{ var("backfill_start") }}' as date)
    {% elif is_incremental() %}
        and {{ column_name }} >= (
            select coalesce(max({{ column_name }}), date '2020-01-01') from {{ this }}
        )
    {% endif %}
{% endmacro %}
