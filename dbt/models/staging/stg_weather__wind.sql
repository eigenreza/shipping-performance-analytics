select
    cast(cell_lat as double) as cell_lat,
    cast(cell_lon as double) as cell_lon,
    cast(hour_utc as timestamp) as hour_utc,
    cast(wind_speed_10m as double) as wind_speed_ms,
    cast(wind_direction_10m as double) as wind_direction_deg,
    cast(wind_gusts_10m as double) as wind_gust_ms
from {{ source('raw', 'weather_wind') }}
where cast(hour_utc as date) <= date '{{ var("data_end_date") }}'
