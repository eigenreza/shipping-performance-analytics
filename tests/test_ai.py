"""SQL guard, metric catalog, scoring rules and the insight number checker."""

from __future__ import annotations

import duckdb
import pytest

from spa.ai import catalog, insights, sqlguard
from spa.ai.evaluate import parse_number, score
from spa.ai.questions import QUESTIONS


@pytest.mark.parametrize("sql", [
    "select count(*) from marts.dim_ship",
    "with x as (select * from marts.fct_port_call) select count(*) from x",
    "select segment_key from marts.fct_ship_year_emissions union all select 'x'",
])
def test_guard_accepts_selects(sql):
    assert sqlguard.check(sql)


@pytest.mark.parametrize("sql", [
    "delete from marts.dim_ship",
    "drop table marts.dim_ship",
    "select * from staging.stg_mrv__ship_year",
    "select * from intermediate.int_fleet_ships",
    "select * from dim_ship",
    "select * from read_parquet('data/raw/mrv/*.parquet')",
    "select * from glob('*')",
    "select getenv('GEMINI_API_KEY')",
    "select 1; select 2",
    "copy marts.dim_ship to 'x.csv'",
    "attach 'x.db'",
    "install httpfs",
    "pragma show_tables",
    "create table marts.x as select 1",
])
def test_guard_blocks_everything_else(sql):
    with pytest.raises(sqlguard.UnsafeQuery):
        sqlguard.check(sql)


def test_guard_limits_rows():
    con = duckdb.connect()
    con.execute("create schema marts; create table marts.t as select range as v from range(1000)")
    res = sqlguard.run(con, "select v from marts.t")
    assert len(res["rows"]) == sqlguard.MAX_ROWS and res["truncated"]


def test_catalog_sql_and_filters():
    sql, params = catalog.metric_sql("co2_t", {"segment": "Vehicle carrier"}, 2025, 2025)
    assert "f.segment_key = ?" in sql and params == ["Vehicle carrier", 2025, 2025]
    with pytest.raises(ValueError):
        catalog.metric_sql("no_such_metric")
    with pytest.raises(ValueError):
        catalog.metric_sql("co2_t", {"port": "Bergen"})  # port filter does not apply to ship-year metrics


def test_questions_frozen_shape():
    ids = [q[0] for q in QUESTIONS]
    assert len(ids) == 40 and len(set(ids)) == 40
    assert sum(q[1] == "dev" for q in QUESTIONS) == 10
    assert sum(q[1] == "test" for q in QUESTIONS) == 30


@pytest.mark.parametrize("kind,gold,answer,ok", [
    ("number", 4300769.68, "4300769.7", True),
    ("number", 4300769.68, "4,300,770", True),
    ("number", 4300769.68, "4.4 million", False),
    ("number", 0.3706, "0.371", True),
    ("number", 0.3706, "37.1%", True),
    ("number", 0.3706, "37.06", True),
    ("number", -0.1036, "-10.36%", True),
    ("number", -0.1036, "0.9113", False),
    ("number", 229, None, False),
    ("text", "Stavanger", "Stavanger", True),
    ("text", "Vehicle carrier", "Vehicle carriers have the lower value: Vehicle carrier", True),
    ("text", "December", "Dec", False),
])
def test_scoring_rules(kind, gold, answer, ok):
    assert score(kind, gold, answer) is ok


def test_parse_number():
    assert parse_number("ANSWER 1,234.5") == 1234.5
    assert parse_number("12.5%") == pytest.approx(0.125)
    assert parse_number("none") is None


CONTEXT = {"rows": [
    {"segment": "A", "year": 2024, "co2_t": 1000.0, "ships": 10},
    {"segment": "A", "year": 2025, "co2_t": 1100.0, "ships": 12},
]}


@pytest.mark.parametrize("text,status", [
    ("CO2 rose from 1,000 tonnes in 2024 to 1,100 tonnes in 2025.", "supported"),
    ("CO2 rose by 10% between 2024 and 2025.", "supported"),
    ("The fleet grew from 10 to 12 ships.", "supported"),
    ("CO2 rose by 100 tonnes.", "supported"),
    ("CO2 reached 1,150 tonnes in 2025.", "unsupported"),
    ("CO2 rose by 15% in 2025.", "unsupported"),
    ("Emissions went up.", "no numbers"),
])
def test_number_checker(text, status):
    assert insights.check_finding(text, CONTEXT).status == status


def test_findings_parser():
    assert insights.parse_findings('["one finding about CO2", "two finding about ships", "three finding about cost"]') == [
        "one finding about CO2", "two finding about ships", "three finding about cost"]
    assert len(insights.parse_findings("1. The first finding is here.\n2. The second finding is here.\n3. And the third one is here.")) == 3
