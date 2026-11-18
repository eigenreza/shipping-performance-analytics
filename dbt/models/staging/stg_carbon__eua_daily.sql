-- Daily EU ETS allowance price. Ember's series carries a value for every
-- calendar day; weekend and holiday values repeat the last trading price.
select
    cast(price_date as date) as price_date,
    cast(eua_price_eur as double) as eua_price_eur_per_t
from {{ source('raw', 'eua_daily') }}
where cast(price_date as date) <= date '{{ var("data_end_date") }}'
