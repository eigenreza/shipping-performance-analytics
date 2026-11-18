-- Each stop episode is placed against the Kystverket location register.
-- Berth: within 1 km of a quay, port facility, ferry quay or harbour point.
-- Anchored: stopped further from any quay. The port is the nearest location
-- with a UN/LOCODE within 25 km; anchorages are tied to that port as well.
with loc as (
    select * from {{ ref('stg_kystverket__locations') }}
    where location_type in ('QUAY', 'PORT_FACILITY', 'FERRY_QUAY', 'HARBOUR', 'ANCHORAGE')
),

pairs as (
    select
        e.ship_key,
        e.island_id,
        l.location_id,
        l.location_type,
        l.locode,
        {{ haversine_nm('e.lat', 'e.lon', 'l.lat', 'l.lon') }} * 1.852 as dist_km
    from {{ ref('int_ais_stop_episodes') }} e
    join loc l
      on l.lat between e.lat - 0.3 and e.lat + 0.3
     and l.lon between e.lon - 0.6 and e.lon + 0.6
),

nearest_quay as (
    select ship_key, island_id, min(dist_km) as quay_km
    from pairs where location_type <> 'ANCHORAGE'
    group by 1, 2
),

nearest_anchorage as (
    select ship_key, island_id, min(dist_km) as anchorage_km
    from pairs where location_type = 'ANCHORAGE'
    group by 1, 2
),

nearest_port as (
    select ship_key, island_id, arg_min(locode, dist_km) as locode, min(dist_km) as port_km
    from pairs
    where locode is not null and location_type <> 'ANCHORAGE'
    group by 1, 2
)

select
    e.*,
    q.quay_km,
    a.anchorage_km,
    case when p.port_km <= 25 then p.locode end as locode,
    case
        when q.quay_km <= 1.0 then 'berth'
        when p.port_km <= 25 then 'anchored'
        else 'stopped at sea'
    end as stop_type
from {{ ref('int_ais_stop_episodes') }} e
left join nearest_quay q using (ship_key, island_id)
left join nearest_anchorage a using (ship_key, island_id)
left join nearest_port p using (ship_key, island_id)
