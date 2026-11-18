-- Positions under way (3 knots or more) with the hourly wind and wave values
-- of their grid cell. Grid cells are matched on integer hundredths of a
-- degree to avoid floating point equality.
with t as (
    select
        *,
        cast(round(round(lat / 0.25) * 0.25 * 100) as integer) as wind_lat_key,
        cast(round(round(lon / 0.25) * 0.25 * 100) as integer) as wind_lon_key,
        cast(round(round(lat / 0.5) * 0.5 * 100) as integer) as wave_lat_key,
        cast(round(round(lon / 0.5) * 0.5 * 100) as integer) as wave_lon_key,
        date_trunc('hour', position_ts + interval 30 minute) as hour_utc
    from {{ ref('int_ais_track') }}
    where sog_kn >= 3
),

wind as (
    select cast(round(cell_lat * 100) as integer) as lat_key, cast(round(cell_lon * 100) as integer) as lon_key, *
    from {{ ref('stg_weather__wind') }}
),

waves as (
    select cast(round(cell_lat * 100) as integer) as lat_key, cast(round(cell_lon * 100) as integer) as lon_key, *
    from {{ ref('stg_weather__waves') }}
)

select
    t.ship_key,
    t.position_ts,
    t.lat,
    t.lon,
    t.sog_kn,
    t.cog_deg,
    t.step_nm,
    t.step_minutes,
    t.is_after_gap,
    wi.wind_speed_ms,
    wi.wind_direction_deg,
    wa.wave_height_m,
    wa.wave_direction_deg,
    -- Angle between the ship's course and where the wind comes from:
    -- 0 = head wind, 180 = following wind.
    abs(((wi.wind_direction_deg - t.cog_deg + 540) % 360) - 180) as wind_relative_deg
from t
left join wind wi on wi.lat_key = t.wind_lat_key and wi.lon_key = t.wind_lon_key and wi.hour_utc = t.hour_utc
left join waves wa on wa.lat_key = t.wave_lat_key and wa.lon_key = t.wave_lon_key and wa.hour_utc = t.hour_utc
