-- Norwegian ports at UN/LOCODE level, positioned on the Kystverket harbour
-- point (or the mean of the port's quays where no harbour point exists).
with loc as (
    select * from {{ ref('stg_kystverket__locations') }} where locode like 'NO%'
),

harbour as (
    select locode, arg_min(location_name, location_id) as port_name, avg(lat) as lat, avg(lon) as lon, any_value(county_name) as county_name
    from loc where location_type = 'HARBOUR'
    group by locode
),

other as (
    select locode, arg_min(location_name, location_id) as port_name, avg(lat) as lat, avg(lon) as lon, any_value(county_name) as county_name
    from loc group by locode
)

select
    cast(row_number() over (order by o.locode) as integer) as port_id,
    o.locode as port_key,
    coalesce(h.port_name, o.port_name) as port_name,
    coalesce(h.lat, o.lat) as lat,
    coalesce(h.lon, o.lon) as lon,
    coalesce(h.county_name, o.county_name) as county_name
from other o
left join harbour h using (locode)
