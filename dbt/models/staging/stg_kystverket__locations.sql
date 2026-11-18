-- Kystverket location register: harbours (with UN/LOCODE), port facilities,
-- quays, ferry quays and anchorages.
select
    cast(locationid as bigint) as location_id,
    locationcode as locode,
    locationnamenor as location_name,
    systemname as location_type,
    countyname as county_name,
    cast(lat as double) as lat,
    cast(lon as double) as lon
from {{ source('raw', 'kystverket_locations') }}
where lat is not null and lat <> 0 and lon is not null and lon <> 0
