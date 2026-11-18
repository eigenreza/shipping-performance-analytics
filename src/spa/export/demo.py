"""Precomputed data for the demo app (demo/data/*.json).

Everything the demo shows comes from the warehouse and the result files;
nothing is typed by hand. Only pseudonymous, aggregated or public reference
data is written. The data snapshot is identified by a content hash of the
gold tables, never by a date.
"""

from __future__ import annotations

import hashlib
import json
import math

import duckdb
from shapely.geometry import mapping, shape

from spa.paths import DBT_DIR, EXPORTS, RAW, RESULTS, ROOT, WAREHOUSE
from spa.powerbi import spec
from spa.powerbi.tmdl import translate

OUT = ROOT / "demo" / "frontend" / "public" / "data"
REPO = "https://github.com/eigenreza/shipping-performance-analytics"


def clean(o):
    if isinstance(o, float):
        return None if not math.isfinite(o) else round(o, 1 if abs(o) >= 1000 else 4)
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return o


def dump(name: str, obj) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(clean(obj), separators=(",", ":"), ensure_ascii=False)
    (OUT / f"{name}.json").write_text(text, encoding="utf-8")
    return len(text)


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else None


def snapshot_hash() -> str:
    h = hashlib.sha256()
    for f in sorted((EXPORTS / "gold").glob("*.parquet")):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:12]


def rows(con, sql) -> list[dict]:
    df = con.sql(sql).df()
    return json.loads(df.to_json(orient="records", double_precision=6, date_format="iso"))


def fleet(con) -> dict:
    data = rows(con, """
        select s.ship_pseudonym as ship, f.segment_key as segment, f.reporting_year as year, s.size_class as size,
               s.flag_region as flag, s.design_generation as gen, s.gross_tonnage as gt,
               f.co2_t as co2, f.fuel_t as fuel, f.distance_nm as dist, f.hours_at_sea as hours, f.avg_speed_kn as speed,
               f.co2_kg_per_nm as co2nm, f.co2_ets_scope_t as ets_scope, f.eua_due_t as eua, f.ets_cost_eur as ets_cost,
               f.cii_rating as cii, f.cii_ratio, f.is_rating_worse as worse, f.is_quality_ok as ok
        from marts.fct_ship_year_emissions f join marts.dim_ship s using (ship_version_key)
        order by ship, year""")
    cols = list(data[0].keys())
    return {"columns": cols, "rows": [[r[c] for c in cols] for r in data]}


def ports(con, q4) -> dict:
    calls = rows(con, """
        select p.port_name as port, p.lat, p.lon, p.county_name as county, c.segment_key as segment,
               c.waiting_hours as wait, c.berth_hours as berth, c.port_hours as total, c.is_window_edge as edge,
               c.is_kystverket_matched as confirmed, strftime(c.berth_start_utc, '%Y-%m-%d') as day
        from marts.fct_port_call c join marts.dim_port p using (port_key)""")
    legs = rows(con, """
        select avg_speed_kn as speed, avg_wind_ms as wind, avg_wave_m as wave, sailed_nm as nm, segment_key as segment
        from marts.fct_voyage_leg where avg_speed_kn between 3 and 25""")
    return {"calls": calls, "legs": legs, "speed_by_wind": q4["speed_by_wind"], "speed_by_waves": q4["speed_by_waves"],
            "summary": {k: v for k, v in q4.items() if not (isinstance(v, list) and v and isinstance(v[0], dict))}}


def coastline() -> dict:
    src = RAW / "ports" / "ne_land_norway.geojson"
    if not src.exists():
        return {"type": "FeatureCollection", "features": []}
    gj = json.loads(src.read_text())
    feats = []
    for f in gj["features"]:
        g = shape(f["geometry"]).simplify(0.02, preserve_topology=True)
        if not g.is_empty:
            feats.append({"type": "Feature", "properties": {}, "geometry": json.loads(json.dumps(mapping(g)))})
    out = {"type": "FeatureCollection", "features": feats}
    txt = json.dumps(out)
    txt = __import__("re").sub(r"(\d+\.\d{3})\d+", r"\1", txt)
    return json.loads(txt)


def lineage() -> dict:
    manifest = load(DBT_DIR / "target" / "manifest.json")
    if not manifest:
        return {"nodes": [], "edges": []}
    nodes, edges = [], []
    for uid, n in {**manifest["nodes"], **manifest["sources"]}.items():
        if n["resource_type"] not in ("model", "seed", "source"):
            continue
        layer = n["resource_type"] if n["resource_type"] != "model" else n["fqn"][1]
        nodes.append({"id": uid, "name": n["name"], "layer": layer, "description": (n.get("description") or "")[:240]})
        for parent in n.get("depends_on", {}).get("nodes", []):
            if parent.startswith(("model.", "seed.", "source.")):
                edges.append([parent, uid])
    tests = sum(1 for n in manifest["nodes"].values() if n["resource_type"] == "test")
    return {"nodes": nodes, "edges": edges, "tests": tests}


def powerbi() -> dict:
    measures = [{"name": m.name, "folder": m.folder, "dax": translate(m.expr), "description": m.desc, "format": m.fmt}
                for m in spec.MEASURES]
    measures += [{"name": f"{t[0]} Value", "folder": "Scenarios", "dax": f"SELECTEDVALUE('{t[0]}'[{t[0]}], {t[4]})",
                  "description": t[6], "format": t[5]} for t in spec.WHAT_IF]
    tables = [{"name": t.name, "description": t.desc,
               "kind": "fact" if t.name in (spec.FACT_SYE, spec.FACT_PC, spec.FACT_VL, spec.FACT_CP) else "dimension"}
              for t in spec.TABLES]
    rels = [{"from": f"{a}[{b}]", "to": f"{c}[{d}]", "active": e} for a, b, c, d, e in spec.RELATIONSHIPS]
    shots = sorted(p.name for p in (ROOT / "demo" / "frontend" / "public" / "powerbi").glob("*.png")) \
        if (ROOT / "demo" / "frontend" / "public" / "powerbi").exists() else []
    return {
        "measures": measures, "tables": tables, "relationships": rels,
        "calculation_group": [{"item": n, "dax": e} for n, e, _ in spec.TIME_INTELLIGENCE],
        "field_parameter": spec.FIELD_PARAMETER,
        "what_if": [{"name": t[0], "min": t[1], "max": t[2], "step": t[3], "default": t[4], "description": t[6]} for t in spec.WHAT_IF],
        "roles": [{"name": n, "segment": s, "description": d} for n, s, d in spec.ROLES],
        "bpa_exceptions": spec.BPA_EXCEPTIONS,
        "bpa": load(RESULTS / "powerbi" / "bpa.json"),
        "reconciliation": load(RESULTS / "powerbi" / "reconciliation.json"),
        "screenshots": shots,
    }


SOURCES = [
    {"name": "EU MRV public emission reports (THETIS-MRV)", "publisher": "European Maritime Safety Agency (EMSA)",
     "use": "Yearly fuel, CO2, distance and time at sea per ship, 2018 to 2025", "licence": "Reuse allowed with acknowledgement of EMSA",
     "url": "https://mrv.emsa.europa.eu/#public/emission-report"},
    {"name": "AIS positions, port calls and location register (Kystdatahuset)", "publisher": "Norwegian Coastal Administration (Kystverket)",
     "use": "Ship tracks and port calls on the Norwegian coast, 5 August to 30 September 2026",
     "licence": "Norwegian licence for open government data (NLOD)", "url": "https://kystdatahuset.no"},
    {"name": "Historical Weather API (ERA5) and Marine Weather API", "publisher": "Open-Meteo",
     "use": "Hourly wind and wave height along voyage legs", "licence": "CC BY 4.0; ERA5 generated using Copernicus Climate Change Service information",
     "url": "https://open-meteo.com"},
    {"name": "EU ETS allowance price (front December contract)", "publisher": "Ember",
     "use": "Daily carbon price, 2018 to 30 September 2026", "licence": "CC BY 4.0", "url": "https://ember-energy.org"},
    {"name": "Land polygons (1:10m)", "publisher": "Natural Earth", "use": "Coastline on the port map", "licence": "Public domain",
     "url": "https://www.naturalearthdata.com"},
    {"name": "IMO CII guidelines and EU ETS directive", "publisher": "IMO (MEPC.352-354(78), MEPC.338(76), MEPC.400(83)); EUR-Lex (Directive (EU) 2023/959)",
     "use": "Reference lines, reduction factors, rating boundaries; phase-in and scope rules", "licence": "Official public texts",
     "url": "https://eur-lex.europa.eu/eli/dir/2023/959/oj"},
]

FABRIC = [
    {"piece": "Raw Parquet files (data/raw)", "fabric": "Lakehouse Files area", "state": "Fabric-ready"},
    {"piece": "Bronze, silver, gold Delta tables (deltalake package)", "fabric": "Lakehouse Tables (Delta), medallion layers", "state": "Fabric-ready"},
    {"piece": "Python ingest modules and spa refresh", "fabric": "Notebooks and a Data Pipeline", "state": "Fabric-ready"},
    {"piece": "dbt models on DuckDB", "fabric": "Warehouse with dbt-fabric, or Spark SQL notebooks", "state": "Fabric-ready"},
    {"piece": "TMDL semantic model (Import from Parquet)", "fabric": "Semantic model in Direct Lake mode on the gold tables", "state": "Fabric-ready"},
    {"piece": "PBIR report and RDL paginated report", "fabric": "Report and paginated report items in a workspace", "state": "Fabric-ready"},
]


SIM_LAST_YEAR = 2030  # the CII reduction factors are set by IMO up to 2030


def simulator(ships, rules, bounds, q2, carbon, assumptions) -> dict:
    """Everything the home-page simulator needs: one row per ship of the base year plus the rule tables.

    The browser recomputes CO2, fuel cost, EU ETS cost, days at sea and CII ratings for any speed change,
    carbon price and rule year, with the same formulas as spa.analysis.scenario and the dbt CII model.
    """
    z = {r["year"]: r["z"] for r in rules["cii_reduction"]}
    phase = {r["year"]: r["share"] for r in rules["ets_phase_in"]}
    base = int(q2["base_year"])
    years = [y for y in sorted(z) if base <= y <= SIM_LAST_YEAR]
    # EU ETS surrender stays at the full share after the phase-in (Directive 2003/87/EC Art. 3gb).
    last = phase[max(phase)]
    rel = q2["relations"]
    recent = [c["price"] for c in carbon if c["month"] >= f"{base}-01"]
    return {
        "base_year": base,
        "segments": sorted({s[0] for s in ships}),
        # The CII ratio and reduction factors are sent as integers in millionths, so a ship near a rating
        # boundary gets the same letter in the browser as in the warehouse (the JSON writer rounds floats).
        "ships": [[s[0], round(s[1], 1), round(s[2], 1), round(s[3], 1), round(s[4], 1),
                   None if s[5] is None else round(s[5] * 1e6), round(s[6], 1)] for s in ships],
        "columns": ["segment", "co2_t", "fuel_t", "hours_at_sea", "co2_ets_scope_t", "cii_ratio_millionths", "distance_nm"],
        "years": years,
        "cii_reduction_millionths": {str(y): round(z[y] * 1e6) for y in years},
        "ets_share": {str(y): phase.get(y, last) for y in years},
        "cii_bounds": {b["segment"]: [b["d1"], b["d2"], b["d3"], b["d4"]] for b in bounds},
        "fuel_price": q2["fuel_price_eur_per_t"],
        "day_cost": assumptions["day_cost"],
        "carbon_price": q2["carbon_price_eur_per_t"],
        "carbon_price_basis": q2["carbon_price_basis"],
        "carbon_price_range": [round(min(recent), 1), round(max(recent), 1)],
        "elasticity": {"data": rel["mrv_estimate"]["elasticity"], "data_low": rel["mrv_estimate"]["low"],
                       "data_high": rel["mrv_estimate"]["high"], "engineering": rel["engineering"]["elasticity"]},
    }


def run() -> dict:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    a = RESULTS / "analysis"
    q = {n: load(a / f"{n}.json") for n in ("q1_drivers", "q2_scenarios", "q3_ratings", "q4_ports_weather", "q5_deviations")}
    sizes = {}
    try:
        carbon = rows(con, """select strftime(date_key, '%Y-%m') as month, avg(eua_price_eur_per_t) as price
                              from marts.fct_daily_carbon_price group by 1 order by 1""")
        q2 = q["q2_scenarios"]
        sim = con.sql(f"""select segment_key, co2_t, fuel_t, hours_at_sea, co2_ets_scope_t, cii_ratio, distance_nm
                          from marts.fct_ship_year_emissions
                          where is_quality_ok and reporting_year = {int(q2['base_year'])} order by ship_key""").fetchall()
        bounds = rows(con, "select segment, d1, d2, d3, d4 from reference.cii_rating_boundaries order by 1")
        assumptions = {r["assumption"]: r["value"] for r in rows(con, "select assumption, value from reference.fuel_assumptions")}
        rules = {"cii_reduction": rows(con, "select rating_year as year, reduction_factor as z from reference.cii_reduction_factors order by 1"),
                 "ets_phase_in": rows(con, "select emission_year as year, surrender_share as share from reference.eu_ets_phase_in order by 1")}
        counts = con.sql("""select (select count(*) from marts.fct_ship_year_emissions), (select count(distinct ship_key) from marts.dim_ship),
                                   (select count(*) from marts.fct_port_call), (select count(*) from marts.fct_voyage_leg),
                                   (select count(*) from intermediate.int_ais_track), (select count(distinct ship_key) from intermediate.int_ais_track)""").fetchall()[0]
        sizes["fleet"] = dump("fleet", fleet(con))
        sizes["ports"] = dump("ports", ports(con, q["q4_ports_weather"]))
    finally:
        con.close()
    meta = {
        "snapshot": snapshot_hash(), "repo": REPO, "author": "Reza Azad Gholami",
        "counts": {"ship_years": counts[0], "ships": counts[1], "port_calls": counts[2], "voyage_legs": counts[3],
                   "ais_positions": counts[4], "ais_ships": counts[5]},
        "status": load(RESULTS / "status.json"),
    }
    sizes["meta"] = dump("meta", meta)
    sizes["analysis"] = dump("analysis", q)
    sizes["simulator"] = dump("simulator", simulator(sim, rules, bounds, q["q2_scenarios"], carbon, assumptions))
    sizes["coast"] = dump("coast", coastline())
    ai = {"summary": load(RESULTS / "ai" / "evaluation_summary.json"), "runs": [], "insights": []}
    for f in sorted((RESULTS / "ai").glob("analyst_*.json")):
        r = load(f)
        ai["runs"].append({"model": r["model"], "label": r["label"], "items": [
            {k: i[k] for k in ("id", "split", "question", "type", "gold", "answer", "correct", "text", "sql", "steps", "latency_s", "error")}
            for i in r["items"]]})
    for f in sorted((RESULTS / "ai").glob("insights_*.json")):
        ai["insights"].append(load(f))
    sizes["ai"] = dump("ai", ai)
    sizes["powerbi"] = dump("powerbi", powerbi())
    sizes["build"] = dump("build", {"sources": SOURCES, "lineage": lineage(), "fabric": FABRIC, "status": meta["status"], "rules": rules})
    print({k: f"{v / 1024:.0f} KB" for k, v in sizes.items()})
    return sizes
