-- Every MMSI a fleet ship used during the AIS window (a ship can change MMSI
-- when it changes flag).
select distinct s.mmsi, s.imo_number
from {{ ref('stg_ais__static') }} s
join {{ ref('int_fleet_ships') }} f on f.imo_number = s.imo_number
where s.valid_to is null or s.valid_to >= date '{{ var("data_end_date") }}' - interval 57 day
