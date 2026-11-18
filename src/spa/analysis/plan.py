"""Analysis plan, fixed before any result was computed.

Every rule the analysis follows lives here, so a reader can check that the
methods were not tuned to the results.

Q1  Drivers of fuel efficiency
    Data: ship-years that pass the quality checks and have a gross tonnage.
    Primary model (within-ship): log(CO2 per nm) = b * log(speed) + ship fixed
    effects + year fixed effects. b is the speed elasticity: how much CO2 per
    mile changes when the same ship sails faster or slower.
    Cross-sectional model: log(CO2 per nm) = b * log(speed) + c * log(GT)
    + design generation + segment + year fixed effects, to show the role of
    size and age.
    Uncertainty: 95% percentile intervals from a cluster bootstrap that
    resamples ships (B draws, fixed seed).

Q2  Slow steaming scenarios
    Speed changes of -5%, -10% and -15% applied to the latest reporting year.
    CO2 and fuel scale with (1 + change)^b at constant distance. Fuel cost at
    the documented fuel price, EU ETS cost at the average allowance price of
    the latest data year and full (2026) surrender of the CO2 in scope.
    Extra days at sea per ship = hours at sea * (1 / (1 + change) - 1) / 24.
    Bands use the bootstrap draws of b.

Q3  Carbon ratings
    Share of rated ship-years rated D or E by segment and year, with Wilson
    95% intervals. Ships whose letter worsened compared with the previous
    year, and ships rated worse in the latest year than in 2023 (first
    official year).

Q4  Port waiting and weather
    Port time per call by port: median and 90th percentile of waiting, berth
    and total port hours, share of calls with waiting (Wilson interval).
    Weather: under-way positions at 8 knots or more on voyage legs. Speed
    relative to the same ship's median speed in calm conditions (wind under
    5 m/s and waves under 1 m). Mean relative speed by wind and wave bands,
    with 95% intervals from a bootstrap over voyage legs.

Q5  Deviations
    Residuals of the cross-sectional model of Q1. A ship-year is flagged when
    its robust z-score (residual / (1.4826 * MAD)) is above 2.5 (higher CO2
    per mile than speed, size, age and segment predict) or below -2.5.

Amendment (recorded after the first run, before any scenario result was used)
    The within-ship speed elasticity came out slightly negative, which is not
    physically possible for the same hull. The reason is a property of the
    data: MRV "time at sea" runs from berth to berth and includes anchorage
    and slow port approaches, so annual average speed mixes sailing with
    waiting. Both estimates are kept and reported. For the Q2 scenarios the
    data-based case uses the cross-sectional estimate (the plan's secondary
    model), and the engineering reference uses b = 2 (propulsion power rises
    with the cube of speed, so fuel per mile rises with its square). The
    scenario results show both, so the range is visible.
"""

BOOTSTRAP_DRAWS = 1000
SEED = 17
SPEED_CHANGES = [-0.05, -0.10, -0.15]
CI = 0.95
MIN_TRANSIT_SPEED_KN = 8.0
CALM_WIND_MS = 5.0
CALM_WAVE_M = 1.0
WIND_BANDS = [0, 5, 10, 15, 40]  # m/s
WAVE_BANDS = [0, 1, 2, 3, 15]  # m
DEVIATION_Z = 2.5
MIN_CALLS_PER_PORT = 5
ENGINEERING_ELASTICITY = 2.0
