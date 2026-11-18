"""Metric catalog for the AI analyst.

Each metric has the same definition as the Power BI measure it names, written
in SQL over the star schema. The reconciliation check proves that the DAX and
SQL definitions return the same numbers.
"""

from __future__ import annotations

SYE = "marts.fct_ship_year_emissions f join marts.dim_ship s on s.ship_version_key = f.ship_version_key"
PC = "marts.fct_port_call c join marts.dim_port p on p.port_key = c.port_key join marts.dim_ship s on s.ship_version_key = c.ship_version_key"
CP = "marts.fct_daily_carbon_price d"

# name -> (Power BI measure, description, unit, SQL aggregate, FROM clause, year column)
METRICS: dict[str, dict] = {
    "co2_t": {"measure": "CO2 (t)", "description": "Total CO2 emitted in the EU MRV scope", "unit": "tonnes",
              "sql": "sum(f.co2_t)", "from": SYE, "year": "f.reporting_year"},
    "fuel_t": {"measure": "Fuel (t)", "description": "Total fuel burned in the EU MRV scope", "unit": "tonnes",
               "sql": "sum(f.fuel_t)", "from": SYE, "year": "f.reporting_year"},
    "distance_nm": {"measure": "Distance (nm)", "description": "Distance sailed in the MRV scope", "unit": "nautical miles",
                    "sql": "sum(f.distance_nm)", "from": SYE, "year": "f.reporting_year"},
    "co2_per_nm_kg": {"measure": "CO2 per nm (kg)", "description": "Kilograms of CO2 per nautical mile, quality-checked ship-years",
                      "unit": "kg per nautical mile",
                      "sql": "sum(case when f.is_quality_ok then f.co2_t end) * 1000 / sum(case when f.is_quality_ok then f.distance_nm end)",
                      "from": SYE, "year": "f.reporting_year"},
    "fuel_per_nm_kg": {"measure": "Fuel per nm (kg)", "description": "Kilograms of fuel per nautical mile, quality-checked ship-years",
                       "unit": "kg per nautical mile",
                       "sql": "sum(case when f.is_quality_ok then f.fuel_t end) * 1000 / sum(case when f.is_quality_ok then f.distance_nm end)",
                       "from": SYE, "year": "f.reporting_year"},
    "avg_speed_kn": {"measure": "Average Speed (kn)", "description": "Distance divided by hours at sea, quality-checked ship-years",
                     "unit": "knots",
                     "sql": "sum(case when f.is_quality_ok then f.distance_nm end) / sum(case when f.is_quality_ok then f.hours_at_sea end)",
                     "from": SYE, "year": "f.reporting_year"},
    "ships_reporting": {"measure": "Ships Reporting", "description": "Number of distinct ships with an MRV report", "unit": "ships",
                        "sql": "count(distinct f.ship_key)", "from": SYE, "year": "f.reporting_year"},
    "co2_ets_scope_t": {"measure": "CO2 in EU ETS Scope (t)", "description": "CO2 counted under EU ETS scope rules", "unit": "tonnes",
                        "sql": "sum(f.co2_ets_scope_t)", "from": SYE, "year": "f.reporting_year"},
    "allowances_due_t": {"measure": "Allowances Due (t)", "description": "EU ETS allowances due after the phase-in share", "unit": "tonnes",
                         "sql": "sum(f.eua_due_t)", "from": SYE, "year": "f.reporting_year"},
    "ets_cost_eur": {"measure": "EU ETS Cost (EUR)", "description": "Allowances due times the year's average EU ETS price", "unit": "EUR",
                     "sql": "sum(f.ets_cost_eur)", "from": SYE, "year": "f.reporting_year"},
    "share_rated_d_or_e": {"measure": "Share Rated D or E", "description": "Share of rated ship-years with CII rating D or E",
                           "unit": "share (0 to 1)",
                           "sql": "avg(case when f.cii_rating in ('D','E') then 1.0 when f.cii_rating is not null then 0.0 end)",
                           "from": SYE, "year": "f.reporting_year"},
    "average_cii_ratio": {"measure": "Average CII Ratio", "description": "Average attained CII divided by required CII", "unit": "ratio",
                          "sql": "avg(f.cii_ratio)", "from": SYE, "year": "f.reporting_year"},
    "port_calls": {"measure": "Port Calls", "description": "Number of AIS-derived port calls in Norway (August to September 2026)",
                   "unit": "calls", "sql": "count(*)", "from": PC, "year": "year(c.berth_start_utc)"},
    "share_calls_with_waiting": {"measure": "Share of Calls with Waiting", "description": "Share of port calls with anchorage waiting",
                                 "unit": "share (0 to 1)", "sql": "avg(case when c.has_waiting then 1.0 else 0.0 end)", "from": PC,
                                 "year": "year(c.berth_start_utc)"},
    "median_berth_hours": {"measure": "Median Berth Time (h)", "description": "Median hours alongside the quay per call", "unit": "hours",
                           "sql": "median(c.berth_hours)", "from": PC, "year": "year(c.berth_start_utc)"},
    "average_eua_price": {"measure": "Average EUA Price (EUR/t)", "description": "Average daily EU ETS allowance price",
                          "unit": "EUR per tonne CO2", "sql": "avg(d.eua_price_eur_per_t)", "from": CP, "year": "year(d.date_key)"},
}

# filter name -> SQL column, by FROM clause family
FILTERS = {
    "segment": {"f": "f.segment_key", "c": "c.segment_key"},
    "size_class": {"f": "s.size_class", "c": "s.size_class"},
    "flag_region": {"f": "s.flag_region", "c": "s.flag_region"},
    "design_generation": {"f": "s.design_generation", "c": "s.design_generation"},
    "ship": {"f": "s.ship_pseudonym", "c": "s.ship_pseudonym"},
    "port": {"c": "p.port_name"},
    "month": {"d": "month(d.date_key)"},
}


def metric_sql(name: str, filters: dict | None = None, year_from: int | None = None, year_to: int | None = None) -> tuple[str, list]:
    """SQL and parameters for one metric with optional filters and a year range."""
    if name not in METRICS:
        raise ValueError(f"unknown metric '{name}'. Use list_metrics to see the names.")
    m = METRICS[name]
    family = m["from"].split()[1][0]  # f, c or d alias of the fact table
    where, params = [], []
    for key, value in (filters or {}).items():
        if value in (None, ""):
            continue
        col = FILTERS.get(key, {}).get(family)
        if not col:
            raise ValueError(f"filter '{key}' does not apply to metric '{name}'")
        where.append(f"{col} = ?")
        params.append(value)
    if year_from is not None:
        where.append(f"{m['year']} >= ?")
        params.append(int(year_from))
    if year_to is not None:
        where.append(f"{m['year']} <= ?")
        params.append(int(year_to))
    sql = f"select {m['sql']} as value from {m['from']}" + (" where " + " and ".join(where) if where else "")
    return sql, params
