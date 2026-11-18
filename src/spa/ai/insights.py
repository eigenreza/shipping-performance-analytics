"""AI insight writer and the automatic number checker.

The writer gets the data behind one report page and writes three short
findings. The checker extracts every number from each finding and looks for
it among the values the page data supports: the values themselves, their
differences, ratios and percentage changes, at the precision the finding
uses. A finding is "supported" when every number is found, "unsupported"
when at least one number is not.
"""

from __future__ import annotations

import itertools
import json
import math
import re
from dataclasses import dataclass, field

import duckdb

from spa.ai.llm import Client
from spa.paths import RESULTS, WAREHOUSE

PROMPT_VERSION = "insights-v1"
SYSTEM = """You write short findings for a business report about vehicle carriers and ro-ro ships.
You get the data behind one report page as JSON. Write exactly three findings.
Rules: each finding is one plain sentence for a business reader; use only numbers that appear in the data or simple
differences or percentage changes between them; round sensibly; do not invent causes.
Return only a JSON array of three strings."""

YEAR_RE = re.compile(r"^(19|20)\d{2}$")
NUM_RE = re.compile(
    r"(?<![\w.])([-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?)\s*(%|percent|per cent|percentage points?|million|billion|thousand|k\b|m\b|bn\b)?",
    re.I,
)
SCALE = {"million": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9, "thousand": 1e3, "k": 1e3}


def page_contexts(con: duckdb.DuckDBPyConnection) -> dict[str, dict]:
    """Data behind five report pages, as small tables."""
    def rows(sql):
        df = con.sql(sql).df()
        return json.loads(df.to_json(orient="records", double_precision=6))

    return {
        "overview": {"title": "Fleet overview: totals by segment and year", "rows": rows("""
            select segment_key as segment, reporting_year as year, round(sum(co2_t)) as co2_t, count(distinct ship_key) as ships,
                   round(sum(ets_cost_eur)) as ets_cost_eur
            from marts.fct_ship_year_emissions where reporting_year between 2023 and 2025 group by 1, 2 order by 1, 2""")},
        "efficiency": {"title": "Fleet efficiency: CO2 per nautical mile and speed by segment and year", "rows": rows("""
            select segment_key as segment, reporting_year as year,
                   round(sum(co2_t) * 1000 / sum(distance_nm), 1) as co2_kg_per_nm,
                   round(sum(distance_nm) / sum(hours_at_sea), 2) as speed_kn
            from marts.fct_ship_year_emissions where is_quality_ok and reporting_year between 2021 and 2025 group by 1, 2 order by 1, 2""")},
        "ratings": {"title": "Carbon ratings: share of rated ship-years by rating", "rows": rows("""
            select segment_key as segment, reporting_year as year,
                   round(avg(case when cii_rating in ('A','B') then 1.0 else 0.0 end), 3) as share_a_or_b,
                   round(avg(case when cii_rating in ('D','E') then 1.0 else 0.0 end), 3) as share_d_or_e,
                   count(*) as rated_ship_years
            from marts.fct_ship_year_emissions where cii_rating is not null and reporting_year between 2023 and 2025
            group by 1, 2 order by 1, 2""")},
        "ports": {"title": "Port calls on the Norwegian coast, August to September 2026 (top ports)", "rows": rows("""
            select p.port_name as port, count(*) as calls, round(median(c.berth_hours), 1) as median_berth_hours,
                   round(avg(case when c.has_waiting then 1.0 else 0.0 end), 3) as share_with_waiting
            from marts.fct_port_call c join marts.dim_port p using (port_key) group by 1 order by 2 desc limit 8""")},
        "carbon_price": {"title": "EU ETS allowance price by year (EUR per tonne)", "rows": rows("""
            select year(date_key) as year, round(avg(eua_price_eur_per_t), 2) as average_price,
                   round(min(eua_price_eur_per_t), 2) as lowest, round(max(eua_price_eur_per_t), 2) as highest
            from marts.fct_daily_carbon_price group by 1 order by 1""")},
    }


@dataclass
class NumberCheck:
    text: str
    value: float
    supported: bool
    matched: float | None = None


@dataclass
class FindingCheck:
    finding: str
    numbers: list[NumberCheck] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.numbers:
            return "no numbers"
        return "supported" if all(n.supported for n in self.numbers) else "unsupported"


def candidates(context: dict) -> tuple[list[float], set[int]]:
    """Values a finding may cite: data values, differences, ratios and percentage changes within each column."""
    rows = context["rows"]
    years = {int(v) for r in rows for k, v in r.items() if k == "year" and v is not None}
    cols: dict[str, list[float]] = {}
    for r in rows:
        for k, v in r.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and k != "year":
                cols.setdefault(k, []).append(float(v))
    out = []
    for vals in cols.values():
        out += vals
        for a, b in itertools.permutations(vals, 2):
            out.append(a - b)
            if b:
                out += [a / b, a / b - 1]
    shares = [v for v in out if -1.5 <= v <= 1.5]
    out += [v * 100 for v in shares]  # shares and changes written as percentages
    return out, years


def parse_numbers(text: str, years: set[int]) -> list[tuple[str, float, float]]:
    """(raw text, value, allowed absolute error) for every number in a finding, skipping year labels."""
    found = []
    for m in NUM_RE.finditer(text):
        raw, unit = m.group(1), (m.group(2) or "").lower().strip()
        clean = raw.replace(",", "")
        if YEAR_RE.match(clean) and not unit and int(clean) in years | set(range(2015, 2031)):
            continue
        value = float(clean)
        decimals = len(clean.split(".")[1]) if "." in clean else 0
        scale = SCALE.get(unit, 1.0)
        tol = 0.5 * 10 ** (-decimals) * scale
        if unit in ("%", "percent", "per cent") or unit.startswith("percentage point"):
            pass  # compared against the percentage candidates
        found.append((m.group(0).strip(), value * scale, max(tol, 1e-9)))
    return found


def check_finding(finding: str, context: dict) -> FindingCheck:
    cands, years = candidates(context)
    fc = FindingCheck(finding)
    for raw, value, tol in parse_numbers(finding, years):
        # Allowed error: half a unit of the last digit shown (scaled), plus 0.05% for rounding of the data itself.
        best = next((c for c in cands if abs(c - value) <= tol + 0.0005 * abs(c)), None)
        if best is None:  # signs are often dropped in prose ("fell by 3%")
            best = next((c for c in cands if abs(abs(c) - abs(value)) <= tol + 0.0005 * abs(c)), None)
        fc.numbers.append(NumberCheck(raw, value, best is not None, best))
    return fc


def parse_findings(text: str) -> list[str]:
    text = text.strip()
    m = re.search(r"\[.*\]", text, re.S)
    if m:
        try:
            items = json.loads(m.group(0))
            if isinstance(items, list):
                return [str(x).strip() for x in items if str(x).strip()][:3]
        except json.JSONDecodeError:
            pass
    lines = [re.sub(r"^\s*(?:[-*\d.)]+\s*)", "", ln).strip() for ln in text.splitlines()]
    return [ln for ln in lines if len(ln) > 20][:3]


def write(client: Client, page: str, context: dict) -> dict:
    data = json.dumps(context, separators=(",", ":"))
    reply = client.chat(SYSTEM, [{"role": "user", "content": f"Page: {page}\nData: {data}"}])
    findings = parse_findings(reply.text)
    checks = [check_finding(f, context) for f in findings]
    return {
        "page": page, "model": client.model, "latency_s": reply.latency_s,
        "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens,
        "findings": [{"text": c.finding, "status": c.status,
                      "numbers": [{"text": n.text, "supported": n.supported, "matched": None if n.matched is None or not math.isfinite(n.matched) else round(n.matched, 6)}
                                  for n in c.numbers]} for c in checks],
    }


def contexts() -> dict[str, dict]:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        return page_contexts(con)
    finally:
        con.close()


OUT = RESULTS / "ai"
