-- EU MRV ship-year reports for the project fleet: ro-ro ships and vehicle
-- carriers. Column names changed in the 2024 reporting format, so each
-- measure coalesces the old and new names. Distance is not published as a
-- column; it is derived as total fuel divided by fuel per nautical mile.
with src as (
    select * from {{ source('raw', 'mrv_ship_year') }}
    where ship_type in ('Ro-ro ship', 'Vehicle carrier')
),

typed as (
    select
        trim(cast(imo_number as varchar)) as imo_number,
        trim(name) as ship_name,
        ship_type as mrv_ship_type,
        cast(reporting_period as integer) as reporting_year,
        nullif(trim(technical_efficiency), '') as technical_efficiency_raw,
        upper(trim(port_of_registry)) as port_of_registry,
        nullif(trim(ice_class), '') as ice_class,
        cast(total_fuel_consumption as double) as fuel_t,
        cast(total_co2_emissions as double) as co2_t,
        cast(co2_emissions_from_all_voyages_between_ports_under_a_ms_jurisdiction as double) as co2_intra_eea_voyages_t,
        cast(co2_emissions_from_all_voyages_which_departed_from_ports_under_a_ms_jurisdiction as double) as co2_departing_eea_t,
        cast(co2_emissions_from_all_voyages_to_ports_under_a_ms_jurisdiction as double) as co2_arriving_eea_t,
        cast(co2_emissions_which_occurred_within_ports_under_a_ms_jurisdiction_at_berth as double) as co2_at_berth_eea_t,
        cast(co2_emissions_to_be_reported_under_directive_2003_87_ec as double) as co2_ets_reported_t,
        cast(coalesce(annual_total_time_spent_at_sea, annual_time_spent_at_sea, time_spent_at_sea, total_time_spent_at_sea) as double)
            as hours_at_sea,
        cast(coalesce(annual_average_fuel_consumption_per_distance, fuel_consumption_per_distance) as double) as fuel_kg_per_nm,
        cast(coalesce(annual_average_co2_emissions_per_distance, co2_emissions_per_distance) as double) as co2_kg_per_nm,
        cast(coalesce(annual_average_co2_emissions_per_transport_work_mass, co2_emissions_per_transport_work_mass) as double)
            as co2_g_per_tonne_nm
    from src
)

select
    *,
    regexp_extract(technical_efficiency_raw, '^(EEDI|EEXI|EIV)', 1) as technical_index_type,
    try_cast(regexp_extract(technical_efficiency_raw, '\(([0-9.]+)', 1) as double) as technical_index_value,
    {{ safe_divide('fuel_t * 1000', 'fuel_kg_per_nm') }} as distance_nm,
    {{ safe_divide('co2_t * 1000000', 'co2_g_per_tonne_nm') }} as transport_work_tonne_nm
from typed
where imo_number is not null
