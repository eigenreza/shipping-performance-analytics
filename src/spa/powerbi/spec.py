"""Specification of the Power BI semantic model.

Tables, friendly column names, relationships, measures (with descriptions,
format strings and display folders), the time intelligence calculation group,
the metric field parameter, what-if parameters and row-level security roles.
``spa powerbi`` turns this into TMDL; TOM then validates and normalises it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FACT_SYE = "Ship Year Emissions"
FACT_PC = "Port Calls"
FACT_VL = "Voyage Legs"
FACT_CP = "Carbon Price"


@dataclass
class Col:
    source: str
    name: str | None = None  # friendly name, defaults to source
    hidden: bool = False
    fmt: str | None = None
    desc: str | None = None
    sort_by: str | None = None
    summarize: str = "none"
    category: str | None = None  # dataCategory, for example Latitude


@dataclass
class Table:
    name: str
    file: str
    desc: str
    columns: list[Col] = field(default_factory=list)
    hide_unlisted: bool = True  # columns not listed are loaded and hidden


@dataclass
class Measure:
    name: str
    expr: str
    fmt: str
    folder: str
    desc: str


TABLES = [
    Table("Date", "dim_date.parquet", "Calendar from 2018 to the data end date (30 September 2026). Marked as the date table.", [
        Col("date_id", "Date Key", hidden=True, fmt="0", desc="Integer date key (yyyymmdd) used by relationships."),
        Col("date_key", "Date", fmt="mm/dd/yyyy", desc="Calendar date."),
        Col("year", "Year", fmt="0", desc="Calendar year."),
        Col("quarter_label", "Quarter", desc="Calendar quarter, Q1 to Q4.", sort_by="Quarter Number"),
        Col("quarter", "Quarter Number", hidden=True, fmt="0"),
        Col("month", "Month Number", hidden=True, fmt="0"),
        Col("month_short", "Month", sort_by="Month Number", desc="Month name, sorted by month number."),
        Col("year_month", "Year Month", desc="Year and month, for example 2026-09.", sort_by="Month Start"),
        Col("month_start", "Month Start", hidden=True, fmt="mm/dd/yyyy"),
        Col("is_weekend", "Is Weekend", desc="True on Saturdays and Sundays."),
    ]),
    Table("Segment", "dim_segment.parquet", "Fleet segment: vehicle carriers or ro-ro ships. Conformed dimension shared by all fact tables.", [
        Col("segment_id", "Segment Key", hidden=True, fmt="0"),
        Col("segment_key", "Segment", desc="Vehicle carrier or Ro-ro ship."),
        Col("segment_description", "Segment Description", desc="Plain description of the segment."),
        Col("cii_capacity_measure", "CII Capacity Measure", desc="Capacity used for the carbon intensity rating (gross tonnage for both segments)."),
    ]),
    Table("Ship", "dim_ship.parquet", "Pseudonymous ships, one row per ship version (slowly changing type 2). No names or IMO numbers.", [
        Col("ship_version_key", hidden=True, fmt="0"),
        Col("ship_key", hidden=True, fmt="0"),
        Col("ship_pseudonym", "Ship", desc="Stable pseudonym, for example Carrier 017. Ships are never shown by name."),
        Col("version_no", "Version", fmt="0", desc="Version number of the ship's attributes (a new version when flag, segment, ice class or efficiency index type changes)."),
        Col("valid_from_year", "Valid From Year", fmt="0", desc="First reporting year of this version."),
        Col("valid_to_year", "Valid To Year", fmt="0", desc="Last reporting year of this version."),
        Col("is_current", "Is Current Version", desc="True for the latest version of each ship."),
        Col("segment", "Ship Segment", desc="Segment of the ship in this version."),
        Col("flag_region", "Flag Region", desc="Broad region of the flag state, from the MRV port of registry."),
        Col("flag_state", "Flag State", desc="Flag state, from the MRV port of registry.", category="Country"),
        Col("ice_class", "Ice Class", desc="Ice class reported in MRV (None if not ice classed)."),
        Col("technical_index_type", "Efficiency Index Type", desc="Technical efficiency index reported in MRV: EEDI, EEXI or EIV."),
        Col("design_generation", "Design Generation", desc="EEDI generation (contracted 2013 or later) or pre-EEDI. A build-era proxy, since MRV has no build year."),
        Col("gross_tonnage", "Gross Tonnage", fmt="#,0", summarize="none", desc="Gross tonnage, reported by Kystverket or estimated from AIS length and beam (see Tonnage Method)."),
        Col("tonnage_method", "Tonnage Method", desc="Whether gross tonnage is reported or estimated."),
        Col("size_class", "Size Class", desc="Size band in gross tonnage."),
        Col("length_m", "Length (m)", fmt="#,0", summarize="none", desc="Length overall from AIS."),
        Col("has_ais_identity", "Seen in AIS Register", desc="True when the ship could be linked to an AIS identity."),
    ]),
    Table("Port", "dim_port.parquet", "Norwegian ports at UN/LOCODE level from the Kystverket location register.", [
        Col("port_id", "Port Key", hidden=True, fmt="0"),
        Col("port_key", "Port Code", desc="UN/LOCODE of the port."),
        Col("port_name", "Port", desc="Port name."),
        Col("county_name", "County", desc="County of the port.", category="StateOrProvince"),
        Col("lat", "Latitude", fmt="0.000", category="Latitude", summarize="none"),
        Col("lon", "Longitude", fmt="0.000", category="Longitude", summarize="none"),
    ]),
    Table(FACT_SYE, "fct_ship_year_emissions.parquet",
          "Fact table. Grain: one row per ship and EU MRV reporting year (2018 to 2025). Linked to the date table on 31 December of the year.", [
        Col("reporting_year", "Reporting Year", fmt="0", desc="MRV reporting year."),
        Col("cii_rating", "CII Rating", desc="IMO carbon intensity rating, A best to E worst (approximation on the MRV scope)."),
        Col("cii_rating_prev", "CII Rating Previous Year", desc="Rating of the same ship in the previous reporting year."),
        Col("is_rating_worse", "Rating Worsened", desc="True when the rating letter is worse than the year before."),
        Col("is_official_cii_year", "Official CII Year", desc="True from 2023, the first year ratings apply under IMO rules."),
        Col("is_quality_ok", "Passes Quality Checks", desc="True when distance, speed and carbon factor are physically plausible."),
    ]),
    Table(FACT_PC, "fct_port_call.parquet",
          "Fact table. Grain: one AIS-derived port call in Norway (ship, port, berth period), August to September 2026.", [
        Col("arrival_utc", "Arrival (UTC)", fmt="yyyy-mm-dd hh:nn", desc="Arrival in the port area: start of anchorage waiting, or berthing if there was no wait."),
        Col("berth_start_utc", "Berthing (UTC)", fmt="yyyy-mm-dd hh:nn", desc="Start of the first berth stop."),
        Col("departure_utc", "Departure (UTC)", fmt="yyyy-mm-dd hh:nn", desc="End of the last berth stop."),
        Col("has_waiting", "Had Waiting", desc="True when the ship anchored before berthing."),
        Col("is_kystverket_matched", "Confirmed by Kystverket", desc="True when Kystverket's own port call records show the same ship arriving at the same port within 12 hours."),
        Col("is_window_edge", "Cut by Data Window", desc="True when the call starts or ends at the edge of the AIS window."),
    ]),
    Table(FACT_VL, "fct_voyage_leg.parquet",
          "Fact table. Grain: one voyage leg between two consecutive port calls of the same ship on the Norwegian coast, with weather.", [
        Col("departure_utc", "Leg Departure (UTC)", fmt="yyyy-mm-dd hh:nn", desc="Departure from the origin port."),
        Col("arrival_utc", "Leg Arrival (UTC)", fmt="yyyy-mm-dd hh:nn", desc="Arrival in the destination port area."),
    ]),
    Table(FACT_CP, "fct_daily_carbon_price.parquet",
          "Fact table. Grain: one row per day. EU ETS allowance price (front December contract) in EUR per tonne of CO2.", []),
    Table("Model Parameters", "model_parameters.parquet",
          "Parameters estimated by the analysis (for example the speed elasticity of fuel per nautical mile) with their uncertainty intervals.", [
        Col("parameter", "Parameter", desc="Parameter name."),
        Col("segment", "Parameter Segment", desc="Segment the estimate applies to (All for the pooled fleet)."),
        Col("value", "Value", hidden=True, fmt="0.000", summarize="none", desc="Point estimate (read by the Speed Elasticity measure)."),
        Col("low", "Interval Low", fmt="0.000", summarize="none", desc="Lower end of the 95% bootstrap interval."),
        Col("high", "Interval High", fmt="0.000", summarize="none", desc="Upper end of the 95% bootstrap interval."),
        Col("description", "Parameter Description", desc="What the parameter means."),
    ], hide_unlisted=False),
]

# (from table, from column, to table, to column, active)
RELATIONSHIPS = [
    (FACT_SYE, "ship_version_key", "Ship", "ship_version_key", True),
    (FACT_SYE, "segment_id", "Segment", "segment_id", True),
    (FACT_SYE, "date_id", "Date", "date_id", True),
    (FACT_PC, "ship_version_key", "Ship", "ship_version_key", True),
    (FACT_PC, "segment_id", "Segment", "segment_id", True),
    (FACT_PC, "port_id", "Port", "port_id", True),
    (FACT_PC, "date_id", "Date", "date_id", True),
    (FACT_VL, "ship_version_key", "Ship", "ship_version_key", True),
    (FACT_VL, "segment_id", "Segment", "segment_id", True),
    (FACT_VL, "origin_port_id", "Port", "port_id", True),
    (FACT_VL, "destination_port_id", "Port", "port_id", False),
    (FACT_VL, "date_id", "Date", "date_id", True),
    (FACT_CP, "date_id", "Date", "date_id", True),
]

S = f"'{FACT_SYE}'"
P = f"'{FACT_PC}'"
V = f"'{FACT_VL}'"
C = f"'{FACT_CP}'"
QOK = f"KEEPFILTERS({S}[is_quality_ok] = TRUE())"

MEASURES = [
    # Emissions
    Measure("CO2 (t)", f"SUM({S}[co2_t])", "#,0", "Emissions", "Total CO2 emitted in the EU MRV scope, in tonnes."),
    Measure("Fuel (t)", f"SUM({S}[fuel_t])", "#,0", "Emissions", "Total fuel burned in the EU MRV scope, in tonnes."),
    Measure("Distance (nm)", f"SUM({S}[distance_nm])", "#,0", "Emissions", "Distance sailed in the MRV scope, in nautical miles (total fuel divided by fuel per nautical mile)."),
    Measure("Hours at Sea", f"SUM({S}[hours_at_sea])", "#,0", "Emissions", "Time at sea in the MRV scope, in hours."),
    Measure("Ships Reporting", f"COUNTROWS(SUMMARIZE({S}, Ship[ship_key]))", "#,0", "Emissions", "Number of distinct ships with an MRV report in the current filter."),
    Measure("Ship-Years", f"COUNTROWS({S})", "#,0", "Emissions", "Number of ship-year reports."),
    Measure("Quality-Checked Share", f"DIVIDE(CALCULATE(COUNTROWS({S}), {S}[is_quality_ok] = TRUE()), COUNTROWS({S}))", "#,0.0%;-#,0.0%;#,0.0%", "Data Quality",
            "Share of ship-years whose distance, speed and carbon factor are physically plausible. Efficiency measures use only these."),
    # Efficiency (quality-checked ship-years only)
    Measure("CO2 per nm (kg)", f"CALCULATE(DIVIDE(SUM({S}[co2_t]) * 1000, SUM({S}[distance_nm])), {QOK})", "#,0.0", "Efficiency",
            "Kilograms of CO2 per nautical mile: total CO2 divided by total distance, over quality-checked ship-years. Lower is better."),
    Measure("Fuel per nm (kg)", f"CALCULATE(DIVIDE(SUM({S}[fuel_t]) * 1000, SUM({S}[distance_nm])), {QOK})", "#,0.0", "Efficiency",
            "Kilograms of fuel per nautical mile over quality-checked ship-years."),
    Measure("Average Speed (kn)", f"CALCULATE(DIVIDE(SUM({S}[distance_nm]), SUM({S}[hours_at_sea])), {QOK})", "#,0.0", "Efficiency",
            "Average speed in knots: distance divided by hours at sea, over quality-checked ship-years."),
    Measure("CO2 per Tonne-Mile (g)",
            f"CALCULATE(DIVIDE(SUM({S}[co2_t]) * 1000000, SUM({S}[transport_work_tonne_nm])), {QOK}, KEEPFILTERS(NOT ISBLANK({S}[transport_work_tonne_nm])))",
            "#,0.0", "Efficiency", "Grams of CO2 per tonne of cargo carried one nautical mile, for ship-years that report transport work by cargo mass."),
    Measure("Carbon Factor (t CO2 per t fuel)", "DIVIDE([CO2 (t)], [Fuel (t)])", "0.000", "Efficiency",
            "Tonnes of CO2 per tonne of fuel. About 3.11 for heavy fuel oil and lower for LNG."),
    # EU ETS
    Measure("CO2 in EU ETS Scope (t)", f"SUM({S}[co2_ets_scope_t])", "#,0", "EU ETS",
            "CO2 counted under the EU ETS rules: 100% of voyages between EEA ports and at berth, 50% of voyages into or out of the EEA."),
    Measure("EU ETS Scope Share", "DIVIDE([CO2 in EU ETS Scope (t)], [CO2 (t)])", "#,0.0%;-#,0.0%;#,0.0%", "EU ETS",
            "Share of MRV CO2 that falls under the EU ETS scope rules."),
    Measure("Allowances Due (t)", f"SUM({S}[eua_due_t])", "#,0", "EU ETS",
            "Allowances to surrender: CO2 in scope times the phase-in share (40% for 2024, 70% for 2025, 100% from 2026). Zero before 2024."),
    Measure("EU ETS Cost (EUR)", f"SUM({S}[ets_cost_eur])", "#,0", "EU ETS",
            "Allowances due times the average EU ETS price of the same year, in euros."),
    Measure("EU ETS Cost per Ship (EUR)", "DIVIDE([EU ETS Cost (EUR)], [Ships Reporting])", "#,0", "EU ETS",
            "EU ETS cost divided by the number of ships reporting."),
    Measure("EU ETS Cost at Scenario Price (EUR)", "[CO2 in EU ETS Scope (t)] * [Carbon Price Scenario Value]", "#,0", "Scenarios",
            "Full-scope EU ETS cost (100% surrender, the rule from 2026) at the carbon price chosen with the Carbon Price Scenario parameter."),
    # Carbon price
    Measure("Average EUA Price (EUR/t)", f"AVERAGE({C}[eua_price_eur_per_t])", "#,0.00", "Carbon Price",
            "Average daily EU ETS allowance price in the selected period, EUR per tonne of CO2."),
    Measure("Latest EUA Price (EUR/t)", f"VAR d = CALCULATE(MAX({C}[date_key]), {C}) RETURN CALCULATE(AVERAGE({C}[eua_price_eur_per_t]), {C}[date_key] = d)",
            "#,0.00", "Carbon Price", "EU ETS allowance price on the last day in the selected period."),
    Measure("EUA Price Range (EUR/t)", f"MAX({C}[eua_price_eur_per_t]) - MIN({C}[eua_price_eur_per_t])", "#,0.00", "Carbon Price",
            "Highest minus lowest daily price in the selected period."),
    # CII
    Measure("Rated Ship-Years", f"CALCULATE(COUNTROWS({S}), KEEPFILTERS(NOT ISBLANK({S}[cii_rating])))", "#,0", "Carbon Rating",
            "Ship-years with a CII rating (needs gross tonnage and a reduction factor for the year)."),
    Measure("Share Rated D or E", f"DIVIDE(CALCULATE(COUNTROWS({S}), KEEPFILTERS({S}[cii_rating] IN {{\"D\", \"E\"}})), [Rated Ship-Years])", "#,0.0%;-#,0.0%;#,0.0%", "Carbon Rating",
            "Share of rated ship-years with a D or E rating. Under IMO rules, a D for three years in a row or one E requires a corrective plan."),
    Measure("Share Rated A or B", f"DIVIDE(CALCULATE(COUNTROWS({S}), KEEPFILTERS({S}[cii_rating] IN {{\"A\", \"B\"}})), [Rated Ship-Years])", "#,0.0%;-#,0.0%;#,0.0%", "Carbon Rating",
            "Share of rated ship-years with an A or B rating."),
    Measure("Average CII Ratio", f"AVERAGE({S}[cii_ratio])", "0.000", "Carbon Rating",
            "Average of attained CII divided by required CII. Below 1 is better than required."),
    Measure("Ships with Worsening Rating", f"CALCULATE(COUNTROWS(SUMMARIZE({S}, Ship[ship_key])), KEEPFILTERS({S}[is_rating_worse] = TRUE()))", "#,0", "Carbon Rating",
            "Ships whose rating letter is worse than in the previous year."),
    # Ports
    Measure("Port Calls", f"COUNTROWS({P})", "#,0", "Ports", "Number of AIS-derived port calls."),
    Measure("Median Waiting Time (h)", f"MEDIAN({P}[waiting_hours])", "#,0.0", "Ports",
            "Median hours at anchor before berthing, over all calls (calls without waiting count as zero)."),
    Measure("Average Waiting Time when Waiting (h)", f"CALCULATE(AVERAGE({P}[waiting_hours]), KEEPFILTERS({P}[has_waiting] = TRUE()))", "#,0.0", "Ports",
            "Average hours at anchor for the calls that did wait."),
    Measure("Share of Calls with Waiting", f"DIVIDE(CALCULATE(COUNTROWS({P}), KEEPFILTERS({P}[has_waiting] = TRUE())), [Port Calls])", "#,0.0%;-#,0.0%;#,0.0%", "Ports",
            "Share of port calls with anchorage waiting before berthing."),
    Measure("Total Waiting Time (h)", f"SUM({P}[waiting_hours])", "#,0", "Ports", "Total hours at anchor before berthing."),
    Measure("Median Berth Time (h)", f"MEDIAN({P}[berth_hours])", "#,0.0", "Ports", "Median hours alongside the quay per call."),
    Measure("Calls Confirmed by Kystverket", f"DIVIDE(CALCULATE(COUNTROWS({P}), {P}[is_kystverket_matched] = TRUE(), {P}[is_window_edge] = FALSE()), CALCULATE(COUNTROWS({P}), {P}[is_window_edge] = FALSE()))",
            "#,0.0%;-#,0.0%;#,0.0%", "Data Quality", "Share of AIS-derived calls that Kystverket's own port call records confirm within 12 hours."),
    # Voyages and weather
    Measure("Voyage Legs", f"COUNTROWS({V})", "#,0", "Voyages and Weather", "Number of voyage legs between port calls."),
    Measure("Legs Arriving", f"CALCULATE([Voyage Legs], USERELATIONSHIP({V}[destination_port_id], Port[port_id]))", "#,0", "Voyages and Weather",
            "Voyage legs that end in the port in view (uses the inactive destination relationship; Voyage Legs counts legs that start there)."),
    Measure("Leg Distance (nm)", f"SUM({V}[sailed_nm])", "#,0", "Voyages and Weather", "Distance sailed along the AIS track."),
    Measure("Leg Speed (kn)", f"DIVIDE(SUM({V}[sailed_nm]), SUM({V}[steaming_hours]))", "#,0.0", "Voyages and Weather",
            "Average speed while under way (3 knots or more)."),
    Measure("Average Wind (m/s)", f"DIVIDE(SUMX({V}, {V}[avg_wind_ms] * {V}[steaming_hours]), CALCULATE(SUM({V}[steaming_hours]), NOT ISBLANK({V}[avg_wind_ms])))",
            "#,0.0", "Voyages and Weather", "Average 10 m wind speed along the legs, weighted by steaming hours."),
    Measure("Average Wave Height (m)", f"DIVIDE(SUMX({V}, {V}[avg_wave_m] * {V}[steaming_hours]), CALCULATE(SUM({V}[steaming_hours]), NOT ISBLANK({V}[avg_wave_m])))",
            "0.00", "Voyages and Weather", "Average significant wave height along the legs, weighted by steaming hours."),
    Measure("Rough Weather Share", f"DIVIDE(SUMX({V}, {V}[rough_share] * {V}[steaming_hours]), CALCULATE(SUM({V}[steaming_hours]), NOT ISBLANK({V}[rough_share])))",
            "#,0.0%;-#,0.0%;#,0.0%", "Voyages and Weather", "Share of steaming time in wind of 10.8 m/s or more (Beaufort 6) or waves of 2.5 m or more."),
    # Scenarios
    Measure("Speed Elasticity",
            "VAR p = SELECTEDVALUE('Speed Relation'[Parameter Key], \"speed_elasticity_mrv\") RETURN CALCULATE(MAX('Model Parameters'[value]), 'Model Parameters'[parameter] = p, 'Model Parameters'[segment] = \"All\")",
            "0.00", "Scenarios",
            "Exponent b in CO2 per nautical mile ~ speed^b, from the Speed Relation choice: estimated from MRV data across ships (default, conservative) or the engineering rule b = 2."),
    Measure("Scenario CO2 (t)", "[CO2 (t)] * POWER(1 + [Speed Change Value], [Speed Elasticity])", "#,0", "Scenarios",
            "CO2 if every ship sailed the same distance at the changed speed: CO2 times (1 + speed change) to the power of the elasticity."),
    Measure("CO2 Saved (t)", "[CO2 (t)] - [Scenario CO2 (t)]", "#,0", "Scenarios", "CO2 avoided in the speed scenario."),
    Measure("Fuel Cost Saved (EUR)", "([Fuel (t)] - [Fuel (t)] * POWER(1 + [Speed Change Value], [Speed Elasticity])) * [Fuel Price Value]", "#,0", "Scenarios",
            "Fuel saved in the speed scenario times the fuel price chosen with the Fuel Price parameter."),
    Measure("EU ETS Cost Saved (EUR)", "[CO2 Saved (t)] * [EU ETS Scope Share] * [Carbon Price Scenario Value]", "#,0", "Scenarios",
            "CO2 saved that falls under the EU ETS scope, at the scenario carbon price and full (2026) surrender."),
    Measure("Extra Sailing Days", "DIVIDE([Hours at Sea] * (DIVIDE(1, 1 + [Speed Change Value]) - 1), 24)", "#,0", "Scenarios",
            "Added days at sea to cover the same distance at the changed speed, summed over ships. The trade-off for the savings."),
    Measure("Extra Days per Ship", "DIVIDE([Extra Sailing Days], [Ships Reporting])", "#,0.0", "Scenarios",
            "Added days at sea per ship and year in the speed scenario."),
    # Peers and ranking
    Measure("Efficiency Rank", "IF(HASONEVALUE(Ship[Ship]) && NOT ISBLANK([CO2 per nm (kg)]), RANKX(FILTER(ALLSELECTED(Ship[Ship]), NOT ISBLANK([CO2 per nm (kg)])), [CO2 per nm (kg)], , ASC, DENSE))", "#,0", "Peers and Ranking",
            "Rank of the ship by CO2 per nautical mile among the ships in view, 1 = lowest CO2 per mile."),
    Measure("Segment Peer CO2 per nm (kg)", "VAR seg = SELECTEDVALUE(Ship[Ship Segment]) RETURN CALCULATE([CO2 per nm (kg)], REMOVEFILTERS(Ship), Ship[Ship Segment] = seg)",
            "#,0.0", "Peers and Ranking", "CO2 per nautical mile of all ships in the same segment, for comparison with one ship."),
    Measure("Variance vs Segment Peers", "IF(NOT ISBLANK([CO2 per nm (kg)]), DIVIDE([CO2 per nm (kg)] - [Segment Peer CO2 per nm (kg)], [Segment Peer CO2 per nm (kg)]))", "#,0.0%;-#,0.0%;#,0.0%", "Peers and Ranking",
            "How much more (positive) or less (negative) CO2 per mile the ship emits than its segment."),
    Measure("Size-Class Peer CO2 per nm (kg)",
            "VAR seg = SELECTEDVALUE(Ship[Ship Segment]) VAR sz = SELECTEDVALUE(Ship[Size Class]) RETURN CALCULATE([CO2 per nm (kg)], REMOVEFILTERS(Ship), Ship[Ship Segment] = seg, Ship[Size Class] = sz)",
            "#,0.0", "Peers and Ranking", "CO2 per nautical mile of ships in the same segment and size class."),
    Measure("Variance vs Size-Class Peers", "IF(NOT ISBLANK([CO2 per nm (kg)]), DIVIDE([CO2 per nm (kg)] - [Size-Class Peer CO2 per nm (kg)], [Size-Class Peer CO2 per nm (kg)]))", "#,0.0%;-#,0.0%;#,0.0%", "Peers and Ranking",
            "How much more or less CO2 per mile the ship emits than ships of its segment and size class."),
    # Labels for the report
    Measure("Ship Label", "SELECTEDVALUE(Ship[Ship], \"Several ships\")", "", "Labels",
            "Name of the ship in view (its pseudonym), for tooltips and page headers."),
    Measure("Selected Scope Label", "\"Ships: \" & FORMAT([Ships Reporting], \"#,0\") & \"  |  Ship-years: \" & FORMAT([Ship-Years], \"#,0\")", "", "Labels",
            "Text label summarising the current selection, for page headers."),
]

TIME_INTELLIGENCE = [
    ("Current", "SELECTEDMEASURE()", None),
    ("Year to Date", "CALCULATE(SELECTEDMEASURE(), DATESYTD('Date'[Date]))", None),
    ("Prior Year", "CALCULATE(SELECTEDMEASURE(), SAMEPERIODLASTYEAR('Date'[Date]))", None),
    ("Year over Year", "VAR cur = SELECTEDMEASURE() VAR py = CALCULATE(SELECTEDMEASURE(), SAMEPERIODLASTYEAR('Date'[Date])) RETURN IF(NOT ISBLANK(cur) && NOT ISBLANK(py), cur - py)", None),
    ("Year over Year %", "VAR cur = SELECTEDMEASURE() VAR py = CALCULATE(SELECTEDMEASURE(), SAMEPERIODLASTYEAR('Date'[Date])) RETURN DIVIDE(cur - py, py)", "\"#,0.0%;-#,0.0%;#,0.0%\""),
    ("Rolling 12 Months", "CALCULATE(SELECTEDMEASURE(), DATESINPERIOD('Date'[Date], MAX('Date'[Date]), -12, MONTH))", None),
]

FIELD_PARAMETER = [
    "CO2 (t)", "Fuel (t)", "Distance (nm)", "CO2 per nm (kg)", "Average Speed (kn)",
    "CO2 in EU ETS Scope (t)", "EU ETS Cost (EUR)", "Share Rated D or E", "Average CII Ratio", "Ships Reporting",
]

WHAT_IF = [
    # (table, min, max, step, default, format, description)
    ("Speed Change", -0.20, 0.0, 0.01, -0.10, "#,0.0%;-#,0.0%;#,0.0%", "What-if parameter: speed change applied to every ship (negative = slower)."),
    ("Carbon Price Scenario", 0, 200, 5, 75, "#,0", "What-if parameter: EU ETS allowance price in EUR per tonne for the scenarios."),
    ("Fuel Price", 300, 1000, 25, 550, "#,0", "What-if parameter: fuel price in EUR per tonne (default 550, a documented assumption)."),
]

ROLES = [
    ("Vehicle Carriers Only", "Vehicle carrier", "Sees only vehicle carriers and their port calls and voyages."),
    ("Ro-ro Ships Only", "Ro-ro ship", "Sees only ro-ro ships and their port calls and voyages."),
]

# Best Practice Analyzer rules that conflict with a deliberate design choice, per object.
# Each exception carries its reason, also listed in docs/power-bi.md.
BPA_EXCEPTIONS = {
    "ENSURE_TABLES_HAVE_RELATIONSHIPS": "Disconnected by design: parameter, selector, measure and calculation group tables.",
    "REDUCE_USAGE_OF_CALCULATED_TABLES": "What-if parameters and field parameters are calculated tables by definition.",
    "REMOVE_ROLES_WITH_NO_MEMBERS": "Members are assigned in the Power BI service after publishing, never in the project files.",
    "DAX_MEASURES_UNQUALIFIED": "Field parameters require NAMEOF with a fully qualified measure reference.",
    "INTEGER_FORMATTING": "Ratios, prices and elasticities need two or three decimals to be readable.",
}
RATIO_MEASURES = {"Carbon Factor (t CO2 per t fuel)", "Average CII Ratio", "Speed Elasticity", "Average EUA Price (EUR/t)",
                  "Latest EUA Price (EUR/t)", "EUA Price Range (EUR/t)", "Average Wave Height (m)", "Selected Scope Label",
                  "Ship Label"}
