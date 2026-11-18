select
    cast(cell_lat as double) as cell_lat,
    cast(cell_lon as double) as cell_lon,
    cast(hour_utc as timestamp) as hour_utc,
    cast(wave_height as double) as wave_height_m,
    cast(wave_direction as double) as wave_direction_deg,
    cast(wave_period as double) as wave_period_s
from {{ source('raw', 'weather_waves') }}
where cast(hour_utc as date) <= date '{{ var("data_end_date") }}'
