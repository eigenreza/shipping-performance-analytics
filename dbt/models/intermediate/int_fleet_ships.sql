-- One row per fleet ship (IMO number) with a stable pseudonym. The pseudonym
-- number is the rank of a salted hash within the segment, so it reveals
-- nothing about the IMO number and does not change between runs.
with years as (
    select
        imo_number,
        arg_max(mrv_ship_type, reporting_year) as segment,
        min(reporting_year) as first_year,
        max(reporting_year) as last_year,
        count(*) as reporting_years,
        bool_or(technical_index_type = 'EEDI') as has_eedi
    from {{ ref('stg_mrv__ship_year') }}
    group by imo_number
),

hashed as (
    select *, {{ ship_hash('imo_number') }} as ship_hash from years
)

select
    imo_number,
    ship_hash,
    row_number() over (order by ship_hash) as ship_key,
    segment,
    case segment when 'Vehicle carrier' then 'Carrier ' else 'Ro-ro ' end
        || lpad(cast(row_number() over (partition by segment order by ship_hash) as varchar), 3, '0') as ship_pseudonym,
    first_year,
    last_year,
    reporting_years,
    case when has_eedi then 'EEDI generation (contracted 2013 or later)'
         else 'Pre-EEDI generation' end as design_generation
from hashed
