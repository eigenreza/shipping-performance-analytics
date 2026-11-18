"""Checks on everything that is published: hygiene, privacy, generated docs, demo."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from spa import docs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def test_hygiene_scan_is_clean():
    import hygiene

    res = hygiene.run()
    assert res["fails"] == [], "\n".join(res["fails"][:20])


def test_gold_tables_are_pseudonymous():
    gold = ROOT / "data" / "exports" / "gold"
    files = list(gold.glob("*.parquet"))
    if not files:
        pytest.skip("gold export not present")
    for f in files:
        cols = set(pq.read_schema(f).names)
        assert not cols & {"imo_number", "mmsi", "ship_name", "name", "call_sign", "imoNumber"}, f.name
    ships = pq.read_table(gold / "dim_ship.parquet").column("ship_pseudonym").to_pylist()
    assert all(re.fullmatch(r"(Carrier|Ro-ro) \d{3}", s) for s in ships)


def test_demo_data_is_pseudonymous_and_dated_within_range():
    data = ROOT / "demo" / "frontend" / "public" / "data"
    if not data.exists():
        pytest.skip("demo data not exported")
    fleet = json.loads((data / "fleet.json").read_text(encoding="utf-8"))
    i = fleet["columns"].index("ship")
    assert all(re.fullmatch(r"(Carrier|Ro-ro) \d{3}", r[i]) for r in fleet["rows"])
    ports = json.loads((data / "ports.json").read_text(encoding="utf-8"))
    assert max(c["day"] for c in ports["calls"]) <= "2026-09-30"


def test_readme_and_measure_docs_are_current():
    assert docs.check() == []


def test_no_dates_or_timestamps_in_result_files():
    for f in (ROOT / "results").rglob("*.json"):
        if "calls" in f.parts:
            continue
        text = f.read_text(encoding="utf-8-sig")
        assert not re.search(r"\b20\d\d-\d\d-\d\dT\d\d:\d\d", text) or f.name.startswith(("analyst_", "insights_")), f.name
        assert not re.search(r"generated_at|run_at|timestamp", text, re.I), f.name


def test_demo_server_serves_pages_and_data():
    from fastapi.testclient import TestClient

    from demo.backend.app import DIST, app

    if not (DIST / "index.html").exists():
        pytest.skip("demo front end not built")
    c = TestClient(app)
    assert c.get("/health").json()["status"] == "ok"
    index = c.get("/")
    assert index.status_code == 200 and "Shipping performance analytics" in index.text
    assert c.get("/#/ports").status_code == 200
    assert c.get("/data/meta.json").json()["author"] == "Reza Azad Gholami"
    assert c.get("/some/deep/link").status_code == 200  # single-page app fallback


def test_demo_simulator_matches_the_analysis():
    """The browser simulator uses the same data and formulas as the Q2 scenarios and the dbt CII ratings."""
    data = ROOT / "demo" / "frontend" / "public" / "data"
    if not (data / "simulator.json").exists():
        pytest.skip("demo data not exported")
    sim = json.loads((data / "simulator.json").read_text(encoding="utf-8"))
    q2 = json.loads((data / "analysis.json").read_text(encoding="utf-8"))["q2_scenarios"]
    ships = sim["ships"]
    assert len(ships) == q2["ships"]
    co2 = sum(s[1] for s in ships)
    assert co2 == pytest.approx(q2["co2_t"], rel=1e-4)
    for key, b in (("mrv_estimate", sim["elasticity"]["data"]), ("engineering", sim["elasticity"]["engineering"])):
        ten = next(s for s in q2["relations"][key]["scenarios"] if abs(s["speed_change"] + 0.1) < 1e-9)
        assert co2 * (1 - 0.9 ** b) == pytest.approx(ten["co2_saved_t"], rel=1e-3)
        days = sum(s[3] for s in ships) * (1 / 0.9 - 1) / 24 / len(ships)
        assert days == pytest.approx(ten["extra_days_per_ship"], abs=0.05)

    # Ratings recomputed from the ratio in the base year equal the warehouse letters.
    fleet = json.loads((data / "fleet.json").read_text(encoding="utf-8"))
    col = {c: i for i, c in enumerate(fleet["columns"])}
    letters = sorted(r[col["cii"]] for r in fleet["rows"]
                     if r[col["year"]] == sim["base_year"] and r[col["ok"]] and r[col["cii"]])

    def letter(ratio, bounds):
        return "ABCDE"[next((i for i, b in enumerate(bounds) if ratio < b), 4)]

    again = sorted(letter(s[5] / 1e6, sim["cii_bounds"][s[0]]) for s in ships if s[5] is not None)
    assert again == letters
