"""EU MRV (THETIS-MRV) public emission reports published by EMSA.

One workbook per reporting year. The latest published version of each year is
downloaded, parsed and written to ``data/raw/mrv/mrv_<year>.parquet`` with
normalized column names. All ship types are kept in the raw layer; the fleet
filter (ro-ro ships and vehicle carriers) is applied in dbt staging.
"""

from __future__ import annotations

import re
import unicodedata
import warnings
from pathlib import Path

import openpyxl
import pandas as pd

from spa import http
from spa.paths import RAW

BASE = "https://mrv.emsa.europa.eu/api/public-emission-report"
OUT = RAW / "mrv"


def list_files() -> list[dict]:
    r = http.get(f"{BASE}/downloadable-files", params={"page": 1, "limit": 100})
    return r.json()["results"]


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).replace("₂", "2")
    text = text.encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def _units(text: str) -> str:
    m = re.search(r"\[(.*?)\]", str(text))
    return m.group(1) if m else ""


def parse_workbook(path: Path) -> pd.DataFrame:
    """Parse an MRV workbook. Row 3 holds the column headers.

    Units are kept in a side table so that columns with the same words but
    different units (for example per mass and per volume) stay distinct.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    groups = [next(rows), next(rows)]
    header = next(rows)
    # Forward-fill the two group header rows so duplicated labels (for example
    # the monitoring method letters) get a unique prefix.
    filled = []
    for g in groups:
        cur, out = None, []
        for v in g:
            cur = v if v not in (None, "") else cur
            out.append(cur)
        filled.append(out)
    names, seen = [], {}
    for i, h in enumerate(header):
        base = _slug(h) if h else f"col_{i}"
        unit = _slug(_units(h)) if h else ""
        if base in ("a", "b", "c", "d"):
            base = f"monitoring_method_{base}"
        if "laden" not in base and filled[1][i] and "laden" in str(filled[1][i]).lower():
            base = f"laden_{base}"
        if unit and base in seen:
            base = f"{base}__{unit}"
        n = seen.get(base, 0)
        seen[base] = n + 1
        names.append(base if n == 0 else f"{base}_{n + 1}")
    data = [r for r in rows if r and r[0] not in (None, "")]
    wb.close()
    df = pd.DataFrame(data, columns=names)
    # Normalize "N/A", "Division by zero!" and similar placeholders to null.
    df = df.replace({"N/A": None, "Not Applicable": None, "Division by zero!": None, "": None})
    for c in df.columns:
        if df[c].dtype == object:
            conv = pd.to_numeric(df[c], errors="coerce")
            non_null = df[c].notna().sum()
            if non_null and conv.notna().sum() >= 0.95 * non_null and c not in ("imo_number",):
                df[c] = conv
    df["imo_number"] = df["imo_number"].astype(str).str.strip()
    return df


def run(years: list[int] | None = None, force: bool = False) -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    log = []
    for f in list_files():
        year, version = f["reportingPeriod"], f["version"]
        if years and year not in years:
            continue
        xlsx = OUT / f"mrv_{year}.xlsx"
        meta = OUT / f"mrv_{year}.version"
        if force or not xlsx.exists() or not meta.exists() or meta.read_text().strip() != str(version):
            size = http.download(f"{BASE}/reporting-period-document/binary/{year}/{version}", xlsx, timeout=600)
            meta.write_text(str(version))
        else:
            size = xlsx.stat().st_size
        df = parse_workbook(xlsx)
        df["source_version"] = version
        df.to_parquet(OUT / f"mrv_{year}.parquet", index=False)
        log.append({"year": year, "version": version, "bytes": size, "rows": len(df)})
        print(f"MRV {year} v{version}: {len(df):,} rows, {size / 1e6:.1f} MB")
    return log


if __name__ == "__main__":
    run()
