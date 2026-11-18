-- AIS static records for fleet ships. Length and beam come from the antenna
-- offsets (bow + stern, port + starboard).
select
    cast(mmsi as bigint) as mmsi,
    cast(cast("imoNumber" as bigint) as varchar) as imo_number,
    trim(name) as ais_name,
    cast("shipType" as integer) as ais_ship_type,
    cast("dimensionToBow" as integer) + cast("dimensionToStern" as integer) as length_m,
    cast("dimensionToPort" as integer) + cast("dimensionToStarboard" as integer) as beam_m,
    cast("validFrom" as timestamp) as valid_from,
    cast("validTo" as timestamp) as valid_to
from {{ source('raw', 'ais_static') }}
