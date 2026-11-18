-- Port calls derived from AIS. Consecutive berth stops at the same port less
-- than three hours apart (for example a shift between quays) form one call.
-- Waiting time is the time anchored at the same port after the ship's
-- previous call and within 24 hours before berthing.
with berths as (
    select * from {{ ref('int_ais_stops_located') }}
    where stop_type = 'berth' and locode is not null
),

sequenced as (
    select
        *,
        case when locode is distinct from lag(locode) over w
               or date_diff('second', lag(stop_end_utc) over w, stop_start_utc) > 3 * 3600
             then 1 else 0 end as is_new_call
    from berths
    window w as (partition by ship_key order by stop_start_utc)
),

grouped as (
    select *, sum(is_new_call) over (partition by ship_key order by stop_start_utc rows unbounded preceding) as call_seq
    from sequenced
),

calls as (
    select
        ship_key,
        call_seq,
        any_value(locode) as locode,
        min(stop_start_utc) as berth_start_utc,
        max(stop_end_utc) as departure_utc,
        count(*) as berth_stops
    from grouped
    group by ship_key, call_seq
),

with_prev as (
    select *, lag(departure_utc) over (partition by ship_key order by berth_start_utc) as prev_departure_utc
    from calls
),

waiting as (
    select
        c.ship_key,
        c.call_seq,
        sum(a.stop_hours) as waiting_hours,
        min(a.stop_start_utc) as anchor_start_utc
    from with_prev c
    join {{ ref('int_ais_stops_located') }} a
      on a.ship_key = c.ship_key
     and a.stop_type = 'anchored'
     and a.locode = c.locode
     and a.stop_end_utc <= c.berth_start_utc
     and a.stop_end_utc >= c.berth_start_utc - interval 24 hour
     and (c.prev_departure_utc is null or a.stop_start_utc >= c.prev_departure_utc)
    group by 1, 2
)

select
    c.ship_key,
    c.call_seq,
    c.locode,
    coalesce(w.anchor_start_utc, c.berth_start_utc) as arrival_utc,
    c.berth_start_utc,
    c.departure_utc,
    coalesce(w.waiting_hours, 0) as waiting_hours,
    date_diff('second', c.berth_start_utc, c.departure_utc) / 3600.0 as berth_hours,
    c.berth_stops,
    -- Calls cut by the start or end of the AIS window have unknown true length.
    (c.berth_start_utc < date '{{ var("data_end_date") }}' - interval 56 day + interval 2 hour
        or c.departure_utc > date '{{ var("data_end_date") }}' + interval 1 day - interval 2 hour) as is_window_edge
from with_prev c
left join waiting w using (ship_key, call_seq)
