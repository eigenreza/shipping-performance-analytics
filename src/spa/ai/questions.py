"""Evaluation questions for the AI analyst, frozen before any model was scored.

40 business questions: 10 for development (prompt tuning allowed), 30 for the
test (reported). Each gold answer is computed directly by SQL on the
warehouse at evaluation time, so it always matches the current data.

Scoring rules (fixed with the questions):
* number: correct when the model's ANSWER is within 0.5% of the gold value
  (relative), or within 0.0005 for values below 1. A share may be given as a
  fraction (0.371) or a percentage (37.1%).
* text: correct when the normalised ANSWER (lower case, no punctuation)
  equals the normalised gold, or contains it as a whole word sequence.
* An answer without an ANSWER line, or a run that fails, is wrong.
"""

from __future__ import annotations

SYE = "marts.fct_ship_year_emissions"
QOK = "is_quality_ok"

QUESTIONS = [
    # ------------------------------------------------------------ development (10)
    ("D01", "dev", "What was the total CO2 emitted by vehicle carriers in 2025, in tonnes?", "number",
     f"select sum(co2_t) from {SYE} where segment_key = 'Vehicle carrier' and reporting_year = 2025"),
    ("D02", "dev", "How many ro-ro ships reported to EU MRV for 2024?", "number",
     f"select count(distinct ship_key) from {SYE} where segment_key = 'Ro-ro ship' and reporting_year = 2024"),
    ("D03", "dev", "What was the average EU ETS allowance price in 2025, in euros per tonne?", "number",
     "select avg(eua_price_eur_per_t) from marts.fct_daily_carbon_price where year(date_key) = 2025"),
    ("D04", "dev", "What was the CO2 per nautical mile of vehicle carriers in 2023, in kg?", "number",
     f"select sum(co2_t) * 1000 / sum(distance_nm) from {SYE} where segment_key = 'Vehicle carrier' and reporting_year = 2023 and {QOK}"),
    ("D05", "dev", "Which Norwegian port had the most port calls by fleet ships?", "text",
     "select p.port_name from marts.fct_port_call c join marts.dim_port p using (port_key) group by 1 order by count(*) desc limit 1"),
    ("D06", "dev", "What share of rated ro-ro ship-years had a CII rating of D or E in 2025?", "number",
     f"select avg(case when cii_rating in ('D','E') then 1.0 else 0.0 end) from {SYE} where segment_key = 'Ro-ro ship' and reporting_year = 2025 and cii_rating is not null"),
    ("D07", "dev", "What was the total EU ETS cost of the whole fleet for 2024, in euros?", "number",
     f"select sum(ets_cost_eur) from {SYE} where reporting_year = 2024"),
    ("D08", "dev", "In which year between 2018 and 2025 was the average EU ETS allowance price highest?", "text",
     "select cast(year(date_key) as varchar) from marts.fct_daily_carbon_price where year(date_key) between 2018 and 2025 group by 1 order by avg(eua_price_eur_per_t) desc limit 1"),
    ("D09", "dev", "What was the average speed of vehicle carriers in 2025, in knots?", "number",
     f"select sum(distance_nm) / sum(hours_at_sea) from {SYE} where segment_key = 'Vehicle carrier' and reporting_year = 2025 and {QOK}"),
    ("D10", "dev", "How many vehicle carriers got a worse CII rating in 2025 than in 2024?", "number",
     f"select count(distinct ship_key) from {SYE} where segment_key = 'Vehicle carrier' and reporting_year = 2025 and is_rating_worse"),
    # ------------------------------------------------------------ test (30)
    ("T01", "test", "How much fuel did ro-ro ships burn in 2022, in tonnes?", "number",
     f"select sum(fuel_t) from {SYE} where segment_key = 'Ro-ro ship' and reporting_year = 2022"),
    ("T02", "test", "What was the total CO2 of the whole fleet (both segments) in 2019, in tonnes?", "number",
     f"select sum(co2_t) from {SYE} where reporting_year = 2019"),
    ("T03", "test", "By what percentage did total CO2 of vehicle carriers change from 2019 to 2020?", "number",
     f"select sum(case when reporting_year = 2020 then co2_t end) / sum(case when reporting_year = 2019 then co2_t end) - 1 from {SYE} where segment_key = 'Vehicle carrier'"),
    ("T04", "test", "Which segment had the lower CO2 per nautical mile in 2025: vehicle carriers or ro-ro ships?", "text",
     f"select segment_key from {SYE} where reporting_year = 2025 and {QOK} group by 1 order by sum(co2_t) / sum(distance_nm) limit 1"),
    ("T05", "test", "How many nautical miles did vehicle carriers sail in 2021?", "number",
     f"select sum(distance_nm) from {SYE} where segment_key = 'Vehicle carrier' and reporting_year = 2021"),
    ("T06", "test", "How many vehicle carrier ship-years were rated E in 2024?", "number",
     f"select count(*) from {SYE} where segment_key = 'Vehicle carrier' and reporting_year = 2024 and cii_rating = 'E'"),
    ("T07", "test", "Which vehicle carrier had the highest CO2 per nautical mile in 2025? Give its pseudonym.", "text",
     f"select s.ship_pseudonym from {SYE} f join marts.dim_ship s using (ship_version_key) where f.segment_key = 'Vehicle carrier' and f.reporting_year = 2025 and f.{QOK} order by f.co2_kg_per_nm desc limit 1"),
    ("T08", "test", "What share of the fleet's MRV CO2 in 2025 fell under the EU ETS scope rules?", "number",
     f"select sum(co2_ets_scope_t) / sum(co2_t) from {SYE} where reporting_year = 2025"),
    ("T09", "test", "How many EU ETS allowances were due for ro-ro ships for 2025, in tonnes?", "number",
     f"select sum(eua_due_t) from {SYE} where segment_key = 'Ro-ro ship' and reporting_year = 2025"),
    ("T10", "test", "What share of port calls in Norway involved waiting at anchor before berthing?", "number",
     "select avg(case when has_waiting then 1.0 else 0.0 end) from marts.fct_port_call"),
    ("T11", "test", "How many different Norwegian ports received at least one port call from fleet ships?", "number",
     "select count(distinct port_key) from marts.fct_port_call"),
    ("T12", "test", "What was the median time at berth per call in Drammen, in hours?", "number",
     "select median(c.berth_hours) from marts.fct_port_call c join marts.dim_port p using (port_key) where p.port_name = 'Drammen'"),
    ("T13", "test", "What was the average EU ETS allowance price in September 2026, in euros per tonne?", "number",
     "select avg(eua_price_eur_per_t) from marts.fct_daily_carbon_price where year(date_key) = 2026 and month(date_key) = 9"),
    ("T14", "test", "What was the highest daily EU ETS allowance price in 2023, in euros per tonne?", "number",
     "select max(eua_price_eur_per_t) from marts.fct_daily_carbon_price where year(date_key) = 2023"),
    ("T15", "test", "How many vehicle carriers in the size class 'Large (57,700 GT and above)' reported for 2025?", "number",
     f"select count(distinct f.ship_key) from {SYE} f join marts.dim_ship s using (ship_version_key) where f.segment_key = 'Vehicle carrier' and f.reporting_year = 2025 and s.size_class = 'Large (57,700 GT and above)'"),
    ("T16", "test", "What was the CO2 per nautical mile in 2025 of vehicle carriers of the EEDI generation (contracted 2013 or later), in kg?", "number",
     f"select sum(f.co2_t) * 1000 / sum(f.distance_nm) from {SYE} f join marts.dim_ship s using (ship_version_key) where f.segment_key = 'Vehicle carrier' and f.reporting_year = 2025 and f.{QOK} and s.design_generation = 'EEDI generation (contracted 2013 or later)'"),
    ("T17", "test", "What was the average ratio of attained to required CII for ro-ro ships in 2023?", "number",
     f"select avg(cii_ratio) from {SYE} where segment_key = 'Ro-ro ship' and reporting_year = 2023"),
    ("T18", "test", "Which flag region had the most fleet ships reporting for 2025?", "text",
     f"select s.flag_region from {SYE} f join marts.dim_ship s using (ship_version_key) where f.reporting_year = 2025 group by 1 order by count(distinct f.ship_key) desc limit 1"),
    ("T19", "test", "What was the combined EU ETS cost of vehicle carriers for 2024 and 2025 together, in euros?", "number",
     f"select sum(ets_cost_eur) from {SYE} where segment_key = 'Vehicle carrier' and reporting_year in (2024, 2025)"),
    ("T20", "test", "How many voyage legs between Norwegian ports were recorded?", "number",
     "select count(*) from marts.fct_voyage_leg"),
    ("T21", "test", "What was the average speed of ro-ro ships in 2018, in knots?", "number",
     f"select sum(distance_nm) / sum(hours_at_sea) from {SYE} where segment_key = 'Ro-ro ship' and reporting_year = 2018 and {QOK}"),
    ("T22", "test", "In which year between 2018 and 2025 was the fleet's CO2 per nautical mile lowest?", "text",
     f"select cast(reporting_year as varchar) from {SYE} where {QOK} group by 1 order by sum(co2_t) / sum(distance_nm) limit 1"),
    ("T23", "test", "How many port calls did fleet ships make in Bergen?", "number",
     "select count(*) from marts.fct_port_call c join marts.dim_port p using (port_key) where p.port_name = 'Bergen'"),
    ("T24", "test", "How much CO2 did vehicle carriers emit at berth in EEA ports in 2025, in tonnes?", "number",
     f"select sum(co2_at_berth_eea_t) from {SYE} where segment_key = 'Vehicle carrier' and reporting_year = 2025"),
    ("T25", "test", "How many ro-ro ship-years were rated A in 2025?", "number",
     f"select count(*) from {SYE} where segment_key = 'Ro-ro ship' and reporting_year = 2025 and cii_rating = 'A'"),
    ("T26", "test", "By what percentage did the EU ETS cost of vehicle carriers grow from 2024 to 2025?", "number",
     f"select sum(case when reporting_year = 2025 then ets_cost_eur end) / sum(case when reporting_year = 2024 then ets_cost_eur end) - 1 from {SYE} where segment_key = 'Vehicle carrier'"),
    ("T27", "test", "How many fleet ships have a gross tonnage that is estimated rather than reported? Count each ship once using its current version.", "number",
     "select count(*) from marts.dim_ship where is_current and tonnage_method = 'Estimated from AIS length and beam'"),
    ("T28", "test", "What is the average gross tonnage of vehicle carriers, using each ship's current version and only ships with a known tonnage?", "number",
     "select avg(gross_tonnage) from marts.dim_ship where is_current and segment = 'Vehicle carrier' and gross_tonnage is not null"),
    ("T29", "test", "What was the fuel consumption per nautical mile of ro-ro ships in 2025, in kg?", "number",
     f"select sum(fuel_t) * 1000 / sum(distance_nm) from {SYE} where segment_key = 'Ro-ro ship' and reporting_year = 2025 and {QOK}"),
    ("T30", "test", "In which month of 2025 was the average EU ETS allowance price highest? Give the month name.", "text",
     "select strftime(min(date_key), '%B') from marts.fct_daily_carbon_price where year(date_key) = 2025 group by month(date_key) order by avg(eua_price_eur_per_t) desc limit 1"),
]
