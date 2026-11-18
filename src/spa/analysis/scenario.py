"""Slow steaming scenario arithmetic, shared by the analysis, the tests and the demo.

At constant distance, CO2 and fuel per year scale with (1 + speed change)^b,
where b is the speed elasticity of CO2 per nautical mile. Time at sea scales
with 1 / (1 + speed change).
"""

from __future__ import annotations


def saved_share(speed_change: float, elasticity: float) -> float:
    """Share of CO2 (and fuel) saved by a relative speed change, for example -0.10."""
    if speed_change <= -1:
        raise ValueError("speed change must be above -100%")
    return 1 - (1 + speed_change) ** elasticity


def extra_days(hours_at_sea: float, speed_change: float) -> float:
    """Extra days at sea to sail the same distance at the changed speed."""
    return hours_at_sea * (1 / (1 + speed_change) - 1) / 24


def ets_cost_saved(co2_saved_t: float, scope_share: float, carbon_price: float, surrender_share: float = 1.0) -> float:
    """EU ETS cost avoided: CO2 saved in scope, times the surrender share and the allowance price."""
    return co2_saved_t * scope_share * surrender_share * carbon_price
