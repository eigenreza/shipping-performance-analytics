{# Read raw Parquet files from the configured raw folder. #}
{% macro raw_parquet(relative_glob) -%}
    read_parquet('{{ var("raw_path") }}/{{ relative_glob }}', union_by_name = true)
{%- endmacro %}
