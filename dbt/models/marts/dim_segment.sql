select
    case segment when 'Vehicle carrier' then 1 else 2 end as segment_id,
    segment as segment_key,
    segment as segment_name,
    case segment
        when 'Vehicle carrier' then 'Pure car and truck carriers that move new vehicles and rolling cargo on many decks.'
        else 'Roll-on roll-off cargo ships for trailers, rolling equipment and project cargo, without passenger capacity.'
    end as segment_description,
    'Gross tonnage' as cii_capacity_measure
from (select distinct segment from {{ ref('int_fleet_ships') }})
