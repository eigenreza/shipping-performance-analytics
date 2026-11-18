{# Generic test: values fall inside an inclusive range (nulls are ignored). #}
{% test accepted_range(model, column_name, min_value=none, max_value=none) %}
select {{ column_name }} as value
from {{ model }}
where {{ column_name }} is not null
  and (
    {% if min_value is not none %}{{ column_name }} < {{ min_value }}{% else %}false{% endif %}
    or {% if max_value is not none %}{{ column_name }} > {{ max_value }}{% else %}false{% endif %}
  )
{% endtest %}

{# Generic test: no date or timestamp after the project's data end date. #}
{% test not_after_data_end(model, column_name) %}
select {{ column_name }} as value
from {{ model }}
where cast({{ column_name }} as date) > date '{{ var("data_end_date") }}'
{% endtest %}

{# Generic test: the table is fresh enough relative to the data end date. #}
{% test max_date_within(model, column_name, days) %}
select max(cast({{ column_name }} as date)) as latest
from {{ model }}
having max(cast({{ column_name }} as date)) < date '{{ var("data_end_date") }}' - interval {{ days }} day
{% endtest %}
