-- Grain: one row per AIS-derived port call (ship, port, berth period).
-- Each call is cross-checked against Kystverket's own port call records for
-- the same ship and port: a match means Kystverket logged an arrival within
-- 12 hours of the AIS-derived berthing time.
with calls as (
    select * from {{ ref('int_port_calls') }} where locode like 'NO%'
),

kv as (
    select
        upper(k.ship_name) as ship_name_key,
        l.locode,
        k.arrival_utc
    from {{ ref('stg_kystverket__port_calls') }} k
    join {{ ref('stg_kystverket__locations') }} l using (location_id)
),

ident as (
    select f.ship_key, i.ship_name_key
    from {{ ref('int_fleet_ships') }} f
    join {{ ref('int_ship_identity') }} i using (imo_number)
),

matched as (
    select
        c.ship_key,
        c.call_seq,
        min(abs(date_diff('minute', kv.arrival_utc, c.berth_start_utc))) / 60.0 as kv_arrival_diff_hours
    from calls c
    join ident i using (ship_key)
    join kv on kv.ship_name_key = i.ship_name_key
           and kv.locode = c.locode
           and kv.arrival_utc between c.arrival_utc - interval 12 hour and c.departure_utc
    group by 1, 2
)

select
    cast(c.ship_key * 10000 + c.call_seq as bigint) as port_call_key,
    c.ship_key,
    v.ship_version_key,
    v.segment as segment_key,
    case v.segment when 'Vehicle carrier' then 1 else 2 end as segment_id,
    dp.port_id,
    cast(strftime(c.berth_start_utc, '%Y%m%d') as integer) as date_id,
    c.locode as port_key,
    cast(c.berth_start_utc as date) as date_key,
    c.arrival_utc,
    c.berth_start_utc,
    c.departure_utc,
    c.waiting_hours,
    c.berth_hours,
    date_diff('second', c.arrival_utc, c.departure_utc) / 3600.0 as port_hours,
    c.waiting_hours > 0 as has_waiting,
    c.berth_stops,
    c.is_window_edge,
    m.kv_arrival_diff_hours is not null as is_kystverket_matched,
    m.kv_arrival_diff_hours
from calls c
left join matched m using (ship_key, call_seq)
-- AIS data is from 2026, so calls use the ship's current (latest) version.
join {{ ref('dim_ship') }} v on v.ship_key = c.ship_key and v.is_current
join {{ ref('dim_port') }} dp on dp.port_key = c.locode
