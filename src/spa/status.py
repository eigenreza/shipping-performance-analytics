"""Data freshness and data quality status table.

Reads the warehouse and the latest dbt run results and writes
``results/status.json``. Each row is one check with a status of ok, warn or
fail. The same table is shown by ``spa status`` and on the demo's
"How it is built" page.
"""

from __future__ import annotations

import json
from datetime import date

import duckdb

from spa.paths import DATA_END, DBT_DIR, RESULTS, WAREHOUSE

FRESHNESS = [
    # (check, table, date column, max allowed lag in days behind the data end date)
    ("AIS positions", "intermediate.int_ais_track", "position_ts", 2),
    ("AIS-derived port calls", "marts.fct_port_call", "date_key", 7),
    ("Carbon price", "marts.fct_daily_carbon_price", "date_key", 7),
    ("Weather (wind)", "staging.stg_weather__wind", "hour_utc", 2),
    ("Weather (waves)", "staging.stg_weather__waves", "hour_utc", 2),
]


def _freshness(con) -> list[dict]:
    end = date.fromisoformat(DATA_END)
    rows = []
    for name, table, col, lag in FRESHNESS:
        latest, n = con.sql(f"select max(cast({col} as date)), count(*) from {table}").fetchall()[0]
        behind = (end - latest).days if latest else None
        status = "fail" if latest is None or latest > end else ("ok" if behind <= lag else "warn")
        rows.append({
            "check": f"Freshness: {name}",
            "detail": f"latest {latest}, {n:,} rows, {behind} days before the data end date (limit {lag})",
            "status": status,
        })
    year = con.sql("select max(reporting_year) from marts.fct_ship_year_emissions").fetchall()[0][0]
    rows.append({
        "check": "Freshness: EU MRV reports",
        "detail": f"latest reporting year {year}",
        "status": "ok" if year and year >= end.year - 1 else "warn",
    })
    return rows


def _quality(con) -> list[dict]:
    rows = []
    q = con.sql("""select count(*), avg(is_quality_ok::int) from marts.fct_ship_year_emissions""").fetchall()[0]
    rows.append({
        "check": "Quality: plausible MRV ship-years",
        "detail": f"{q[1]:.1%} of {q[0]:,} ship-years pass distance, speed and carbon factor checks",
        "status": "ok" if q[1] >= 0.95 else "warn",
    })
    m = con.sql("select avg(is_kystverket_matched::int), count(*) from marts.fct_port_call where not is_window_edge").fetchall()[0]
    rows.append({
        "check": "Quality: port calls confirmed by Kystverket records",
        "detail": f"{m[0]:.1%} of {m[1]:,} AIS-derived calls have a Kystverket record within 12 hours",
        "status": "ok" if m[0] >= 0.5 else "warn",
    })
    c = con.sql("select avg((gross_tonnage is not null)::int) from marts.dim_ship where is_current").fetchall()[0][0]
    rows.append({
        "check": "Quality: ships with known or estimated gross tonnage",
        "detail": f"{c:.1%} of fleet ships",
        "status": "ok" if c >= 0.85 else "warn",
    })
    return rows


def _dbt_tests() -> list[dict]:
    path = DBT_DIR / "target" / "run_results.json"
    if not path.exists():
        return [{"check": "dbt tests", "detail": "no run results found", "status": "warn"}]
    res = json.loads(path.read_text(encoding="utf-8"))["results"]
    tests = [r for r in res if r["unique_id"].startswith("test.")]
    failed = [r for r in tests if r["status"] not in ("pass", "success")]
    return [{
        "check": "dbt tests",
        "detail": f"{len(tests) - len(failed)} of {len(tests)} tests pass",
        "status": "ok" if tests and not failed else "fail",
    }]


def run() -> list[dict]:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        rows = _freshness(con) + _quality(con) + _dbt_tests()
    finally:
        con.close()
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "status.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows
