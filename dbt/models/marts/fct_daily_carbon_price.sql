-- Grain: one row per calendar day.
select
    cast(strftime(price_date, '%Y%m%d') as integer) as date_id,
    price_date as date_key,
    eua_price_eur_per_t
from {{ ref('stg_carbon__eua_daily') }}
