-- Grain: one row per voyage leg between two consecutive AIS-derived port
-- calls of the same ship on the Norwegian coast. Distance is summed along the
-- AIS track, leaving out steps across coverage gaps. Weather is averaged over
-- the positions where the ship was under way.
with calls as (
    select
        *,
        lead(port_key) over w as next_port_key,
        lead(port_id) over w as next_port_id,
        lead(berth_start_utc) over w as next_berth_start_utc,
        lead(arrival_utc) over w as next_arrival_utc
    from {{ ref('fct_port_call') }}
    window w as (partition by ship_key order by berth_start_utc)
),

legs as (
    select
        ship_key,
        ship_version_key,
        segment_key,
        segment_id,
        port_id as origin_port_id,
        port_call_key as origin_call_key,
        port_key as origin_port_key,
        next_port_key as destination_port_key,
        next_port_id as destination_port_id,
        departure_utc,
        next_arrival_utc as arrival_utc
    from calls
    where next_port_key is not null
),

track as (
    select
        l.ship_key,
        l.origin_call_key,
        sum(case when not t.is_after_gap then t.step_nm else 0 end) as sailed_nm,
        sum(case when not t.is_after_gap and t.sog_kn >= 3 then t.step_minutes else 0 end) / 60.0 as steaming_hours,
        sum(case when t.is_after_gap then t.step_minutes else 0 end) / 60.0 as gap_hours
    from legs l
    join {{ ref('int_ais_track') }} t
      on t.ship_key = l.ship_key and t.position_ts > l.departure_utc and t.position_ts <= l.arrival_utc
    group by 1, 2
),

wx as (
    select
        l.ship_key,
        l.origin_call_key,
        avg(w.wind_speed_ms) as avg_wind_ms,
        avg(w.wave_height_m) as avg_wave_m,
        max(w.wave_height_m) as max_wave_m,
        avg(case when w.wind_speed_ms >= 10.8 or w.wave_height_m >= 2.5 then 1.0 else 0.0 end) as rough_share,
        avg(case when w.wind_relative_deg <= 45 then 1.0 else 0.0 end) as head_wind_share,
        median(w.sog_kn) as median_sog_kn
    from legs l
    join {{ ref('int_track_weather') }} w
      on w.ship_key = l.ship_key and w.position_ts > l.departure_utc and w.position_ts <= l.arrival_utc
    group by 1, 2
)

select
    l.origin_call_key as voyage_leg_key,
    l.ship_key,
    l.ship_version_key,
    l.segment_key,
    l.segment_id,
    l.origin_port_id,
    l.destination_port_id,
    cast(strftime(l.departure_utc, '%Y%m%d') as integer) as date_id,
    l.origin_port_key,
    l.destination_port_key,
    cast(l.departure_utc as date) as date_key,
    l.departure_utc,
    l.arrival_utc,
    date_diff('second', l.departure_utc, l.arrival_utc) / 3600.0 as leg_hours,
    t.sailed_nm,
    t.steaming_hours,
    {{ safe_divide('t.sailed_nm', 't.steaming_hours') }} as avg_speed_kn,
    w.median_sog_kn,
    t.gap_hours,
    1 - {{ safe_divide('t.gap_hours', 'date_diff(\'second\', l.departure_utc, l.arrival_utc) / 3600.0') }} as coverage_share,
    w.avg_wind_ms,
    w.avg_wave_m,
    w.max_wave_m,
    w.rough_share,
    w.head_wind_share
from legs l
left join track t using (ship_key, origin_call_key)
left join wx w using (ship_key, origin_call_key)
where coalesce(t.sailed_nm, 0) >= 5
