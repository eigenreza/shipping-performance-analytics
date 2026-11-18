"""Write small synthetic raw files for CI and tests (tests/fixtures/raw).

The files have the same layout as the real raw layer but invented ships,
identifiers and values, so the full dbt build runs in CI without any
download. One ship has a scripted voyage (berth, anchorage wait, berth) so
the port call detection can be tested against a known answer.

Identifiers are deliberately invalid (IMO numbers fail the IMO check digit,
MMSI numbers use an unassigned country code).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "raw"

SHIPS = [
    # imo, name, type, mmsi, length, beam, gt (reported or None)
    ("1000010", "FIXTURE ALPHA", "Vehicle carrier", 100000011, 200, 32, 58000),
    ("1000020", "FIXTURE BRAVO", "Vehicle carrier", 100000012, 180, 32, 45000),
    ("1000030", "FIXTURE CHARLIE", "Vehicle carrier", 100000013, 140, 22, 20000),
    ("1000040", "FIXTURE DELTA", "Vehicle carrier", 100000014, 228, 32, None),
    ("1000050", "FIXTURE ECHO", "Ro-ro ship", 100000015, 190, 26, 25000),
    ("1000060", "FIXTURE FOXTROT", "Ro-ro ship", 100000016, 150, 23, 12000),
    ("1000070", "FIXTURE GOLF", "Ro-ro ship", 100000017, 120, 20, None),
]

# MRV layouts by reporting year: (time at sea column, per-distance prefix, extra columns)
FORMATS = {
    2019: {"time": ["annual_total_time_spent_at_sea", "total_time_spent_at_sea"], "fpd": "annual_average_fuel_consumption_per_distance",
           "cpd": "annual_average_co2_emissions_per_distance", "ctw": "annual_average_co2_emissions_per_transport_work_mass", "ets": False},
    2023: {"time": ["annual_time_spent_at_sea", "time_spent_at_sea"], "fpd": "annual_average_fuel_consumption_per_distance",
           "cpd": "annual_average_co2_emissions_per_distance", "ctw": "annual_average_co2_emissions_per_transport_work_mass", "ets": False},
    2024: {"time": ["time_spent_at_sea"], "fpd": "fuel_consumption_per_distance", "cpd": "co2_emissions_per_distance",
           "ctw": "co2_emissions_per_transport_work_mass", "ets": True},
    2025: {"time": ["time_spent_at_sea"], "fpd": "fuel_consumption_per_distance", "cpd": "co2_emissions_per_distance",
           "ctw": "co2_emissions_per_transport_work_mass", "ets": True},
}


def mrv() -> None:
    for year, fmt in FORMATS.items():
        rows = []
        for k, (imo, name, typ, *_rest) in enumerate(SHIPS):
            distance = 40000 + 3000 * k + (year - 2019) * 200
            hours = distance / (14 + k * 0.3)
            fuel = distance * (110 + 8 * k) / 1000
            co2 = fuel * 3.114
            r = {
                "imo_number": imo, "name": name, "ship_type": typ, "reporting_period": float(year),
                "technical_efficiency": "EEDI (9.5 gCO₂/t·nm)" if k % 2 == 0 else "EIV (14.2 gCO₂/t·nm)",
                "port_of_registry": "OSLO" if k < 3 else "PANAMA", "ice_class": None,
                "total_fuel_consumption": fuel, "total_co2_emissions": co2,
                "co2_emissions_from_all_voyages_between_ports_under_a_ms_jurisdiction": co2 * 0.5,
                "co2_emissions_from_all_voyages_which_departed_from_ports_under_a_ms_jurisdiction": co2 * 0.2,
                "co2_emissions_from_all_voyages_to_ports_under_a_ms_jurisdiction": co2 * 0.2,
                "co2_emissions_which_occurred_within_ports_under_a_ms_jurisdiction_at_berth": co2 * 0.1,
                fmt["fpd"]: fuel * 1000 / distance, fmt["cpd"]: co2 * 1000 / distance,
                fmt["ctw"]: co2 * 1e6 / (distance * 9000),
                "source_version": 1,
            }
            for c in fmt["time"]:
                r[c] = hours
            if fmt["ets"]:
                r["co2_emissions_to_be_reported_under_directive_2003_87_ec"] = co2 * 0.7
            rows.append(r)
        # an unrelated ship type that staging must filter out
        rows.append({**rows[0], "imo_number": "1000990", "name": "FIXTURE TANKER", "ship_type": "Oil tanker"})
        pd.DataFrame(rows).to_parquet(OUT / "mrv" / f"mrv_{year}.parquet", index=False)


def carbon() -> None:
    days = pd.date_range("2019-01-01", "2026-09-30", freq="D")
    price = 25 + 60 * (np.arange(len(days)) / len(days))
    pd.DataFrame({"price_date": days.date, "eua_price_eur": price.round(2), "source": "fixture"}).to_parquet(OUT / "carbon" / "eua_daily.parquet", index=False)


def static() -> None:
    rows = [{"mmsi": mmsi, "msgType": 5, "aisClass": "A", "imoNumber": float(imo), "callSign": None, "name": name, "shipType": 70,
             "dimensionToBow": length - 20, "dimensionToStern": 20, "dimensionToPort": beam // 2, "dimensionToStarboard": beam - beam // 2,
             "draught": 9.0, "validFrom": "2020-01-01T00:00:00", "validTo": None, "truncated_source": False}
            for imo, name, _t, mmsi, length, beam, _gt in SHIPS]
    pd.DataFrame(rows).to_parquet(OUT / "ais" / "static_fleet.parquet", index=False)


PORT_A = (59.70, 10.25)  # fixture port "Alpha Havn"
PORT_B = (60.39, 5.32)   # fixture port "Bravo Havn"
ANCHOR_B = (60.36, 5.20)


def track(mmsi: int, start: datetime) -> list[dict]:
    """Berth at A for 6 h, sail to B's anchorage, wait 3 h, berth at B for 8 h, then leave."""
    pts = []

    def add(t, lat, lon, sog):
        pts.append({"mmsi": mmsi, "ts": t, "lon": lon, "lat": lat, "cog": 270.0, "sog": sog, "calc_speed": sog,
                    "sec_prevpoint": 120, "dist_prevpoint": 0.0, "true_heading": 270, "rot": None})

    t = start
    # At berth: sparse vertices (simplified track), as in the real data
    for h in (0, 3, 6):
        add(t + timedelta(hours=h), PORT_A[0], PORT_A[1], 0.0)
    t += timedelta(hours=6)
    # Sail A -> anchorage, 12 knots, every 2 minutes
    steps = 180
    for i in range(1, steps + 1):
        f = i / steps
        add(t + timedelta(minutes=2 * i), PORT_A[0] + (ANCHOR_B[0] - PORT_A[0]) * f, PORT_A[1] + (ANCHOR_B[1] - PORT_A[1]) * f, 12.0)
    t += timedelta(minutes=2 * steps)
    # Waiting at anchor: 3 hours
    for h in (1, 2, 3):
        add(t + timedelta(hours=h), ANCHOR_B[0], ANCHOR_B[1], 0.1)
    t += timedelta(hours=3)
    # Short approach to the berth
    for i in range(1, 16):
        f = i / 15
        add(t + timedelta(minutes=2 * i), ANCHOR_B[0] + (PORT_B[0] - ANCHOR_B[0]) * f, ANCHOR_B[1] + (PORT_B[1] - ANCHOR_B[1]) * f, 6.0)
    t += timedelta(minutes=30)
    # Berth at B for 8 hours
    for h in (0, 4, 8):
        add(t + timedelta(hours=h), PORT_B[0], PORT_B[1], 0.0)
    t += timedelta(hours=8)
    for i in range(1, 30):
        add(t + timedelta(minutes=2 * i), PORT_B[0] - 0.01 * i, PORT_B[1] - 0.02 * i, 11.0)
    return pts


def positions() -> None:
    pts = track(100000011, datetime(2026, 9, 26, 6, 0)) + track(100000015, datetime(2026, 9, 24, 2, 0))
    df = pd.DataFrame(pts)
    df["ts"] = pd.to_datetime(df["ts"])
    df.to_parquet(OUT / "ais" / "positions" / "b000_fixture.parquet", index=False)


def port_calls_and_tonnage() -> None:
    calls = [
        {"id": 1, "shipid": 501, "shipname": "FIXTURE ALPHA", "shiptype": "Vehicles Carrier", "shipcategory": "x", "gt": 58000, "dwt": 20000,
         "locationid": 2, "name": "Bravo Havn", "type": "Havn", "country": "NO", "county": "46", "council": "4601",
         "eta": "2026-09-26T22:40:00+02:00", "etd": "2026-09-27T07:00:00+02:00", "tinterval": "", "hours": 8.3, "query_day": "2026-09-26"},
    ]
    pd.DataFrame(calls).to_parquet(OUT / "ais" / "port_calls" / "2026-09-26.parquet", index=False)
    ton = [{"shipname": name, "shiptype": "Vehicles Carrier" if t == "Vehicle carrier" else "Ro-Ro Cargo Ship", "gt": gt, "dwt": None}
           for _i, name, t, _m, _l, _b, gt in SHIPS if gt]
    pd.DataFrame(ton).to_parquet(OUT / "ais" / "tonnage_calibration.parquet", index=False)


def locations() -> None:
    rows = [
        (1, "NOAAA", "Alpha Havn", "HARBOUR", PORT_A),
        (3, "NOAAA", "Alpha kai", "QUAY", (PORT_A[0] + 0.001, PORT_A[1])),
        (2, "NOBBB", "Bravo Havn", "HARBOUR", PORT_B),
        (4, "NOBBB", "Bravo terminal", "PORT_FACILITY", (PORT_B[0], PORT_B[1] + 0.002)),
        (5, "NOBBB", "Bravo ankring", "ANCHORAGE", ANCHOR_B),
    ]
    df = pd.DataFrame([{"locationid": i, "locationcode": c, "locationnamenor": n, "isactive": False, "locationtypenor": "x",
                        "systemname": s, "countyname": "Fixture", "lat": p[0], "lon": p[1]} for i, c, n, s, p in rows])
    df.to_parquet(OUT / "ports" / "kystverket_locations.parquet", index=False)


def weather() -> None:
    hours = pd.date_range("2026-09-20", "2026-09-30 23:00", freq="h")
    cells = [(lat, lon) for lat in np.arange(59.5, 60.6, 0.25) for lon in np.arange(5.0, 10.6, 0.25)]
    wind = pd.DataFrame([{"hour_utc": h, "wind_speed_10m": 6.0, "wind_direction_10m": 250.0, "wind_gusts_10m": 9.0,
                          "cell_lat": round(la, 2), "cell_lon": round(lo, 2), "dataset": "wind", "grid_deg": 0.25}
                         for la, lo in cells for h in hours])
    wind.to_parquet(OUT / "weather" / "wind_00000.parquet", index=False)
    cells5 = [(lat, lon) for lat in np.arange(59.5, 60.6, 0.5) for lon in np.arange(5.0, 10.6, 0.5)]
    waves = pd.DataFrame([{"hour_utc": h, "wave_height": 1.2, "wave_direction": 240.0, "wave_period": 6.0,
                           "cell_lat": round(la, 2), "cell_lon": round(lo, 2), "dataset": "waves", "grid_deg": 0.5}
                          for la, lo in cells5 for h in hours])
    waves.to_parquet(OUT / "weather" / "waves_00000.parquet", index=False)


def run() -> None:
    for sub in ("mrv", "carbon", "ais/positions", "ais/port_calls", "ports", "weather"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    mrv()
    carbon()
    static()
    positions()
    port_calls_and_tonnage()
    locations()
    weather()
    print(f"fixtures written to {OUT}")


if __name__ == "__main__":
    _ = date
    run()
