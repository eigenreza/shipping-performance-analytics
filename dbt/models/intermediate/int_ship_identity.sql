-- Links fleet ships to their AIS identity (MMSI) and AIS-reported length and
-- beam. Where a ship used more than one MMSI, the record valid latest wins.
with ranked as (
    select
        s.*,
        row_number() over (partition by s.imo_number order by coalesce(s.valid_to, timestamp '2999-01-01') desc, s.valid_from desc) as rn,
        max(case when s.length_m between 60 and 250 then s.length_m end) over (partition by s.imo_number) as length_m_any,
        max(case when s.beam_m between 10 and 45 then s.beam_m end) over (partition by s.imo_number) as beam_m_any
    from {{ ref('stg_ais__static') }} s
    join {{ ref('int_fleet_ships') }} f on f.imo_number = s.imo_number
)

select
    imo_number,
    mmsi,
    upper(trim(ais_name)) as ship_name_key,
    case when length_m between 60 and 250 then length_m else length_m_any end as length_m,
    case when beam_m between 10 and 45 then beam_m else beam_m_any end as beam_m
from ranked
where rn = 1
