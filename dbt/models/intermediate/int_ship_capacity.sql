-- Gross tonnage (GT) for each fleet ship. MRV does not publish tonnage, so GT
-- is taken from Kystverket port call records where the ship called Norway,
-- and otherwise estimated from AIS length and beam with a log-log fit,
-- calibrated per segment on the ships that have both values. Ships with no
-- AIS dimensions keep an unknown GT and get no carbon intensity rating.
with reported as (
    select ship_name_key, max(gross_tonnage) as gt_reported
    from (
        select ship_name_key, gross_tonnage from {{ ref('stg_kystverket__tonnage') }}
        union all
        select upper(trim(ship_name)), gross_tonnage from {{ ref('stg_kystverket__port_calls') }}
        where gross_tonnage > 0
    )
    group by ship_name_key
),

base as (
    select
        f.imo_number,
        f.segment,
        i.length_m,
        i.beam_m,
        -- A reported GT is accepted only when it is physically plausible for the
        -- ship's length and beam; this drops matches on a shared ship name.
        case when r.gt_reported / nullif(i.length_m * i.beam_m, 0) between 2.5 and 12
             then r.gt_reported end as gt_reported
    from {{ ref('int_fleet_ships') }} f
    left join {{ ref('int_ship_identity') }} i using (imo_number)
    left join reported r on r.ship_name_key = i.ship_name_key
),

fit as (
    select
        segment,
        regr_slope(ln(gt_reported), ln(length_m * beam_m)) as slope,
        regr_intercept(ln(gt_reported), ln(length_m * beam_m)) as intercept,
        regr_r2(ln(gt_reported), ln(length_m * beam_m)) as calibration_r2,
        regr_count(ln(gt_reported), ln(length_m * beam_m)) as n_calibration
    from base
    where gt_reported > 1000 and length_m is not null and beam_m is not null
    group by segment
),

estimated as (
    select
        b.*,
        f.calibration_r2,
        f.n_calibration,
        case when b.length_m is not null and b.beam_m is not null
             then exp(f.intercept + f.slope * ln(b.length_m * b.beam_m)) end as gt_estimated
    from base b
    left join fit f using (segment)
),

errors as (
    -- Median absolute percentage error of the estimate on ships with reported GT.
    select segment, median(abs(gt_estimated / gt_reported - 1)) as calibration_mape
    from estimated
    where gt_reported > 1000 and gt_estimated is not null
    group by segment
)

select
    e.imo_number,
    e.segment,
    e.length_m,
    e.beam_m,
    e.gt_reported,
    e.gt_estimated,
    coalesce(e.gt_reported, e.gt_estimated) as gross_tonnage,
    case when e.gt_reported is not null then 'Reported (Kystverket port calls)'
         when e.gt_estimated is not null then 'Estimated from AIS length and beam'
         else 'Unknown' end as tonnage_method,
    e.calibration_r2,
    e.n_calibration,
    x.calibration_mape
from estimated e
left join errors x using (segment)
