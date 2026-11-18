"""Reconciliation between the Power BI semantic model and the warehouse.

Two checks, both run against the model loaded in Power BI Desktop (its local
Analysis Services engine) and written to results/powerbi/:

* every measure is evaluated once, so no measure returns an error;
* key measures, by year and segment, equal the same numbers computed in SQL
  on the DuckDB warehouse (relative tolerance 1e-6).

Usage: spa powerbi-check --port <port of the running Desktop model>
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import duckdb

from spa.paths import RESULTS, ROOT, WAREHOUSE, WORK
from spa.powerbi import spec
from spa.powerbi.tmdl import MEASURE_TABLE

TOL = 1e-6
OUT = RESULTS / "powerbi"

# (id, DAX measure, DAX filter on 'Ship Year Emissions' or None, SQL)
SYE = "marts.fct_ship_year_emissions"
CHECKS = [
    ("co2_total", "CO2 (t)", None, f"select sum(co2_t) from {SYE}"),
    ("fuel_total", "Fuel (t)", None, f"select sum(fuel_t) from {SYE}"),
    ("ships_reporting", "Ships Reporting", None, f"select count(distinct ship_key) from {SYE}"),
    ("ets_cost_total", "EU ETS Cost (EUR)", None, f"select sum(ets_cost_eur) from {SYE}"),
    ("allowances_total", "Allowances Due (t)", None, f"select sum(eua_due_t) from {SYE}"),
    ("port_calls", "Port Calls", None, "select count(*) from marts.fct_port_call"),
    ("leg_distance", "Leg Distance (nm)", None, "select sum(sailed_nm) from marts.fct_voyage_leg"),
    ("eua_avg", "Average EUA Price (EUR/t)", None, "select avg(eua_price_eur_per_t) from marts.fct_daily_carbon_price"),
]
for year in (2019, 2023, 2024, 2025):
    for seg in ("Vehicle carrier", "Ro-ro ship"):
        where = f"reporting_year = {year} and segment_key = '{seg}'"
        dax_filter = f"'Ship Year Emissions'[Reporting Year] = {year}, Segment[Segment] = \"{seg}\""
        key = f"{year}_{'vc' if seg.startswith('Vehicle') else 'roro'}"
        CHECKS += [
            (f"co2_{key}", "CO2 (t)", dax_filter, f"select sum(co2_t) from {SYE} where {where}"),
            (f"co2_per_nm_{key}", "CO2 per nm (kg)", dax_filter,
             f"select sum(co2_t) * 1000 / sum(distance_nm) from {SYE} where {where} and is_quality_ok"),
            (f"speed_{key}", "Average Speed (kn)", dax_filter,
             f"select sum(distance_nm) / sum(hours_at_sea) from {SYE} where {where} and is_quality_ok"),
            (f"share_de_{key}", "Share Rated D or E", dax_filter,
             f"select avg(case when cii_rating in ('D','E') then 1.0 else 0.0 end) from {SYE} where {where} and cii_rating is not null"),
            (f"ets_cost_{key}", "EU ETS Cost (EUR)", dax_filter, f"select sum(ets_cost_eur) from {SYE} where {where}"),
        ]


def all_measures() -> list[tuple[str, str]]:
    out = [(MEASURE_TABLE, m.name) for m in spec.MEASURES]
    out += [(t[0], f"{t[0]} Value") for t in spec.WHAT_IF]
    return out


CONTEXT = "'Ship Year Emissions'[Reporting Year] = 2025, Ship[Ship] = \"{ship}\""
SHIP_MEASURES = ["Efficiency Rank", "Segment Peer CO2 per nm (kg)", "Variance vs Segment Peers",
                 "Size-Class Peer CO2 per nm (kg)", "Variance vs Size-Class Peers"]


def sample_ship() -> str:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        return con.sql("""select s.ship_pseudonym from marts.fct_ship_year_emissions f
                          join marts.dim_ship s using (ship_version_key)
                          where f.reporting_year = 2025 and f.is_quality_ok and s.size_class not like 'Unknown%'
                          order by s.ship_pseudonym limit 1""").fetchall()[0][0]
    finally:
        con.close()


def queries() -> list[dict]:
    qs = []
    ship = sample_ship()
    for name in SHIP_MEASURES:
        qs.append({"id": f"context::{name}", "dax": f'EVALUATE ROW("v", CALCULATE([{name}], {CONTEXT.format(ship=ship)}))'})
    for role, _seg, _ in spec.ROLES:
        qs.append({"id": f"rls::{role}", "roles": role,
                   "dax": 'EVALUATE ROW("segments", DISTINCTCOUNT(Segment[Segment]), "ships", [Ships Reporting], '
                          '"calls", [Port Calls], "seg", MIN(Segment[Segment]))'})
    for _, name in all_measures():
        qs.append({"id": f"measure::{name}", "dax": f'EVALUATE ROW("v", [{name}])'})
    for cid, measure, flt, _ in CHECKS:
        expr = f"CALCULATE([{measure}], {flt})" if flt else f"[{measure}]"
        qs.append({"id": f"check::{cid}", "dax": f'EVALUATE ROW("v", {expr})'})
    return qs


def run(port: int) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    qfile, rfile = WORK / "dax_queries.json", WORK / "dax_results.json"
    qfile.write_text(json.dumps(queries()), encoding="utf-8")
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(ROOT / "tools" / "powerbi" / "run_dax.ps1"), "-Port", str(port),
                    "-InFile", str(qfile), "-OutFile", str(rfile)], check=True)
    raw = json.loads(rfile.read_text(encoding="utf-8-sig"))
    res = {r["id"]: r for r in raw}
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    measures = []
    for _, name in all_measures():
        r = res[f"measure::{name}"]
        val = r["rows"][0].get("[v]") if r.get("ok") and r.get("rows") else None
        measures.append({"measure": name, "ok": bool(r.get("ok")), "value": val, "error": r.get("error")})
    context = []
    for name in SHIP_MEASURES:
        r = res[f"context::{name}"]
        val = r["rows"][0].get("[v]") if r.get("ok") and r.get("rows") else None
        context.append({"measure": name, "context": "one ship, 2025", "ok": bool(r.get("ok")) and val is not None, "value": val,
                        "error": r.get("error")})
    rls = []
    for role, segment, _ in spec.ROLES:
        r = res[f"rls::{role}"]
        row = r["rows"][0] if r.get("ok") and r.get("rows") else {}
        sql_ships = con.sql(f"select count(distinct ship_key) from {SYE} where segment_key = '{segment}'").fetchall()[0][0]
        sql_calls = con.sql(f"select count(*) from marts.fct_port_call where segment_key = '{segment}'").fetchall()[0][0]
        rls.append({"role": role, "segments_visible": row.get("[segments]"), "segment": row.get("[seg]"),
                    "ships_dax": row.get("[ships]"), "ships_sql": sql_ships, "calls_dax": row.get("[calls]"), "calls_sql": sql_calls,
                    "pass": row.get("[segments]") == 1 and row.get("[seg]") == segment and row.get("[ships]") == sql_ships
                    and (row.get("[calls]") or 0) == sql_calls})
    checks = []
    for cid, measure, flt, sql in CHECKS:
        r = res[f"check::{cid}"]
        dax = r["rows"][0].get("[v]") if r.get("ok") and r.get("rows") else None
        sqlv = con.sql(sql).fetchall()[0][0]
        sqlv = float(sqlv) if sqlv is not None else None
        ok = dax is not None and sqlv is not None and math.isclose(float(dax), sqlv, rel_tol=TOL, abs_tol=1e-9)
        checks.append({"check": cid, "measure": measure, "filter": flt or "none", "dax": dax, "sql": sqlv, "match": ok})
    con.close()
    summary = {
        "measures_evaluated": len(measures), "measures_without_error": sum(m["ok"] for m in measures),
        "reconciliation_checks": len(checks), "reconciliation_matches": sum(c["match"] for c in checks),
        "tolerance": TOL,
        "ship_context_measures_ok": sum(c["ok"] for c in context), "ship_context_measures": len(context),
        "rls_roles_passed": sum(x["pass"] for x in rls), "rls_roles": len(rls),
    }
    (OUT / "measure_smoke_test.json").write_text(json.dumps(measures, indent=2, default=str), encoding="utf-8")
    (OUT / "reconciliation.json").write_text(json.dumps({"summary": summary, "checks": checks, "ship_context": context, "rls": rls}, indent=2, default=str), encoding="utf-8")
    return summary


def desktop_port() -> int:
    import os

    base = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Power BI Desktop" / "AnalysisServicesWorkspaces"
    newest = max(base.glob("*/Data/msmdsrv.port.txt"), key=lambda p: p.stat().st_mtime)
    return int(newest.read_text(encoding="utf-16-le").lstrip(chr(0xFEFF)).strip())
