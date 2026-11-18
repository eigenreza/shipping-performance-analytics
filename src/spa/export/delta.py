"""Exports from the warehouse.

* ``data/exports/gold/*.parquet``: the star schema for Power BI (Import mode)
  and the demo. Pseudonymous only, small, and kept in the repository so the
  Power BI project opens without running the pipeline.
* ``data/exports/delta/{bronze,silver,gold}``: the same layers as Delta
  tables written with the open-source ``deltalake`` package, laid out like a
  Fabric lakehouse (bronze = raw files, silver = staging and intermediate
  models, gold = marts). Bronze and silver hold identifiers and stay local.
"""

from __future__ import annotations

import shutil

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from deltalake import write_deltalake

from spa.paths import EXPORTS, WAREHOUSE

GOLD_TABLES = [
    "dim_date", "dim_segment", "dim_ship", "dim_port",
    "fct_ship_year_emissions", "fct_port_call", "fct_voyage_leg", "fct_daily_carbon_price",
]
REFERENCE_TABLES = ["eu_ets_phase_in", "cii_reference_lines", "cii_reduction_factors", "cii_rating_boundaries", "fuel_assumptions"]


def _tables(con, schema: str) -> list[str]:
    return [r[0] for r in con.sql(
        f"select table_name from information_schema.tables where table_schema = '{schema}' order by 1"
    ).fetchall()]


def _arrow(con, schema: str, table: str) -> pa.Table:
    t = con.sql(f'select * from "{schema}"."{table}"').arrow()
    if isinstance(t, pa.RecordBatchReader):
        t = t.read_all()
    # Drop pandas/duckdb schema metadata so files carry no tool or time stamps.
    return t.replace_schema_metadata(None)


def write_gold_parquet(con) -> dict:
    out = EXPORTS / "gold"
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name in GOLD_TABLES:
        t = _arrow(con, "marts", name)
        pq.write_table(t, out / f"{name}.parquet", compression="zstd", write_statistics=True)
        counts[name] = t.num_rows
    for name in REFERENCE_TABLES:
        t = _arrow(con, "reference", name)
        pq.write_table(t, out / f"ref_{name}.parquet", compression="zstd")
    return counts


def write_delta(con) -> dict:
    root = EXPORTS / "delta"
    if root.exists():
        shutil.rmtree(root)
    layers = {
        "bronze": [("staging", t) for t in _tables(con, "staging")],
        "silver": [("intermediate", t) for t in _tables(con, "intermediate")],
        "gold": [("marts", t) for t in _tables(con, "marts")] + [("reference", t) for t in _tables(con, "reference")],
    }
    counts = {}
    for layer, items in layers.items():
        for schema, table in items:
            t = _arrow(con, schema, table)
            write_deltalake(str(root / layer / table), t, mode="overwrite")
            counts[f"{layer}.{table}"] = t.num_rows
    return counts


def run(delta: bool = True) -> dict:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        info = {"gold_parquet": write_gold_parquet(con)}
        if delta:
            info["delta"] = write_delta(con)
    finally:
        con.close()
    return info
