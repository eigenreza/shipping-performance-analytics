-- Ship-year metrics: distance, speed, efficiency, EU ETS exposure and the
-- IMO carbon intensity rating (CII).
--
-- EU ETS: the CO2 in scope is 100% of intra-EEA voyages and of emissions at
-- berth plus 50% of voyages into or out of the EEA. It is computed for every
-- year (as if the scheme had applied) and multiplied by the phase-in share
-- for the allowances actually due (40% for 2024, 70% for 2025).
--
-- CII: attained CII = CO2 (grams) / (GT x distance). MRV distance and CO2
-- cover voyages linked to EEA ports, while IMO DCS covers all voyages, so the
-- rating here is an approximation computed on the MRV scope.
with y as (
    select * from {{ ref('stg_mrv__ship_year') }}
),

scope as (
    select
        y.*,
        coalesce(co2_intra_eea_voyages_t, 0) + coalesce(co2_at_berth_eea_t, 0)
            + 0.5 * (coalesce(co2_departing_eea_t, 0) + coalesce(co2_arriving_eea_t, 0)) as co2_ets_scope_t
    from y
),

carbon as (
    select year(price_date) as price_year, avg(eua_price_eur_per_t) as eua_avg_eur
    from {{ ref('stg_carbon__eua_daily') }}
    group by 1
),

cap as (
    select imo_number, gross_tonnage, tonnage_method from {{ ref('int_ship_capacity') }}
),

ref_line as (
    select
        s.imo_number,
        s.reporting_year,
        r.a * pow(case when r.capacity_cap is not null then r.capacity_cap else c.gross_tonnage end, -r.c) as cii_reference
    from scope s
    join cap c using (imo_number)
    join {{ ref('cii_reference_lines') }} r
      on r.segment = s.mrv_ship_type
     and c.gross_tonnage >= r.capacity_min
     and (r.capacity_max is null or c.gross_tonnage < r.capacity_max)
),

calc as (
    select
        s.*,
        f.ship_key,
        c.gross_tonnage,
        c.tonnage_method,
        {{ safe_divide('s.distance_nm', 's.hours_at_sea') }} as avg_speed_kn,
        {{ safe_divide('s.co2_t * 1000000', 'c.gross_tonnage * s.distance_nm') }} as cii_attained,
        rl.cii_reference,
        rl.cii_reference * (1 - z.reduction_factor) as cii_required,
        coalesce(p.surrender_share, 0) as ets_surrender_share,
        cb.eua_avg_eur
    from scope s
    join {{ ref('int_fleet_ships') }} f using (imo_number)
    left join cap c using (imo_number)
    left join ref_line rl using (imo_number, reporting_year)
    left join {{ ref('cii_reduction_factors') }} z on z.rating_year = s.reporting_year
    left join {{ ref('eu_ets_phase_in') }} p on p.emission_year = s.reporting_year
    left join carbon cb on cb.price_year = s.reporting_year
),

rated as (
select
    c.*,
    {{ safe_divide('cii_attained', 'cii_required') }} as cii_ratio,
    case
        when cii_attained is null or cii_required is null then null
        when cii_attained < b.d1 * cii_required then 'A'
        when cii_attained < b.d2 * cii_required then 'B'
        when cii_attained < b.d3 * cii_required then 'C'
        when cii_attained < b.d4 * cii_required then 'D'
        else 'E'
    end as cii_rating,
    reporting_year >= 2023 as is_official_cii_year,
    co2_ets_scope_t * ets_surrender_share as eua_due_t,
    co2_ets_scope_t * ets_surrender_share * eua_avg_eur as ets_cost_eur,
    -- Data quality: the record is usable for efficiency analysis when the
    -- derived distance, speed and carbon factor are physically plausible.
    (
        fuel_t > 0 and co2_t > 0 and distance_nm > 100 and hours_at_sea > 24
        and {{ safe_divide('distance_nm', 'hours_at_sea') }} between 3 and 26
        and co2_t / fuel_t between 2.5 and 3.3
    ) as is_quality_ok
from calc c
left join {{ ref('cii_rating_boundaries') }} b on b.segment = c.mrv_ship_type
)

select
    *,
    -- Rating of the same ship in the previous reporting year, and whether the
    -- rating letter got worse (for example C to D).
    lag(cii_rating) over (partition by ship_key order by reporting_year) as cii_rating_prev,
    case when lag(reporting_year) over (partition by ship_key order by reporting_year) = reporting_year - 1
         then cii_rating > lag(cii_rating) over (partition by ship_key order by reporting_year)
         else false end as is_rating_worse
from rated
