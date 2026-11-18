-- Kystverket port call records. Each day was queried separately, so calls
-- spanning several days appear more than once and are de-duplicated on id.
-- Times arrive with a UTC offset and are converted to UTC.
with src as (
    select * exclude (query_day) from {{ source('raw', 'kystverket_port_calls') }}
),

dedup as (
    select *, row_number() over (partition by id order by etd desc nulls last) as rn
    from src
)

select
    cast(id as bigint) as kv_call_id,
    cast(shipid as bigint) as kv_ship_id,
    trim(shipname) as ship_name,
    shiptype as kv_ship_type,
    cast(gt as double) as gross_tonnage,
    cast(dwt as double) as deadweight_t,
    cast(locationid as bigint) as location_id,
    cast(timezone('UTC', cast(eta as timestamptz)) as timestamp) as arrival_utc,
    cast(timezone('UTC', cast(etd as timestamptz)) as timestamp) as departure_utc,
    cast(hours as double) as hours_in_port
from dedup
where rn = 1
  and cast(timezone('UTC', cast(eta as timestamptz)) as date) <= date '{{ var("data_end_date") }}'
