"""Daily EU ETS allowance (EUA) price history from Ember.

Ember publishes the daily EU ETS price (front December contract, EUR per
tonne of CO2) in its "European electricity prices and costs" data tool under
CC-BY-4.0. The series is read from the published chart data and written to
``data/raw/carbon/eua_daily.parquet``. Rows after the project's data end
date are dropped.
"""

from __future__ import annotations

import json
import re

import pandas as pd

from spa import http
from spa.paths import DATA_END, RAW

CHART_URL = "https://flo.uri.sh/visualisation/30588075/embed?auto=1"
SOURCE_PAGE = "https://ember-energy.org/data/european-electricity-prices-and-costs/"
OUT = RAW / "carbon"


def parse_chart(html: str) -> pd.DataFrame:
    m = re.search(r"_Flourish_data\s*=\s*(\{.*?\})\s*,\s*\n", html, re.S)
    if not m:
        m = re.search(r"_Flourish_data\s*=\s*(\{\"data\":\[.*?\]\})", html, re.S)
    if not m:
        raise ValueError("price series not found in chart data")
    payload = json.loads(m.group(1))
    rows = []
    for rec in payload["data"]:
        value = rec["value"][0]
        if value in ("", None):
            continue
        rows.append({"price_date": rec["label"], "eua_price_eur": float(value), "unit": rec["metadata"][1]})
    df = pd.DataFrame(rows)
    df["price_date"] = pd.to_datetime(df["price_date"]).dt.date
    return df


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    html = http.get(CHART_URL, timeout=120).text
    df = parse_chart(html)
    df = df[df["price_date"] <= pd.Timestamp(DATA_END).date()].sort_values("price_date")
    if not (df["unit"] == "€/t").all():
        raise ValueError("unexpected unit in carbon price series")
    df = df.drop(columns="unit")
    df["source"] = "Ember (CC-BY-4.0), EU ETS front December contract"
    df.to_parquet(OUT / "eua_daily.parquet", index=False)
    info = {"rows": len(df), "first": str(df.price_date.min()), "last": str(df.price_date.max())}
    print(f"EUA prices: {info}")
    return info


if __name__ == "__main__":
    run()
