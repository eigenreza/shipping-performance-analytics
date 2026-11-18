"""The warehouse built from synthetic fixtures gives hand-computed answers."""

from __future__ import annotations

import pytest


def test_port_calls_detected_with_waiting(fixture_warehouse):
    rows = fixture_warehouse.sql("""
        select port_key, waiting_hours, berth_hours, is_kystverket_matched
        from marts.fct_port_call order by ship_key, berth_start_utc""").fetchall()
    # Two fixture ships, each: berth at Alpha (no wait), then 3 h at anchor and 8 h at berth in Bravo.
    assert [r[0] for r in rows] == ["NOAAA", "NOBBB", "NOAAA", "NOBBB"]
    assert [r[1] for r in rows] == pytest.approx([0, 3, 0, 3])
    assert [r[2] for r in rows] == pytest.approx([6, 8, 6, 8])
    # Only one of the calls has a Kystverket record in the fixtures.
    assert sum(r[3] for r in rows) == 1


def test_voyage_legs_have_weather(fixture_warehouse):
    legs = fixture_warehouse.sql("select sailed_nm, avg_wind_ms, avg_wave_m from marts.fct_voyage_leg").fetchall()
    assert len(legs) == 2
    for nm, wind, wave in legs:
        assert nm > 100
        assert wind == pytest.approx(6.0)
        assert wave == pytest.approx(1.2)


def test_cii_matches_hand_calculation(fixture_warehouse):
    # Vehicle carrier with reported GT 58,000: above 57,700 GT the capacity in the reference line is capped at 57,700.
    co2, dist, gt, attained, required, rating = fixture_warehouse.sql("""
        select f.co2_t, f.distance_nm, f.gross_tonnage, f.cii_attained, f.cii_required, f.cii_rating
        from marts.fct_ship_year_emissions f where f.reporting_year = 2025 and f.gross_tonnage = 58000""").fetchall()[0]
    assert attained == pytest.approx(co2 * 1e6 / (gt * dist))
    reference = 3627 * 57700 ** -0.590
    assert required == pytest.approx(reference * (1 - 0.09))
    ratio = attained / required
    expected = "A" if ratio < 0.86 else "B" if ratio < 0.94 else "C" if ratio < 1.06 else "D" if ratio < 1.16 else "E"
    assert rating == expected


def test_cii_small_vehicle_carrier_uses_lower_band(fixture_warehouse):
    gt, required = fixture_warehouse.sql("""
        select f.gross_tonnage, f.cii_required from marts.fct_ship_year_emissions f
        where f.reporting_year = 2025 and f.gross_tonnage = 20000""").fetchall()[0]
    assert required == pytest.approx(330 * gt ** -0.329 * (1 - 0.09))


def test_eu_ets_scope_and_phase_in(fixture_warehouse):
    rows = fixture_warehouse.sql("""
        select reporting_year, co2_t, co2_ets_scope_t, ets_surrender_share, eua_due_t, ets_cost_eur, eua_avg_eur
        from marts.fct_ship_year_emissions""").fetchall()
    for year, co2, scope, share, due, cost, price in rows:
        # Fixture split: 50% intra-EEA, 10% at berth, 20% departing, 20% arriving -> 0.5 + 0.1 + 0.5 * 0.4 = 0.8
        assert scope == pytest.approx(0.8 * co2)
        assert share == {2019: 0.0, 2023: 0.0, 2024: 0.4, 2025: 0.7}[year]
        assert due == pytest.approx(scope * share)
        assert cost == pytest.approx(due * price)


def test_no_fixture_identifier_reaches_marts(fixture_warehouse):
    cols = fixture_warehouse.sql("""
        select table_name, column_name from information_schema.columns where table_schema = 'marts'""").fetchall()
    names = {c for _, c in cols}
    assert not names & {"imo_number", "mmsi", "ship_name", "name", "ais_name"}
    pseudonyms = [r[0] for r in fixture_warehouse.sql("select ship_pseudonym from marts.dim_ship").fetchall()]
    assert all(p.startswith(("Carrier ", "Ro-ro ")) for p in pseudonyms)
    assert "FIXTURE TANKER" not in str(fixture_warehouse.sql("select * from marts.dim_ship").fetchall())


def test_tonnage_estimate_and_plausibility(fixture_warehouse):
    rows = dict(fixture_warehouse.sql("""
        select tonnage_method, count(*) from intermediate.int_ship_capacity group by 1""").fetchall())
    assert rows.get("Reported (Kystverket port calls)", 0) == 5
    assert rows.get("Estimated from AIS length and beam", 0) == 2
