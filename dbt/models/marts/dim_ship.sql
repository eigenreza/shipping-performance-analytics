-- Ship dimension, slowly changing type 2. A new version starts when a ship's
-- segment, flag region, ice class or technical efficiency index type changes
-- between reporting years. Facts carry both the durable ship_key and the
-- ship_version_key valid in that year. Ship names and IMO numbers are not
-- carried into this table: ships appear only under their pseudonym.
with yearly as (
    select
        y.ship_key,
        y.reporting_year,
        y.mrv_ship_type as segment,
        coalesce(r.flag_region, 'Other or unknown') as flag_region,
        coalesce(r.flag_state, 'Other or unknown') as flag_state,
        coalesce(y.ice_class, 'None') as ice_class,
        coalesce(y.technical_index_type, 'Not reported') as technical_index_type
    from {{ ref('int_ship_year') }} y
    left join {{ ref('registry_port_flag') }} r on r.port_of_registry = y.port_of_registry
),

changes as (
    select
        *,
        case when (segment, flag_region, flag_state, ice_class, technical_index_type)
                  is not distinct from lag((segment, flag_region, flag_state, ice_class, technical_index_type))
                  over (partition by ship_key order by reporting_year)
             then 0 else 1 end as is_change
    from yearly
),

versions as (
    select *, sum(is_change) over (partition by ship_key order by reporting_year rows unbounded preceding) as version_no
    from changes
),

collapsed as (
    select
        ship_key,
        version_no,
        any_value(segment) as segment,
        any_value(flag_region) as flag_region,
        any_value(flag_state) as flag_state,
        any_value(ice_class) as ice_class,
        any_value(technical_index_type) as technical_index_type,
        min(reporting_year) as valid_from_year,
        max(reporting_year) as valid_to_year
    from versions
    group by ship_key, version_no
)

select
    cast(ship_key * 100 + version_no as bigint) as ship_version_key,
    c.ship_key,
    f.ship_pseudonym,
    cast(c.version_no as integer) as version_no,
    c.valid_from_year,
    c.valid_to_year,
    c.valid_to_year = max(c.valid_to_year) over (partition by c.ship_key) as is_current,
    c.segment,
    c.flag_region,
    c.flag_state,
    c.ice_class,
    c.technical_index_type,
    f.design_generation,
    cap.gross_tonnage,
    cap.tonnage_method,
    case
        when cap.gross_tonnage is null then 'Unknown'
        when c.segment = 'Vehicle carrier' and cap.gross_tonnage < 30000 then 'Small (under 30,000 GT)'
        when c.segment = 'Vehicle carrier' and cap.gross_tonnage < 57700 then 'Medium (30,000 to 57,700 GT)'
        when c.segment = 'Vehicle carrier' then 'Large (57,700 GT and above)'
        when cap.gross_tonnage < 10000 then 'Small (under 10,000 GT)'
        when cap.gross_tonnage < 25000 then 'Medium (10,000 to 25,000 GT)'
        else 'Large (25,000 GT and above)'
    end as size_class,
    cap.length_m,
    f.first_year as first_reporting_year,
    f.last_year as last_reporting_year,
    exists (select 1 from {{ ref('int_ais_mmsi_map') }} m where m.imo_number = f.imo_number) as has_ais_identity
from collapsed c
join {{ ref('int_fleet_ships') }} f using (ship_key)
left join {{ ref('int_ship_capacity') }} cap on cap.imo_number = f.imo_number
