"""Kystverket AIS and port call data from the Kystdatahuset open web services.

Four datasets, all limited to the analysis window (eight weeks ending on the
project's data end date):

* ``static``: AIS static ship records, used only to link the MRV fleet (by IMO
  number) to AIS identities (MMSI). Kept in the private raw layer.
* ``port_calls``: Kystverket's own port call records (time in port per ship and
  location), used as an independent cross-check of the AIS-derived calls.
* ``positions``: AIS positions for the fleet, thinned to one position per
  ``THIN_SECONDS`` per ship.
* ``locations``: Kystverket's register of Norwegian ports and quays.

Every request is checkpointed to its own Parquet file so an interrupted run
resumes where it stopped.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta

import duckdb
import pandas as pd
import requests

from spa.http import USER_AGENT
from spa.paths import DATA_END, RAW

BASE = "https://kystdatahuset.kystverket.no/ws"
OUT = RAW / "ais"
WINDOW_DAYS = 57  # eight weeks plus the end day
THIN_SECONDS = 120
FLEET_TYPES = ("Ro-ro ship", "Vehicle carrier")

POSITION_COLUMNS = [
    "mmsi", "ts", "lon", "lat", "cog", "sog", "message_nr", "calc_speed",
    "sec_prevpoint", "dist_prevpoint", "true_heading", "rot",
]


def window() -> tuple[date, date]:
    end = date.fromisoformat(DATA_END)
    return end - timedelta(days=WINDOW_DAYS - 1), end


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def _call(sess, method: str, path: str, *, retries: int = 5, timeout: int = 300, **kw) -> dict:
    for attempt in range(retries):
        try:
            r = sess.request(method, BASE + path, timeout=timeout, **kw)
            if r.status_code >= 500 or r.status_code == 429:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError, json.JSONDecodeError):
            if attempt == retries - 1:
                raise
            time.sleep(3 * 2**attempt)
    raise RuntimeError("unreachable")


def fleet_imos() -> list[int]:
    rows = duckdb.sql(
        f"""select distinct try_cast(imo_number as bigint) imo
            from '{(RAW / "mrv").as_posix()}/mrv_*.parquet'
            where ship_type in {FLEET_TYPES} and try_cast(imo_number as bigint) is not null"""
    ).fetchall()
    return sorted(r[0] for r in rows)


def static(force: bool = False) -> int:
    """AIS static records valid in the window, reduced to the MRV fleet."""
    dest = OUT / "static_fleet.parquet"
    if dest.exists() and not force:
        return len(pd.read_parquet(dest))
    start, end = window()
    sess = _session()
    payload = _call(
        sess, "GET", "/api/ais/static-messages",
        params={"start": start.isoformat(), "end": (end + timedelta(days=1)).isoformat(), "limit": 500000},
        timeout=600,
    )
    df = pd.DataFrame(payload["data"])
    imos = set(fleet_imos())
    df = df[df["imoNumber"].isin(imos)].copy()
    df["truncated_source"] = "truncated" in (payload.get("msg") or "")
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest, index=False)
    print(f"AIS static: {len(df):,} fleet records, {df.mmsi.nunique()} MMSI, {df.imoNumber.nunique()} IMO")
    return len(df)


def fleet_mmsis() -> list[int]:
    start, _ = window()
    df = pd.read_parquet(OUT / "static_fleet.parquet")
    valid = df["validTo"].isna() | (pd.to_datetime(df["validTo"]) >= pd.Timestamp(start))
    return sorted(df.loc[valid, "mmsi"].astype("int64").unique().tolist())


def port_calls(force: bool = False) -> int:
    """Kystverket time-in-port records, one request per day."""
    start, end = window()
    outdir = OUT / "port_calls"
    outdir.mkdir(parents=True, exist_ok=True)
    sess = _session()
    n = 0
    d = start
    while d <= end:
        dest = outdir / f"{d.isoformat()}.parquet"
        if force or not dest.exists():
            payload = _call(
                sess, "POST", "/api/location/time-in-port/all",
                json={"startTime": d.isoformat(), "endTime": (d + timedelta(days=1)).isoformat()},
            )
            df = pd.DataFrame(payload.get("data") or [])
            df["query_day"] = d.isoformat()
            df.to_parquet(dest, index=False)
        n += 1
        d += timedelta(days=1)
    print(f"Port call records: {n} days")
    return n


def thin(df: pd.DataFrame, seconds: int = THIN_SECONDS) -> pd.DataFrame:
    """Keep the first position in each ``seconds`` bucket per ship."""
    if df.empty:
        return df
    df = df.sort_values(["mmsi", "ts"])
    bucket = df["ts"].dt.floor(f"{seconds}s")
    return df.loc[~pd.DataFrame({"m": df["mmsi"], "b": bucket}).duplicated()].reset_index(drop=True)


def _positions_request(sess, mmsis: list[int], t0: datetime, t1: datetime) -> pd.DataFrame:
    payload = _call(
        sess, "POST", "/api/ais/positions/for-mmsis-time",
        json={"mmsiIds": mmsis, "start": t0.strftime("%Y%m%d%H%M"), "end": t1.strftime("%Y%m%d%H%M"), "minSpeed": -1},
        timeout=600,
    )
    rows = payload.get("data") or []
    if not payload.get("success") and rows == []:
        msg = (payload.get("msg") or "").lower()
        if "no data" not in msg and "ingen" not in msg and msg.strip():
            print(f"  note: {msg[:120]}")
    df = pd.DataFrame(rows, columns=POSITION_COLUMNS) if rows else pd.DataFrame(columns=POSITION_COLUMNS)
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"])
        df = df.drop(columns=["message_nr"])
    return df


def positions(batch: int = 100, days: int = 7, limit_batches: int | None = None) -> dict:
    """AIS positions for the fleet in the window, thinned and checkpointed."""
    start, end = window()
    mmsis = fleet_mmsis()
    outdir = OUT / "positions"
    outdir.mkdir(parents=True, exist_ok=True)
    sess = _session()
    stats = {"requests": 0, "rows": 0, "seconds": 0.0}
    batches = [mmsis[i : i + batch] for i in range(0, len(mmsis), batch)]
    if limit_batches:
        batches = batches[:limit_batches]
    for bi, group in enumerate(batches):
        d = start
        while d <= end:
            d1 = min(d + timedelta(days=days), end + timedelta(days=1))
            dest = outdir / f"b{bi:03d}_{d.isoformat()}.parquet"
            if not dest.exists():
                t = time.time()
                df = _positions_request(sess, group, datetime.combine(d, datetime.min.time()),
                                        datetime.combine(d1, datetime.min.time()))
                df = thin(df)
                df = df[df["ts"] < pd.Timestamp(end + timedelta(days=1))] if not df.empty else df
                df.to_parquet(dest, index=False)
                stats["requests"] += 1
                stats["rows"] += len(df)
                stats["seconds"] += time.time() - t
            d = d1
        print(f"  batch {bi + 1}/{len(batches)} done; {stats}", flush=True)
    return stats


def locations(force: bool = False) -> int:
    dest = RAW / "ports" / "kystverket_locations.parquet"
    if dest.exists() and not force:
        return len(pd.read_parquet(dest))
    sess = _session()
    r = sess.get(BASE + "/api/location/norway/all/geojson", timeout=300)
    r.raise_for_status()
    feats = r.json()["features"]
    rows = []
    for f in feats:
        p = dict(f["properties"])
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates") if geom.get("type") == "Point" else None
        p["lon"], p["lat"] = (coords or [None, None])[:2]
        p.pop("geomll", None)
        rows.append(p)
    df = pd.DataFrame(rows)
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest, index=False)
    print(f"Kystverket locations: {len(df):,}")
    return len(df)


def run() -> None:
    locations()
    static()
    port_calls()
    positions()


if __name__ == "__main__":
    run()


def tonnage_calibration(first: str = "2025-01-01", last: str = "2026-07-31", step_days: int = 7) -> int:
    """Reported gross tonnage and deadweight of ro-ro ships and vehicle carriers.

    Kystverket port call records carry the tonnage of each calling ship. One
    day per week over a longer period gives enough ships to calibrate the
    size estimate used for the carbon intensity rating. Only ship name, type
    and tonnage are kept.
    """
    dest = OUT / "tonnage_calibration.parquet"
    sess = _session()
    frames = []
    d, stop = date.fromisoformat(first), date.fromisoformat(last)
    while d <= stop:
        payload = _call(sess, "POST", "/api/location/time-in-port/all",
                        json={"startTime": d.isoformat(), "endTime": (d + timedelta(days=1)).isoformat()})
        df = pd.DataFrame(payload.get("data") or [])
        if not df.empty:
            keep = df["shiptype"].fillna("").str.contains("Ro-Ro Cargo|Vehicles Carrier|Container/Ro-Ro", regex=True)
            frames.append(df.loc[keep, ["shipname", "shiptype", "gt", "dwt"]])
        d += timedelta(days=step_days)
    out = pd.concat(frames).drop_duplicates()
    out.to_parquet(dest, index=False)
    print(f"Tonnage calibration: {len(out)} ship records")
    return len(out)
