"""Rule tables, scenario arithmetic and the source parsers."""

from __future__ import annotations

import csv
from pathlib import Path

import openpyxl
import pytest

from spa.analysis.scenario import ets_cost_saved, extra_days, saved_share
from spa.ingest import carbon, mrv

SEEDS = Path(__file__).resolve().parents[1] / "dbt" / "seeds"


def read(name):
    with (SEEDS / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_eu_ets_phase_in_matches_directive():
    shares = {int(r["emission_year"]): float(r["surrender_share"]) for r in read("eu_ets_phase_in.csv")}
    assert shares[2024] == 0.40 and shares[2025] == 0.70 and shares[2026] == 1.0
    assert all(0 <= v <= 1 for v in shares.values())


def test_eu_ets_scope_rules():
    rules = {r["voyage_scope"]: float(r["emission_share"]) for r in read("eu_ets_scope_rules.csv")}
    assert rules["between_eea_ports"] == 1.0 and rules["at_berth_in_eea_port"] == 1.0
    assert rules["departing_eea_to_non_eea"] == 0.5 and rules["arriving_eea_from_non_eea"] == 0.5


def test_cii_tables_match_imo_guidelines():
    ref = read("cii_reference_lines.csv")
    vc = [r for r in ref if r["segment"] == "Vehicle carrier"]
    assert {(r["a"], r["c"]) for r in vc} == {("3627", "0.590"), ("330", "0.329")}
    roro = [r for r in ref if r["segment"] == "Ro-ro ship"][0]
    assert (roro["a"], roro["c"], roro["capacity_measure"]) == ("1967", "0.485", "GT")
    z = {int(r["rating_year"]): float(r["reduction_factor"]) for r in read("cii_reduction_factors.csv")}
    assert (z[2023], z[2024], z[2025], z[2026]) == (0.05, 0.07, 0.09, 0.11)
    assert z[2030] == pytest.approx(0.215)
    dd = {r["segment"]: [float(r[k]) for k in ("d1", "d2", "d3", "d4")] for r in read("cii_rating_boundaries.csv")}
    assert dd["Vehicle carrier"] == [0.86, 0.94, 1.06, 1.16]
    assert dd["Ro-ro ship"] == [0.76, 0.89, 1.08, 1.27]


def test_scenario_arithmetic():
    assert saved_share(-0.10, 2.0) == pytest.approx(0.19)
    assert saved_share(0.0, 2.0) == 0
    assert saved_share(-0.10, 0.0) == 0
    assert extra_days(24 * 100, -0.20) == pytest.approx(25.0)
    assert ets_cost_saved(1000, 0.8, 75) == pytest.approx(60000)
    with pytest.raises(ValueError):
        saved_share(-1.0, 2.0)


def test_mrv_parser(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Ship", None, None, None, "Monitoring methods", None, "Annual monitoring results", None, None])
    ws.append([None, None, None, None, None, None, "Totals", None, "Average energy efficiency on Laden Voyages"])
    ws.append(["IMO Number", "Name", "Ship type", "Reporting Period", "A", "A", "Total CO₂ emissions [m tonnes]",
               "Annual average CO₂ emissions per distance [kg CO₂ / n mile]", "CO₂ emissions per distance on laden voyages [kg CO₂ / n mile]"])
    ws.append(["1000010", "X", "Vehicle carrier", 2024, "Yes", None, "1,000", 300.5, "N/A"])
    ws.append([None, None, None, None, None, None, None, None, None])
    path = tmp_path / "mrv.xlsx"
    wb.save(path)
    df = mrv.parse_workbook(path)
    assert len(df) == 1
    assert "total_co2_emissions" in df.columns
    assert "annual_average_co2_emissions_per_distance" in df.columns
    assert "monitoring_method_a" in df.columns and "monitoring_method_a_2" in df.columns
    assert df["imo_number"].iloc[0] == "1000010"
    assert df["co2_emissions_per_distance_on_laden_voyages"].isna().all()


def test_carbon_chart_parser():
    html = ('<script>var _Flourish_data = {"data":[{"label":"2026-09-29","metadata":["29 Sep 2026","€/t"],"value":["80.1"]},'
            '{"label":"2026-09-30","metadata":["30 Sep 2026","€/t"],"value":[""]}]},\n_other = 1</script>')
    df = carbon.parse_chart(html)
    assert len(df) == 1 and df["eua_price_eur"].iloc[0] == 80.1
