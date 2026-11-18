# Analysis

The methods were fixed in `src/spa/analysis/plan.py` before any result was computed. One amendment, recorded in the same file after the first run, is explained under question 2. All numbers below are generated from `results/analysis/*.json` by `spa docs`.

Run it with `spa analyze`. Intervals are 95% intervals: percentile intervals from a cluster bootstrap that resamples ships (so years of the same ship stay together) or voyage legs, and Wilson intervals for shares.

## 1. What drives fuel efficiency differences?

**Method.** Outcome: log of CO2 per nautical mile, per quality-checked ship-year with a known gross tonnage. Cross-sectional model: log speed, log gross tonnage, design generation (ships that report an EEDI, contracted 2013 or later), segment and year effects. Within-ship model: log speed with ship and year fixed effects, so only a ship's own changes over the years count.

<!-- BEGIN:q1 -->
| Term (outcome: log CO2 per nautical mile) | Estimate | 95% bootstrap interval |
|---|---|---|
| log(speed) | 0.247 | 0.172 to 0.327 |
| log(gross tonnage) | 0.374 | 0.330 to 0.417 |
| EEDI design generation | -0.062 | -0.092 to -0.032 |
| Vehicle carrier (against ro-ro) | -0.344 | -0.388 to -0.303 |
| log(speed), same ship over years (ship and year fixed effects) | -0.069 | -0.117 to -0.018 |

5,131 quality-checked ship-years of 928 ships; R squared 0.506.
<!-- END:q1 -->

**Reading.** On a log-log scale a coefficient is an elasticity: a coefficient b on log gross tonnage means that doubling tonnage raises CO2 per mile by 2^b - 1. Size is the strongest driver; newer EEDI-generation ships emit less per mile at the same size and speed. The speed effect is small and the within-ship estimate is even slightly negative, which is not possible for the same hull. The reason is a property of the data: MRV time at sea runs from berth to berth and includes waiting at anchor and slow port approaches, so a year with more waiting shows a lower average speed and more fuel per mile at the same time.

## 2. What would slower steaming save?

**Method.** At constant distance, CO2 and fuel scale with (1 + speed change) to the power of b. The plan named the within-ship elasticity as the input. Because that estimate is not physically meaningful (see above), the amendment uses two relations side by side: the cross-sectional estimate from MRV data as the conservative case, with its bootstrap interval, and the engineering rule b = 2 (propulsion power rises with the cube of speed, so fuel per mile with its square) as the reference. Fuel cost uses a documented fuel price assumption; EU ETS cost uses the CO2 in scope, full surrender and the average allowance price of 2026 so far. Extra days at sea = hours at sea per ship times (1 / (1 + speed change) - 1) / 24. The demo's simulator also prices that time: extra ship-days times a cost per day at sea (a planning figure in `dbt/seeds/fuel_assumptions.csv` that the visitor can change). Net gain is fuel and carbon saved minus that cost, and the simulator marks the speed change with the highest net gain.

<!-- BEGIN:q2 -->
| Speed relation | Speed change | CO2 saved | CO2 saved (t) | Fuel cost saved (EUR) | EU ETS cost saved (EUR) | Extra days per ship |
|---|---|---|---|---|---|---|
| Estimated from MRV data (conservative) | -5% | 1.3% (0.9% to 1.7%) | 121,466 | 21,564,740 | 6,638,729 | 6.3 |
| Estimated from MRV data (conservative) | -10% | 2.6% (1.8% to 3.4%) | 247,846 | 44,001,906 | 13,546,036 | 13.2 |
| Estimated from MRV data (conservative) | -15% | 3.9% (2.8% to 5.2%) | 379,629 | 67,398,358 | 20,748,660 | 21.0 |
| Engineering rule: fuel per mile rises with speed squared | -5% | 9.8% | 940,871 | 167,039,931 | 51,423,429 | 6.3 |
| Engineering rule: fuel per mile rises with speed squared | -10% | 19.0% | 1,833,492 | 325,513,712 | 100,209,759 | 13.2 |
| Engineering rule: fuel per mile rises with speed squared | -15% | 27.8% | 2,677,864 | 475,421,343 | 146,358,990 | 21.0 |

Base: 750 ships in 2025; fuel price EUR 550 per tonne; carbon price EUR 79.11 per tonne (average daily EU ETS price in 2026 up to 2026-09-30).
<!-- END:q2 -->

**Reading.** The data alone supports only a small saving, because annual averages blur speed; physics points to much more. The true value for a given ship lies between, and depends on how much of its fuel goes to propulsion rather than to auxiliary engines and port time. The trade-off in time is the same under both relations.

## 3. Which ships drift toward poor carbon ratings?

**Method.** CII rating per ship and year (see [carbon-rules.md](carbon-rules.md)), share rated D or E by segment and year with Wilson intervals, and ships whose letter worsened against the year before and against 2023.

<!-- BEGIN:q3 -->
| Year | Segment | Rated ship-years | Rated D or E (95% interval) |
|---|---|---|---|
| 2019 | Ro-ro ship | 260 | 34.2% (28.7% to 40.2%) |
| 2019 | Vehicle carrier | 404 | 33.2% (28.7% to 37.9%) |
| 2020 | Ro-ro ship | 232 | 37.1% (31.1% to 43.5%) |
| 2020 | Vehicle carrier | 421 | 29.9% (25.8% to 34.5%) |
| 2021 | Ro-ro ship | 210 | 40.5% (34.1% to 47.2%) |
| 2021 | Vehicle carrier | 430 | 37.7% (33.2% to 42.3%) |
| 2022 | Ro-ro ship | 216 | 35.6% (29.6% to 42.2%) |
| 2022 | Vehicle carrier | 430 | 45.1% (40.5% to 49.8%) |
| 2023 | Ro-ro ship | 213 | 34.3% (28.2% to 40.9%) |
| 2023 | Vehicle carrier | 416 | 43.0% (38.4% to 47.8%) |
| 2024 | Ro-ro ship | 213 | 34.7% (28.7% to 41.4%) |
| 2024 | Vehicle carrier | 407 | 41.3% (36.6% to 46.1%) |
| 2025 | Ro-ro ship | 222 | 35.6% (29.6% to 42.1%) |
| 2025 | Vehicle carrier | 431 | 37.8% (33.4% to 42.5%) |
<!-- END:q3 -->

**Reading.** The required level tightens every year, so a ship that holds its efficiency still drifts down the scale. The "drifting ships" list on the demo and in Power BI shows which pseudonymous ships moved down a letter.

## 4. How much time is lost waiting at Norwegian ports, and does weather explain slow legs?

**Method.** AIS-derived port calls (see [data-model.md](data-model.md)) for ports with at least five calls; calls cut by the start or end of the window are left out. Weather: under-way positions at 8 knots or more, compared with the same ship's median speed in calm conditions (wind under 5 m/s and waves under 1 m), averaged by wind and wave band, with intervals from resampling voyage legs.

<!-- BEGIN:q4_ports -->
| Port | Calls | Calls with waiting | Median hours at berth | 90th percentile hours at berth |
|---|---|---|---|---|
| Stavanger | 87 | 0.0% | 3.5 | 7.7 |
| Bergen | 45 | 0.0% | 2.7 | 5.6 |
| Håvik | 39 | 0.0% | 2.8 | 6.2 |
| Aibel AS | 36 | 0.0% | 3.2 | 20.2 |
| Drammen | 35 | 0.0% | 8.5 | 20.1 |
| Ålesund | 31 | 0.0% | 3.9 | 9.2 |
| Husnes | 24 | 0.0% | 7.3 | 14.6 |
| Brevik | 23 | 0.0% | 4.0 | 8.2 |
| Bokn | 22 | 0.0% | 15.3 | 47.9 |
| Kristiansund | 19 | 0.0% | 9.1 | 22.7 |
| Årdalstangen | 18 | 0.0% | 15.5 | 25.0 |
| Botnaneset - Flora | 17 | 0.0% | 4.6 | 9.4 |
<!-- END:q4_ports -->

<!-- BEGIN:q4_weather -->
| Wind or wave band | Voyage legs | Speed against calm (95% interval) |
|---|---|---|
| 0 to 5 m/s | 548 | -1.9% (-2.8% to -1.0%) |
| 5 to 10 m/s | 431 | -1.5% (-2.7% to -0.2%) |
| 10 to 15 m/s | 142 | -1.8% (-4.1% to 0.5%) |
| 15 m/s and more | 13 | 3.1% (-4.5% to 12.1%) |
| 0 to 1 m | 563 | -1.9% (-2.9% to -0.9%) |
| 1 to 2 m | 450 | -0.9% (-2.0% to 0.2%) |
| 2 to 3 m | 176 | -2.8% (-4.6% to -1.2%) |
| 3 m and more | 43 | -2.4% (-7.1% to 2.5%) |
<!-- END:q4_weather -->

**Reading.** Waiting at anchor is rare: the vehicle and ro-ro liners in this data berth on schedule and spend their port time alongside. Speed differs only a little between weather bands and the intervals overlap, so in late summer weather does not explain slow legs on its own. The calm band itself sits slightly below zero because the reference is the median speed, and ships also slow down in calm water near ports.

## 5. Deviations

**Method.** Residuals of the cross-sectional model of question 1. A ship-year is flagged when its robust z-score (residual divided by 1.4826 times the median absolute deviation) is beyond 2.5 in either direction.

<!-- BEGIN:q5 -->
| Ship | Year | Segment | CO2 per nm (kg) | Speed (kn) | Above expectation |
|---|---|---|---|---|---|
| Carrier 251 | 2018 | Vehicle carrier | 1,693.4 | 8.0 | 483% |
| Ro-ro 176 | 2018 | Ro-ro ship | 1,217.2 | 11.7 | 281% |
| Ro-ro 285 | 2019 | Ro-ro ship | 749.5 | 6.8 | 248% |
| Ro-ro 285 | 2018 | Ro-ro ship | 699.9 | 9.4 | 198% |
| Carrier 122 | 2018 | Vehicle carrier | 970.6 | 14.9 | 187% |
| Carrier 053 | 2018 | Vehicle carrier | 932.4 | 12.7 | 187% |
| Carrier 505 | 2018 | Vehicle carrier | 888.7 | 14.5 | 165% |
| Carrier 156 | 2022 | Vehicle carrier | 363.4 | 14.7 | 157% |
| Carrier 277 | 2018 | Vehicle carrier | 611.9 | 24.4 | 157% |
| Carrier 156 | 2020 | Vehicle carrier | 350.4 | 14.0 | 154% |
<!-- END:q5 -->

**Reading.** A flag means a ship-year burns far more (or less) per mile than ships of its speed, size, age and segment. Typical causes to check are long waiting with engines running, hull fouling, a trade with short legs and much port time, or a reporting issue. Flags are candidates for review, not findings.
