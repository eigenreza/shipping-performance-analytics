"""Hourly wind and sea state along AIS voyage legs from Open-Meteo.

Positions are snapped to a grid (0.25 degrees for wind, 0.5 degrees for
waves, close to the native resolution of the underlying models). Each grid
cell a fleet ship passed through while under way is queried once for the
whole AIS window: wind from the Historical Weather API (ERA5 reanalysis) and
significant wave height from the Marine Weather API. Requests are paced to
stay inside the free API's per-minute and per-hour limits. Results are cached per cell, so reruns
make no new calls. Data after the project's end date is never requested.
"""

from __future__ import annotations

import time

import duckdb
import pandas as pd
import requests

from spa.http import USER_AGENT
from spa.ingest.ais import window
from spa.paths import RAW

GRID = {"wind": 0.25, "waves": 0.5}
DAYS_PER_CALL = 14  # the API counts each 14 days per location as one call
MAX_CALLS_PER_MINUTE = 500
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
MARINE = "https://marine-api.open-meteo.com/v1/marine"
OUT = RAW / "weather"
BATCH = 25


def cells(grid: float = 0.25, min_speed_kn: float = 3.0) -> pd.DataFrame:
    pos = (RAW / "ais" / "positions").as_posix()
    return duckdb.sql(
        f"""select distinct round(lat / {grid}) * {grid} as cell_lat, round(lon / {grid}) * {grid} as cell_lon
            from '{pos}/*.parquet' where sog > {min_speed_kn}
            order by 1, 2"""
    ).df()


def _fetch(sess, url: str, lats, lons, hourly: str, start, end) -> list[dict]:
    params = {
        "latitude": ",".join(f"{x:.2f}" for x in lats),
        "longitude": ",".join(f"{x:.2f}" for x in lons),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": hourly,
        "timezone": "UTC",
        "wind_speed_unit": "ms",
    }
    for attempt in range(6):
        r = sess.get(url, params=params, timeout=180)
        if r.status_code == 429:
            time.sleep(65)
            continue
        if r.status_code >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else [data]
    raise RuntimeError("Open-Meteo request failed after retries")


def _frame(items: list[dict], lats, lons, kind: str) -> pd.DataFrame:
    frames = []
    for item, la, lo in zip(items, lats, lons, strict=True):
        h = item.get("hourly") or {}
        if not h:
            continue
        df = pd.DataFrame(h)
        df["cell_lat"], df["cell_lon"] = la, lo
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True).rename(columns={"time": "hour_utc"})
    df["hour_utc"] = pd.to_datetime(df["hour_utc"])
    df["dataset"] = kind
    return df


def run() -> dict:
    start, end = window()
    OUT.mkdir(parents=True, exist_ok=True)
    sess = requests.Session()
    sess.headers["User-Agent"] = USER_AGENT
    weight_per_location = -(-((end - start).days + 1) // DAYS_PER_CALL)
    info = {}
    for kind, url, hourly in (
        ("wind", ARCHIVE, "wind_speed_10m,wind_direction_10m,wind_gusts_10m"),
        ("waves", MARINE, "wave_height,wave_direction,wave_period"),
    ):
        grid = cells(GRID[kind])
        calls = 0
        for i in range(0, len(grid), BATCH):
            dest = OUT / f"{kind}_{i:05d}.parquet"
            if dest.exists():
                continue
            chunk = grid.iloc[i : i + BATCH]
            lats, lons = chunk.cell_lat.tolist(), chunk.cell_lon.tolist()
            t = time.time()
            items = _fetch(sess, url, lats, lons, hourly, start, end)
            df = _frame(items, lats, lons, kind)
            df["grid_deg"] = GRID[kind]
            df.to_parquet(dest, index=False)
            weight = len(chunk) * weight_per_location
            calls += weight
            time.sleep(max(0.0, 60.0 * weight / MAX_CALLS_PER_MINUTE - (time.time() - t)))
        info[kind] = {"cells": len(grid), "weighted_calls": calls}
        print(f"Weather {kind}: {info[kind]}", flush=True)
    return info


if __name__ == "__main__":
    run()
