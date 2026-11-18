-- Fleet AIS positions with the step from the previous position (time,
-- distance) and the ship key. Steps across coverage gaps longer than 30
-- minutes are kept but flagged, so distances are not drawn through land.
with p as (
    select
        m.imo_number,
        f.ship_key,
        s.*
    from {{ ref('stg_ais__positions') }} s
    join {{ ref('int_ais_mmsi_map') }} m using (mmsi)
    join {{ ref('int_fleet_ships') }} f using (imo_number)
),

stepped as (
    select
        *,
        lag(position_ts) over w as prev_ts,
        lag(lat) over w as prev_lat,
        lag(lon) over w as prev_lon
    from p
    window w as (partition by ship_key order by position_ts)
)

select
    ship_key,
    imo_number,
    mmsi,
    position_ts,
    lat,
    lon,
    sog_kn,
    cog_deg,
    date_diff('second', prev_ts, position_ts) / 60.0 as step_minutes,
    case when prev_ts is null then 0 else {{ haversine_nm('prev_lat', 'prev_lon', 'lat', 'lon') }} end as step_nm,
    coalesce(date_diff('second', prev_ts, position_ts) > 1800, true) as is_after_gap
from stepped
