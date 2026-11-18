-- AIS positions (UTC). Speed over ground is recalculated by Kystverket from
-- neighbouring track points.
select
    cast(mmsi as bigint) as mmsi,
    cast(ts as timestamp) as position_ts,
    cast(lat as double) as lat,
    cast(lon as double) as lon,
    cast(sog as double) as sog_kn,
    cast(cog as double) as cog_deg,
    cast(true_heading as double) as heading_deg
from {{ source('raw', 'ais_positions') }}
where cast(ts as date) <= date '{{ var("data_end_date") }}'
  and lat between -90 and 90 and lon between -180 and 180
