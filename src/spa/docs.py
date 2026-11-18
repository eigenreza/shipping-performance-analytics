"""Generated documentation.

* docs/measures.md is generated from the TMDL files of the semantic model:
  every measure with its display folder, format, description and DAX.
* README.md tables between <!-- BEGIN:name --> and <!-- END:name --> markers
  are generated from result files, so no number in the README is typed by
  hand. ``check()`` fails when the README is out of date (used in CI).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from spa.paths import RESULTS, ROOT

TMDL = ROOT / "powerbi" / "ShippingPerformance.SemanticModel" / "definition" / "tables"
README = ROOT / "README.md"


# ------------------------------------------------------------------ TMDL parsing
def parse_measures(folder: Path = TMDL) -> list[dict]:
    """Measures from TMDL: name, table, description, DAX, format string, display folder."""
    out = []
    for f in sorted(folder.glob("*.tmdl")):
        lines = f.read_text(encoding="utf-8").splitlines()
        table = None
        desc: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("table "):
                table = line[6:].strip().strip("'")
            stripped = line.strip()
            if stripped.startswith("///"):
                desc.append(stripped[3:].strip())
                i += 1
                continue
            m = re.match(r"^\tmeasure ('(?:[^']|'')+'|\S+)\s*=\s*(.*)$", line)
            if m:
                name = m.group(1).strip("'").replace("''", "'")
                expr = [m.group(2)] if m.group(2).strip() else []
                props = {}
                i += 1
                while i < len(lines) and (lines[i].startswith("\t\t") or not lines[i].strip()):
                    body = lines[i]
                    if body.startswith("\t\t\t") and not props:
                        expr.append(body.strip())
                    elif body.startswith("\t\t") and ":" in body and not body.startswith("\t\t\t"):
                        k, v = body.strip().split(":", 1)
                        props[k.strip()] = v.strip()
                    elif body.strip().startswith("annotation"):
                        pass
                    i += 1
                out.append({"table": table, "name": name, "description": " ".join(desc), "dax": "\n".join(e for e in expr if e).strip(),
                            "format": props.get("formatString", ""), "folder": props.get("displayFolder", "")})
                desc = []
                continue
            if stripped and not stripped.startswith("///"):
                desc = []
            i += 1
    return out


def measures_md() -> str:
    ms = parse_measures()
    folders: dict[str, list[dict]] = {}
    for m in ms:
        folders.setdefault(m["folder"] or "Other", []).append(m)
    lines = [
        "# Measure catalogue",
        "",
        "Generated from the semantic model's TMDL files by `spa docs`. Do not edit by hand.",
        "",
        f"{len(ms)} measures in {len(folders)} display folders. DAX is the formula language of Power BI.",
        "",
    ]
    for folder in sorted(folders):
        lines += [f"## {folder}", ""]
        for m in folders[folder]:
            lines += [f"### {m['name']}", "", m["description"] or "(no description)", "",
                      f"Table: `{m['table']}`" + (f". Format: `{m['format']}`" if m["format"] else ""), "",
                      "```dax", m["dax"], "```", ""]
    return "\n".join(lines)


# ------------------------------------------------------------------ README tables
def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else None


def _n(v, d=0):
    return f"{v:,.{d}f}" if isinstance(v, (int, float)) else "n/a"


def _p(v, d=1):
    return f"{v * 100:.{d}f}%" if isinstance(v, (int, float)) else "n/a"


def tables() -> dict[str, str]:
    a = RESULTS / "analysis"
    q1, q2, q3, q4, q5 = (_load(a / f"{n}.json") for n in ("q1_drivers", "q2_scenarios", "q3_ratings", "q4_ports_weather", "q5_deviations"))
    out = {}
    if q1 and q2 and q3 and q4 and q5:
        ten = {k: next(s for s in v["scenarios"] if abs(s["speed_change"] + 0.1) < 1e-9) for k, v in q2["relations"].items()}
        bands = q4["speed_by_wind"] + q4["speed_by_waves"]
        spread = max(b["speed_change"] for b in bands) - min(b["speed_change"] for b in bands)
        c = q1["cross_sectional"]
        rows = [
            ("What drives fuel efficiency differences?",
             f"Size first: doubling gross tonnage goes with {_n(q1['size_effect_doubling_gt_pct'], 1)}% more CO2 per nautical mile; "
             f"the newer EEDI design generation emits {_n(abs(q1['eedi_generation_effect_pct']), 1)}% less. Annual data show a weak speed "
             f"effect (exponent {_n(c['log_speed']['estimate'], 2)}, 95% interval {_n(c['log_speed']['low'], 2)} to {_n(c['log_speed']['high'], 2)})."),
            ("What would slower steaming save?",
             f"At 10% slower: {_p(ten['mrv_estimate']['co2_saved_share'])} less CO2 on the estimate from MRV data, "
             f"{_p(ten['engineering']['co2_saved_share'])} on the engineering rule, for about {_n(ten['engineering']['extra_days_per_ship'], 1)} "
             f"extra days at sea per ship per year ({q2['base_year']}, {_n(q2['ships'])} ships)."),
            ("Which ships drift toward poor carbon ratings?",
             f"{_p(q3['share_d_or_e_latest'])} of rated ship-years were D or E in {q3['latest_year']} "
             f"(95% interval {_p(q3['share_d_or_e_latest_interval'][0])} to {_p(q3['share_d_or_e_latest_interval'][1])}); "
             f"{_n(q3['ships_worse_than_first_year'])} of {_n(q3['ships_compared'])} ships rated worse than in {q3['first_official_year']}."),
            ("How much time is lost waiting at Norwegian ports?",
             f"Little: {_p(q4['share_with_waiting'])} of {_n(q4['calls'])} calls waited at anchor; median {_n(q4['median_berth_h'], 1)} h at berth. "
             f"Wind and waves change leg speed by at most {_p(spread)}, with overlapping intervals."),
            ("Which ship-years deviate from what speed, size and age predict?",
             f"{_n(q5['flagged'])} of {_n(q5['ship_years_tested'])} ship-years ({_n(q5['flagged_above'])} above, "
             f"{_n(q5['flagged_below'])} below expectation), as candidates for review."),
        ]
        out["answers"] = "| Question | Short answer |\n|---|---|\n" + "\n".join(f"| {q} | {t} |" for q, t in rows)
    ai = _load(RESULTS / "ai" / "evaluation_summary.json")
    if ai:
        lines = ["| Model | Test accuracy (95% interval) | Dev accuracy | Median seconds per question | Insight findings fully supported |", "|---|---|---|---|---|"]
        ins = {i["model"]: i for i in ai["insights"]}
        for s in sorted(ai["analyst"], key=lambda x: -(x["test"]["accuracy"] or 0)):
            t = s["test"]
            lines.append(f"| {s['label']} | {_p(t['accuracy'], 0)} ({_p(t['low'], 0)} to {_p(t['high'], 0)}), {t['correct']}/{t['answered']} | "
                         f"{_p(s['dev']['accuracy'], 0)} | {_n(s.get('median_latency_s'), 1)} | {_p(ins.get(s['model'], {}).get('share_supported'), 0)} |")
        out["ai"] = "\n".join(lines)
    meta = _load(ROOT / "demo" / "frontend" / "public" / "data" / "meta.json")
    rec = _load(RESULTS / "powerbi" / "reconciliation.json")
    bpa = _load(RESULTS / "powerbi" / "bpa.json")
    if meta:
        c = meta["counts"]
        out["data"] = "\n".join([
            "| Data | Volume |", "|---|---|",
            f"| EU MRV ship-year reports (ro-ro ships and vehicle carriers, 2018 to 2025) | {_n(c['ship_years'])} reports, {_n(c['ships'])} ships |",
            f"| AIS positions on the Norwegian coast (5 August to 30 September 2026) | {_n(c['ais_positions'])} positions, {_n(c['ais_ships'])} ships |",
            f"| AIS-derived port calls and voyage legs | {_n(c['port_calls'])} calls, {_n(c['voyage_legs'])} legs |",
            f"| Data snapshot (content hash of the gold tables) | `{meta['snapshot']}` |",
        ])
    if rec and bpa:
        s = rec["summary"]
        out["quality"] = "\n".join([
            "| Check | Result |", "|---|---|",
            f"| DAX measures that evaluate without error | {s['measures_without_error']} of {s['measures_evaluated']} |",
            f"| Key measures equal to SQL (relative tolerance {s['tolerance']:g}) | {s['reconciliation_matches']} of {s['reconciliation_checks']} |",
            f"| Row-level security roles tested in the engine | {s['rls_roles_passed']} of {s['rls_roles']} |",
            f"| Best Practice Analyzer findings ({bpa['rules_checked']} rules) | {bpa['findings']} |",
        ])
    return out



NL = "\n"


def md_table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return NL.join(lines)


def seed_table(name: str, columns: list[tuple[str, str]]) -> str:
    import csv

    with (ROOT / "dbt" / "seeds" / f"{name}.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return md_table([h for _, h in columns], [[r[c] or "" for c, _ in columns] for r in rows])


def more_tables() -> dict[str, str]:
    a = RESULTS / "analysis"
    out = {
        "cii_reference": seed_table("cii_reference_lines", [("segment", "Segment"), ("capacity_measure", "Capacity"), ("capacity_min", "From"),
                                                            ("capacity_max", "Below"), ("capacity_cap", "Capacity cap"), ("a", "a"), ("c", "c"),
                                                            ("source", "Source")]),
        "cii_reduction": seed_table("cii_reduction_factors", [("rating_year", "Year"), ("reduction_factor", "Reduction factor Z"), ("source", "Source")]),
        "cii_boundaries": seed_table("cii_rating_boundaries", [("segment", "Segment"), ("d1", "exp(d1)"), ("d2", "exp(d2)"), ("d3", "exp(d3)"),
                                                               ("d4", "exp(d4)"), ("source", "Source")]),
        "ets_phase_in": seed_table("eu_ets_phase_in", [("emission_year", "Emission year"), ("surrender_share", "Share surrendered"),
                                                       ("gases", "Gases"), ("source_article", "Source")]),
        "ets_scope": seed_table("eu_ets_scope_rules", [("voyage_scope", "Emissions"), ("emission_share", "Share counted"), ("source_article", "Source")]),
    }
    q1, q2, q3, q4, q5 = (_load(a / f"{n}.json") for n in ("q1_drivers", "q2_scenarios", "q3_ratings", "q4_ports_weather", "q5_deviations"))
    if q1:
        labels = {"log_speed": "log(speed)", "log_gt": "log(gross tonnage)", "eedi_generation": "EEDI design generation",
                  "vehicle_carrier": "Vehicle carrier (against ro-ro)"}
        rows = [[labels[k], _n(v["estimate"], 3), f"{_n(v['low'], 3)} to {_n(v['high'], 3)}"] for k, v in q1["cross_sectional"].items()]
        w = q1["speed_elasticity_within"]
        rows.append(["log(speed), same ship over years (ship and year fixed effects)", _n(w["estimate"], 3), f"{_n(w['low'], 3)} to {_n(w['high'], 3)}"])
        out["q1"] = (md_table(["Term (outcome: log CO2 per nautical mile)", "Estimate", "95% bootstrap interval"], rows) + NL + NL
                     + f"{_n(q1['ship_years'])} quality-checked ship-years of {_n(q1['ships'])} ships; R squared {_n(q1['cross_sectional_r2'], 3)}.")
    if q2:
        rows = []
        for key, rel in q2["relations"].items():
            for sc in rel["scenarios"]:
                band = f" ({_p(sc['co2_saved_share_low'])} to {_p(sc['co2_saved_share_high'])})" if key == "mrv_estimate" else ""
                rows.append([rel["label"], _p(sc["speed_change"], 0), _p(sc["co2_saved_share"]) + band, _n(sc["co2_saved_t"]),
                             _n(sc["fuel_cost_saved_eur"]), _n(sc["ets_cost_saved_eur"]), _n(sc["extra_days_per_ship"], 1)])
        out["q2"] = (md_table(["Speed relation", "Speed change", "CO2 saved", "CO2 saved (t)", "Fuel cost saved (EUR)", "EU ETS cost saved (EUR)",
                               "Extra days per ship"], rows) + NL + NL
                     + f"Base: {_n(q2['ships'])} ships in {q2['base_year']}; fuel price EUR {_n(q2['fuel_price_eur_per_t'])} per tonne; "
                     + f"carbon price EUR {_n(q2['carbon_price_eur_per_t'], 2)} per tonne ({q2['carbon_price_basis']}).")
    if q3:
        out["q3"] = md_table(["Year", "Segment", "Rated ship-years", "Rated D or E (95% interval)"],
                             [[str(r["year"]), r["segment"], _n(r["rated"]), f"{_p(r['share_d_or_e'])} ({_p(r['low'])} to {_p(r['high'])})"]
                              for r in q3["by_year_segment"]])
    if q4:
        out["q4_ports"] = md_table(["Port", "Calls", "Calls with waiting", "Median hours at berth", "90th percentile hours at berth"],
                                   [[p["port"], _n(p["calls"]), _p(p["share_with_waiting"]), _n(p["median_berth_h"], 1), _n(p["p90_berth_h"], 1)]
                                    for p in q4["ports"][:12]])
        out["q4_weather"] = md_table(["Wind or wave band", "Voyage legs", "Speed against calm (95% interval)"],
                                     [[b["band"], _n(b["legs"]), f"{_p(b['speed_change'], 1)} ({_p(b['low'], 1)} to {_p(b['high'], 1)})"]
                                      for b in q4["speed_by_wind"] + q4["speed_by_waves"]])
    if q5:
        out["q5"] = md_table(["Ship", "Year", "Segment", "CO2 per nm (kg)", "Speed (kn)", "Above expectation"],
                             [[i["ship"], str(i["year"]), i["segment"], _n(i["co2_kg_per_nm"], 1), _n(i["speed_kn"], 1),
                               f"{_n(i['excess_vs_expected_pct'], 0)}%"] for i in q5["items"][:10]])
    return out


def render_readme(text: str) -> str:
    for name, body in {**tables(), **more_tables()}.items():
        text = re.sub(rf"(<!-- BEGIN:{name} -->).*?(<!-- END:{name} -->)",
                      lambda m, body=body: m.group(1) + NL + body + NL + m.group(2), text, flags=re.S)
    return text


def marked_files() -> list[Path]:
    return [README, *sorted((ROOT / "docs").glob("*.md"))]


def write() -> None:
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "measures.md").write_text(measures_md(), encoding="utf-8")
    for f in marked_files():
        if f.exists() and f.name != "measures.md":
            f.write_text(render_readme(f.read_text(encoding="utf-8")), encoding="utf-8")


def check() -> list[str]:
    problems = []
    for f in marked_files():
        if f.exists() and f.name != "measures.md":
            cur = f.read_text(encoding="utf-8")
            if render_readme(cur) != cur:
                problems.append(f"{f.relative_to(ROOT)}: generated tables are out of date: run `spa docs`")
    md = ROOT / "docs" / "measures.md"
    if md.exists() and md.read_text(encoding="utf-8") != measures_md():
        problems.append("docs/measures.md is out of date: run `spa docs`")
    return problems
