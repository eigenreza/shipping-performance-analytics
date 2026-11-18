"""AI analyst: answers business questions with tools over the warehouse.

Tools:
  list_metrics()                                  the metric catalog (same definitions as the Power BI measures)
  get_metric(metric, filters, year_from, year_to) one number from the catalog
  query_sql(sql)                                  a read-only SELECT on the star schema (row and time limits)

Every answer keeps the SQL that ran, so a reader can check it.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field

import duckdb

from spa.ai import catalog, sqlguard
from spa.ai.llm import Client, Reply
from spa.paths import WAREHOUSE

PROMPT_VERSION = "analyst-v1"
MAX_STEPS = 6

SCHEMA_NOTES = """Tables (DuckDB, schema "marts"). Ships appear only under pseudonyms such as "Carrier 017" or "Ro-ro 042".
- marts.fct_ship_year_emissions: one row per ship and EU MRV reporting year (2018 to 2025). Columns: ship_key, ship_version_key,
  segment_key ('Vehicle carrier' or 'Ro-ro ship'), reporting_year, fuel_t, co2_t, distance_nm, hours_at_sea, avg_speed_kn,
  co2_kg_per_nm, co2_ets_scope_t, eua_due_t (allowances due), ets_cost_eur, co2_at_berth_eea_t, gross_tonnage,
  cii_attained, cii_required, cii_ratio, cii_rating ('A' best to 'E' worst, null if not rated), cii_rating_prev,
  is_rating_worse (boolean), is_quality_ok (boolean; efficiency and speed use only rows where it is true).
- marts.dim_ship: one row per ship version (slowly changing). Columns: ship_version_key, ship_key, ship_pseudonym, is_current,
  segment, flag_region, flag_state, ice_class, technical_index_type, design_generation, gross_tonnage, tonnage_method,
  size_class, length_m. Join facts with dim_ship on ship_version_key.
- marts.fct_port_call: one row per AIS-derived port call in Norway, August to September 2026. Columns: ship_key,
  ship_version_key, segment_key, port_key (UN/LOCODE), arrival_utc, berth_start_utc, departure_utc, waiting_hours,
  berth_hours, port_hours, has_waiting, is_kystverket_matched, is_window_edge.
- marts.dim_port: port_key, port_name, lat, lon, county_name. Join on port_key.
- marts.fct_voyage_leg: one row per voyage leg between two port calls. Columns: ship_key, segment_key, origin_port_key,
  destination_port_key, departure_utc, arrival_utc, sailed_nm, steaming_hours, avg_speed_kn, avg_wind_ms, avg_wave_m, rough_share.
- marts.fct_daily_carbon_price: date_key, eua_price_eur_per_t (EU ETS allowance price, EUR per tonne, one row per day, 2018-01-01 to 2026-09-30).
- marts.dim_date: date_key, year, month, month_short, year_month.
Size classes: vehicle carriers 'Small (under 30,000 GT)', 'Medium (30,000 to 57,700 GT)', 'Large (57,700 GT and above)';
ro-ro ships 'Small (under 10,000 GT)', 'Medium (10,000 to 25,000 GT)', 'Large (25,000 GT and above)'.
Flag regions: 'EU/EEA', 'Americas and Caribbean', 'Asia-Pacific', 'Africa', 'Other Europe', 'Other or unknown'.
Design generation: 'EEDI generation (contracted 2013 or later)', 'Pre-EEDI generation'."""

SYSTEM = f"""You are a careful data analyst for a shipping performance warehouse about vehicle carriers and ro-ro ships.
Answer the user's business question with numbers taken from the tools, never from memory.
Prefer get_metric when a catalog metric fits; use query_sql for anything else. Use only SELECT statements on marts tables.
Shares are numbers from 0 to 1. Do not round in tool calls.
When you have the result, reply in two parts:
1. One or two plain sentences that answer the question.
2. A last line exactly in the form: ANSWER: <value>
For numbers write the plain number without thousands separators or units (for example ANSWER: 4300769.7 or ANSWER: 0.371).
For a name, year or letter write just that (for example ANSWER: Carrier 017).

{SCHEMA_NOTES}"""

TOOLS = [
    {"name": "list_metrics", "description": "List the catalog metrics with their definitions, units and allowed filters.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "get_metric",
     "description": "Compute one catalog metric. Filters: segment, size_class, flag_region, design_generation, ship, port, month. "
                    "Years: reporting year for MRV metrics, calendar year for port calls and carbon prices.",
     "parameters": {"type": "object", "properties": {
         "metric": {"type": "string", "description": "Metric name from list_metrics, for example co2_t"},
         "filters": {"type": "object", "description": "Optional filters, for example {\"segment\": \"Vehicle carrier\"}",
                     "properties": {k: {"type": "string"} for k in catalog.FILTERS}},
         "year_from": {"type": "integer", "description": "First year to include"},
         "year_to": {"type": "integer", "description": "Last year to include"}},
         "required": ["metric"]}},
    {"name": "query_sql", "description": "Run one read-only SELECT query on the marts tables and return up to 200 rows.",
     "parameters": {"type": "object", "properties": {"sql": {"type": "string", "description": "A single SELECT statement"}},
                    "required": ["sql"]}},
]


@dataclass
class Answer:
    question: str
    model: str
    text: str = ""
    value: str | None = None
    sql: list[str] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    error: str | None = None


def _clean(v):
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


class Tools:
    def __init__(self, con: duckdb.DuckDBPyConnection):
        self.con = con

    def call(self, name: str, args: dict) -> tuple[dict, str | None]:
        """Run a tool; returns (result, sql that ran)."""
        try:
            if name == "list_metrics":
                return {"metrics": [{"name": k, "description": m["description"], "unit": m["unit"], "power_bi_measure": m["measure"]}
                                    for k, m in catalog.METRICS.items()]}, None
            if name == "get_metric":
                filters = {k: v for k, v in (args.get("filters") or {}).items() if v not in (None, "")}
                sql, params = catalog.metric_sql(args["metric"], filters, args.get("year_from"), args.get("year_to"))
                value = self.con.execute(sql, params).fetchall()[0][0]
                shown = sql
                for p in params:
                    shown = shown.replace("?", f"'{p}'" if isinstance(p, str) else str(p), 1)
                return {"metric": args["metric"], "value": _clean(value), "unit": catalog.METRICS[args["metric"]]["unit"]}, shown
            if name == "query_sql":
                res = sqlguard.run(self.con, args.get("sql", ""))
                res["rows"] = [[_clean(v) for v in r] for r in res["rows"]]
                return res, res["sql"]
            return {"error": f"unknown tool {name}"}, None
        except (sqlguard.UnsafeQuery, ValueError, KeyError, duckdb.Error) as e:
            return {"error": str(e)[:400]}, None


ANSWER_RE = re.compile(r"ANSWER:\s*(.+)", re.I)


def ask(client: Client, question: str, con: duckdb.DuckDBPyConnection | None = None) -> Answer:
    own = con is None
    con = con or duckdb.connect(str(WAREHOUSE), read_only=True)
    tools = Tools(con)
    ans = Answer(question=question, model=client.model)
    messages: list[dict] = [{"role": "user", "content": question}]
    try:
        for step in range(MAX_STEPS):
            reply: Reply = client.chat(SYSTEM, messages, TOOLS)
            ans.steps = step + 1
            ans.input_tokens += reply.input_tokens
            ans.output_tokens += reply.output_tokens
            ans.latency_s += reply.latency_s
            if not reply.tool_calls:
                ans.text = reply.text.strip()
                m = ANSWER_RE.search(ans.text)
                ans.value = m.group(1).strip().strip("*`").strip() if m else None
                break
            messages.append({"role": "assistant", "content": reply.text, "tool_calls": reply.tool_calls, "raw": reply.raw})
            for call in reply.tool_calls:
                result, sql = tools.call(call["name"], call.get("args") or {})
                ans.tool_calls.append({"name": call["name"], "args": call.get("args"), "ok": "error" not in result})
                if sql:
                    ans.sql.append(sql)
                messages.append({"role": "tool", "name": call["name"], "content": json.loads(json.dumps(result, default=str))})
        else:
            ans.error = f"no final answer after {MAX_STEPS} steps"
    except Exception as e:  # noqa: BLE001 - recorded as a failed answer, never hidden
        ans.error = f"{type(e).__name__}: {str(e)[:300]}"
    finally:
        if own:
            con.close()
    ans.latency_s = round(ans.latency_s, 2)
    return ans
