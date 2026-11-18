# Measure catalogue

Generated from the semantic model's TMDL files by `spa docs`. Do not edit by hand.

57 measures in 11 display folders. DAX is the formula language of Power BI.

## Carbon Price

### Average EUA Price (EUR/t)

Average daily EU ETS allowance price in the selected period, EUR per tonne of CO2.

Table: `Metrics`. Format: `#,0.00`

```dax
AVERAGE('Carbon Price'[eua_price_eur_per_t])
```

### Latest EUA Price (EUR/t)

EU ETS allowance price on the last day in the selected period.

Table: `Metrics`. Format: `#,0.00`

```dax
VAR d = CALCULATE(MAX('Carbon Price'[date_key]), 'Carbon Price') RETURN CALCULATE(AVERAGE('Carbon Price'[eua_price_eur_per_t]), 'Carbon Price'[date_key] = d)
```

### EUA Price Range (EUR/t)

Highest minus lowest daily price in the selected period.

Table: `Metrics`. Format: `#,0.00`

```dax
MAX('Carbon Price'[eua_price_eur_per_t]) - MIN('Carbon Price'[eua_price_eur_per_t])
```

## Carbon Rating

### Rated Ship-Years

Ship-years with a CII rating (needs gross tonnage and a reduction factor for the year).

Table: `Metrics`. Format: `#,0`

```dax
CALCULATE(COUNTROWS('Ship Year Emissions'), KEEPFILTERS(NOT ISBLANK('Ship Year Emissions'[CII Rating])))
```

### Share Rated D or E

Share of rated ship-years with a D or E rating. Under IMO rules, a D for three years in a row or one E requires a corrective plan.

Table: `Metrics`. Format: `#,0.0%;-#,0.0%;#,0.0%`

```dax
DIVIDE(CALCULATE(COUNTROWS('Ship Year Emissions'), KEEPFILTERS('Ship Year Emissions'[CII Rating] IN {"D", "E"})), [Rated Ship-Years])
```

### Share Rated A or B

Share of rated ship-years with an A or B rating.

Table: `Metrics`. Format: `#,0.0%;-#,0.0%;#,0.0%`

```dax
DIVIDE(CALCULATE(COUNTROWS('Ship Year Emissions'), KEEPFILTERS('Ship Year Emissions'[CII Rating] IN {"A", "B"})), [Rated Ship-Years])
```

### Average CII Ratio

Average of attained CII divided by required CII. Below 1 is better than required.

Table: `Metrics`. Format: `0.000`

```dax
AVERAGE('Ship Year Emissions'[cii_ratio])
```

### Ships with Worsening Rating

Ships whose rating letter is worse than in the previous year.

Table: `Metrics`. Format: `#,0`

```dax
CALCULATE(COUNTROWS(SUMMARIZE('Ship Year Emissions', Ship[ship_key])), KEEPFILTERS('Ship Year Emissions'[Rating Worsened] = TRUE()))
```

## Data Quality

### Quality-Checked Share

Share of ship-years whose distance, speed and carbon factor are physically plausible. Efficiency measures use only these.

Table: `Metrics`. Format: `#,0.0%;-#,0.0%;#,0.0%`

```dax
DIVIDE(CALCULATE(COUNTROWS('Ship Year Emissions'), 'Ship Year Emissions'[Passes Quality Checks] = TRUE()), COUNTROWS('Ship Year Emissions'))
```

### Calls Confirmed by Kystverket

Share of AIS-derived calls that Kystverket's own port call records confirm within 12 hours.

Table: `Metrics`. Format: `#,0.0%;-#,0.0%;#,0.0%`

```dax
DIVIDE(CALCULATE(COUNTROWS('Port Calls'), 'Port Calls'[Confirmed by Kystverket] = TRUE(), 'Port Calls'[Cut by Data Window] = FALSE()), CALCULATE(COUNTROWS('Port Calls'), 'Port Calls'[Cut by Data Window] = FALSE()))
```

## EU ETS

### CO2 in EU ETS Scope (t)

CO2 counted under the EU ETS rules: 100% of voyages between EEA ports and at berth, 50% of voyages into or out of the EEA.

Table: `Metrics`. Format: `#,0`

```dax
SUM('Ship Year Emissions'[co2_ets_scope_t])
```

### EU ETS Scope Share

Share of MRV CO2 that falls under the EU ETS scope rules.

Table: `Metrics`. Format: `#,0.0%;-#,0.0%;#,0.0%`

```dax
DIVIDE([CO2 in EU ETS Scope (t)], [CO2 (t)])
```

### Allowances Due (t)

Allowances to surrender: CO2 in scope times the phase-in share (40% for 2024, 70% for 2025, 100% from 2026). Zero before 2024.

Table: `Metrics`. Format: `#,0`

```dax
SUM('Ship Year Emissions'[eua_due_t])
```

### EU ETS Cost (EUR)

Allowances due times the average EU ETS price of the same year, in euros.

Table: `Metrics`. Format: `#,0`

```dax
SUM('Ship Year Emissions'[ets_cost_eur])
```

### EU ETS Cost per Ship (EUR)

EU ETS cost divided by the number of ships reporting.

Table: `Metrics`. Format: `#,0`

```dax
DIVIDE([EU ETS Cost (EUR)], [Ships Reporting])
```

## Efficiency

### CO2 per nm (kg)

Kilograms of CO2 per nautical mile: total CO2 divided by total distance, over quality-checked ship-years. Lower is better.

Table: `Metrics`. Format: `#,0.0`

```dax
CALCULATE(DIVIDE(SUM('Ship Year Emissions'[co2_t]) * 1000, SUM('Ship Year Emissions'[distance_nm])), KEEPFILTERS('Ship Year Emissions'[Passes Quality Checks] = TRUE()))
```

### Fuel per nm (kg)

Kilograms of fuel per nautical mile over quality-checked ship-years.

Table: `Metrics`. Format: `#,0.0`

```dax
CALCULATE(DIVIDE(SUM('Ship Year Emissions'[fuel_t]) * 1000, SUM('Ship Year Emissions'[distance_nm])), KEEPFILTERS('Ship Year Emissions'[Passes Quality Checks] = TRUE()))
```

### Average Speed (kn)

Average speed in knots: distance divided by hours at sea, over quality-checked ship-years.

Table: `Metrics`. Format: `#,0.0`

```dax
CALCULATE(DIVIDE(SUM('Ship Year Emissions'[distance_nm]), SUM('Ship Year Emissions'[hours_at_sea])), KEEPFILTERS('Ship Year Emissions'[Passes Quality Checks] = TRUE()))
```

### CO2 per Tonne-Mile (g)

Grams of CO2 per tonne of cargo carried one nautical mile, for ship-years that report transport work by cargo mass.

Table: `Metrics`. Format: `#,0.0`

```dax
CALCULATE(DIVIDE(SUM('Ship Year Emissions'[co2_t]) * 1000000, SUM('Ship Year Emissions'[transport_work_tonne_nm])), KEEPFILTERS('Ship Year Emissions'[Passes Quality Checks] = TRUE()), KEEPFILTERS(NOT ISBLANK('Ship Year Emissions'[transport_work_tonne_nm])))
```

### Carbon Factor (t CO2 per t fuel)

Tonnes of CO2 per tonne of fuel. About 3.11 for heavy fuel oil and lower for LNG.

Table: `Metrics`. Format: `0.000`

```dax
DIVIDE([CO2 (t)], [Fuel (t)])
```

## Emissions

### CO2 (t)

Total CO2 emitted in the EU MRV scope, in tonnes.

Table: `Metrics`. Format: `#,0`

```dax
SUM('Ship Year Emissions'[co2_t])
```

### Fuel (t)

Total fuel burned in the EU MRV scope, in tonnes.

Table: `Metrics`. Format: `#,0`

```dax
SUM('Ship Year Emissions'[fuel_t])
```

### Distance (nm)

Distance sailed in the MRV scope, in nautical miles (total fuel divided by fuel per nautical mile).

Table: `Metrics`. Format: `#,0`

```dax
SUM('Ship Year Emissions'[distance_nm])
```

### Hours at Sea

Time at sea in the MRV scope, in hours.

Table: `Metrics`. Format: `#,0`

```dax
SUM('Ship Year Emissions'[hours_at_sea])
```

### Ships Reporting

Number of distinct ships with an MRV report in the current filter.

Table: `Metrics`. Format: `#,0`

```dax
COUNTROWS(SUMMARIZE('Ship Year Emissions', Ship[ship_key]))
```

### Ship-Years

Number of ship-year reports.

Table: `Metrics`. Format: `#,0`

```dax
COUNTROWS('Ship Year Emissions')
```

## Labels

### Ship Label

Name of the ship in view (its pseudonym), for tooltips and page headers.

Table: `Metrics`

```dax
SELECTEDVALUE(Ship[Ship], "Several ships")
```

### Selected Scope Label

Text label summarising the current selection, for page headers.

Table: `Metrics`

```dax
"Ships: " & FORMAT([Ships Reporting], "#,0") & "  |  Ship-years: " & FORMAT([Ship-Years], "#,0")
```

## Peers and Ranking

### Efficiency Rank

Rank of the ship by CO2 per nautical mile among the ships in view, 1 = lowest CO2 per mile.

Table: `Metrics`. Format: `#,0`

```dax
IF(HASONEVALUE(Ship[Ship]) && NOT ISBLANK([CO2 per nm (kg)]), RANKX(FILTER(ALLSELECTED(Ship[Ship]), NOT ISBLANK([CO2 per nm (kg)])), [CO2 per nm (kg)], , ASC, DENSE))
```

### Segment Peer CO2 per nm (kg)

CO2 per nautical mile of all ships in the same segment, for comparison with one ship.

Table: `Metrics`. Format: `#,0.0`

```dax
VAR seg = SELECTEDVALUE(Ship[Ship Segment]) RETURN CALCULATE([CO2 per nm (kg)], REMOVEFILTERS(Ship), Ship[Ship Segment] = seg)
```

### Variance vs Segment Peers

How much more (positive) or less (negative) CO2 per mile the ship emits than its segment.

Table: `Metrics`. Format: `#,0.0%;-#,0.0%;#,0.0%`

```dax
IF(NOT ISBLANK([CO2 per nm (kg)]), DIVIDE([CO2 per nm (kg)] - [Segment Peer CO2 per nm (kg)], [Segment Peer CO2 per nm (kg)]))
```

### Size-Class Peer CO2 per nm (kg)

CO2 per nautical mile of ships in the same segment and size class.

Table: `Metrics`. Format: `#,0.0`

```dax
VAR seg = SELECTEDVALUE(Ship[Ship Segment]) VAR sz = SELECTEDVALUE(Ship[Size Class]) RETURN CALCULATE([CO2 per nm (kg)], REMOVEFILTERS(Ship), Ship[Ship Segment] = seg, Ship[Size Class] = sz)
```

### Variance vs Size-Class Peers

How much more or less CO2 per mile the ship emits than ships of its segment and size class.

Table: `Metrics`. Format: `#,0.0%;-#,0.0%;#,0.0%`

```dax
IF(NOT ISBLANK([CO2 per nm (kg)]), DIVIDE([CO2 per nm (kg)] - [Size-Class Peer CO2 per nm (kg)], [Size-Class Peer CO2 per nm (kg)]))
```

## Ports

### Port Calls

Number of AIS-derived port calls.

Table: `Metrics`. Format: `#,0`

```dax
COUNTROWS('Port Calls')
```

### Median Waiting Time (h)

Median hours at anchor before berthing, over all calls (calls without waiting count as zero).

Table: `Metrics`. Format: `#,0.0`

```dax
MEDIAN('Port Calls'[waiting_hours])
```

### Average Waiting Time when Waiting (h)

Average hours at anchor for the calls that did wait.

Table: `Metrics`. Format: `#,0.0`

```dax
CALCULATE(AVERAGE('Port Calls'[waiting_hours]), KEEPFILTERS('Port Calls'[Had Waiting] = TRUE()))
```

### Share of Calls with Waiting

Share of port calls with anchorage waiting before berthing.

Table: `Metrics`. Format: `#,0.0%;-#,0.0%;#,0.0%`

```dax
DIVIDE(CALCULATE(COUNTROWS('Port Calls'), KEEPFILTERS('Port Calls'[Had Waiting] = TRUE())), [Port Calls])
```

### Total Waiting Time (h)

Total hours at anchor before berthing.

Table: `Metrics`. Format: `#,0`

```dax
SUM('Port Calls'[waiting_hours])
```

### Median Berth Time (h)

Median hours alongside the quay per call.

Table: `Metrics`. Format: `#,0.0`

```dax
MEDIAN('Port Calls'[berth_hours])
```

## Scenarios

### Carbon Price Scenario Value

Value chosen with the Carbon Price Scenario parameter (default 75).

Table: `Carbon Price Scenario`. Format: `#,0`

```dax
SELECTEDVALUE('Carbon Price Scenario'[Carbon Price Scenario], 75)
```

### Fuel Price Value

Value chosen with the Fuel Price parameter (default 550).

Table: `Fuel Price`. Format: `#,0`

```dax
SELECTEDVALUE('Fuel Price'[Fuel Price], 550)
```

### EU ETS Cost at Scenario Price (EUR)

Full-scope EU ETS cost (100% surrender, the rule from 2026) at the carbon price chosen with the Carbon Price Scenario parameter.

Table: `Metrics`. Format: `#,0`

```dax
[CO2 in EU ETS Scope (t)] * [Carbon Price Scenario Value]
```

### Speed Elasticity

Exponent b in CO2 per nautical mile ~ speed^b, from the Speed Relation choice: estimated from MRV data across ships (default, conservative) or the engineering rule b = 2.

Table: `Metrics`. Format: `0.00`

```dax
VAR p = SELECTEDVALUE('Speed Relation'[Parameter Key], "speed_elasticity_mrv") RETURN CALCULATE(MAX('Model Parameters'[Value]), 'Model Parameters'[Parameter] = p, 'Model Parameters'[Parameter Segment] = "All")
```

### Scenario CO2 (t)

CO2 if every ship sailed the same distance at the changed speed: CO2 times (1 + speed change) to the power of the elasticity.

Table: `Metrics`. Format: `#,0`

```dax
[CO2 (t)] * POWER(1 + [Speed Change Value], [Speed Elasticity])
```

### CO2 Saved (t)

CO2 avoided in the speed scenario.

Table: `Metrics`. Format: `#,0`

```dax
[CO2 (t)] - [Scenario CO2 (t)]
```

### Fuel Cost Saved (EUR)

Fuel saved in the speed scenario times the fuel price chosen with the Fuel Price parameter.

Table: `Metrics`. Format: `#,0`

```dax
([Fuel (t)] - [Fuel (t)] * POWER(1 + [Speed Change Value], [Speed Elasticity])) * [Fuel Price Value]
```

### EU ETS Cost Saved (EUR)

CO2 saved that falls under the EU ETS scope, at the scenario carbon price and full (2026) surrender.

Table: `Metrics`. Format: `#,0`

```dax
[CO2 Saved (t)] * [EU ETS Scope Share] * [Carbon Price Scenario Value]
```

### Extra Sailing Days

Added days at sea to cover the same distance at the changed speed, summed over ships. The trade-off for the savings.

Table: `Metrics`. Format: `#,0`

```dax
DIVIDE([Hours at Sea] * (DIVIDE(1, 1 + [Speed Change Value]) - 1), 24)
```

### Extra Days per Ship

Added days at sea per ship and year in the speed scenario.

Table: `Metrics`. Format: `#,0.0`

```dax
DIVIDE([Extra Sailing Days], [Ships Reporting])
```

### Speed Change Value

Value chosen with the Speed Change parameter (default -0.1).

Table: `Speed Change`. Format: `#,0.0%;-#,0.0%;#,0.0%`

```dax
SELECTEDVALUE('Speed Change'[Speed Change], -0.1)
```

## Voyages and Weather

### Voyage Legs

Number of voyage legs between port calls.

Table: `Metrics`. Format: `#,0`

```dax
COUNTROWS('Voyage Legs')
```

### Legs Arriving

Voyage legs that end in the port in view (uses the inactive destination relationship; Voyage Legs counts legs that start there).

Table: `Metrics`. Format: `#,0`

```dax
CALCULATE([Voyage Legs], USERELATIONSHIP('Voyage Legs'[destination_port_id], Port[Port Key]))
```

### Leg Distance (nm)

Distance sailed along the AIS track.

Table: `Metrics`. Format: `#,0`

```dax
SUM('Voyage Legs'[sailed_nm])
```

### Leg Speed (kn)

Average speed while under way (3 knots or more).

Table: `Metrics`. Format: `#,0.0`

```dax
DIVIDE(SUM('Voyage Legs'[sailed_nm]), SUM('Voyage Legs'[steaming_hours]))
```

### Average Wind (m/s)

Average 10 m wind speed along the legs, weighted by steaming hours.

Table: `Metrics`. Format: `#,0.0`

```dax
DIVIDE(SUMX('Voyage Legs', 'Voyage Legs'[avg_wind_ms] * 'Voyage Legs'[steaming_hours]), CALCULATE(SUM('Voyage Legs'[steaming_hours]), NOT ISBLANK('Voyage Legs'[avg_wind_ms])))
```

### Average Wave Height (m)

Average significant wave height along the legs, weighted by steaming hours.

Table: `Metrics`. Format: `0.00`

```dax
DIVIDE(SUMX('Voyage Legs', 'Voyage Legs'[avg_wave_m] * 'Voyage Legs'[steaming_hours]), CALCULATE(SUM('Voyage Legs'[steaming_hours]), NOT ISBLANK('Voyage Legs'[avg_wave_m])))
```

### Rough Weather Share

Share of steaming time in wind of 10.8 m/s or more (Beaufort 6) or waves of 2.5 m or more.

Table: `Metrics`. Format: `#,0.0%;-#,0.0%;#,0.0%`

```dax
DIVIDE(SUMX('Voyage Legs', 'Voyage Legs'[rough_share] * 'Voyage Legs'[steaming_hours]), CALCULATE(SUM('Voyage Legs'[steaming_hours]), NOT ISBLANK('Voyage Legs'[rough_share])))
```
