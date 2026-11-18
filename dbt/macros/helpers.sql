{# Great-circle distance in nautical miles between two points given in degrees. #}
{% macro haversine_nm(lat1, lon1, lat2, lon2) -%}
    (2 * 3440.065 * asin(sqrt(
        pow(sin(radians(({{ lat2 }}) - ({{ lat1 }})) / 2), 2)
        + cos(radians({{ lat1 }})) * cos(radians({{ lat2 }}))
        * pow(sin(radians(({{ lon2 }}) - ({{ lon1 }})) / 2), 2)
    )))
{%- endmacro %}

{# Division that returns null instead of failing or returning infinity. #}
{% macro safe_divide(numerator, denominator) -%}
    case when ({{ denominator }}) is null or ({{ denominator }}) = 0 then null
         else ({{ numerator }}) / ({{ denominator }}) end
{%- endmacro %}

{# Stable pseudonymous key for a ship identifier. #}
{% macro ship_hash(imo_expr) -%}
    md5('{{ var("pseudonym_salt") }}' || cast({{ imo_expr }} as varchar))
{%- endmacro %}
