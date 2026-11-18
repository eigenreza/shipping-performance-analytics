-- Stop episodes, found with the gaps-and-islands pattern on track steps.
--
-- Kystverket positions are vertices of simplified AIS tracks. While a ship
-- lies still the track has few vertices, often hours apart, so a stop is
-- recognised on the step between two positions: a step is stationary when
-- the implied speed (distance / elapsed time) is below the stop speed, or the
-- reported speed is below it on a short step. Consecutive stationary steps
-- form an episode that starts when the first step starts. Episodes shorter
-- than the minimum stop duration are manoeuvring and are dropped.
with steps as (
    select
        *,
        position_ts - to_seconds(cast(coalesce(step_minutes, 0) * 60 as bigint)) as step_start_ts,
        {{ safe_divide('step_nm', 'step_minutes / 60.0') }} as implied_kn
    from {{ ref('int_ais_track') }}
),

flagged as (
    select
        *,
        coalesce(step_minutes > 0 and (
            implied_kn < {{ var('stop_speed_kn') }}
            or (sog_kn < {{ var('stop_speed_kn') }} and step_minutes <= 10 and implied_kn < 2 * {{ var('stop_speed_kn') }})
        ), false) as is_stationary
    from steps
),

islands as (
    select
        *,
        sum(case when is_stationary then 0 else 1 end)
            over (partition by ship_key order by position_ts rows unbounded preceding) as island_id
    from flagged
)

select
    ship_key,
    island_id,
    min(step_start_ts) as stop_start_utc,
    max(position_ts) as stop_end_utc,
    date_diff('second', min(step_start_ts), max(position_ts)) / 3600.0 as stop_hours,
    median(lat) as lat,
    median(lon) as lon,
    count(*) as n_positions
from islands
where is_stationary
group by ship_key, island_id
having date_diff('second', min(step_start_ts), max(position_ts)) >= {{ var('min_stop_minutes') }} * 60
