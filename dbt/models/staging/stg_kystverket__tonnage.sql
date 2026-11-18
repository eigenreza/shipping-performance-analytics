-- Reported tonnage of ro-ro ships and vehicle carriers seen in Kystverket
-- port call records, used to calibrate the size estimate.
select distinct
    upper(trim(shipname)) as ship_name_key,
    shiptype as kv_ship_type,
    cast(gt as double) as gross_tonnage,
    cast(dwt as double) as deadweight_t
from {{ source('raw', 'tonnage_calibration') }}
where gt > 0
