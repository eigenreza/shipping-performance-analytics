"""Write the Power BI report in the enhanced report format (PBIR).

Every page opens with three plain lines (What this is, How to use it, What
to notice), carries the repository link in its footer, and uses the same
theme. Files are validated against Microsoft's published JSON schemas in the
tests.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

NS = uuid.UUID("0c8a0c53-62b5-4a39-8f0f-6f4f6a1f9e27")
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/"
V_CONTAINER = SCHEMA + "definition/visualContainer/2.4.0/schema.json"
V_PAGE = SCHEMA + "definition/page/2.0.0/schema.json"
REPO = "github.com/eigenreza/shipping-performance-analytics"
M = "Metrics"
W, H = 1280, 720

THEME = {
    "name": "Shipping Performance",
    "dataColors": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "background": "#FFFFFF",
    "foreground": "#1B2A3A",
    "tableAccent": "#1F4E79",
    "good": "#2A9D8F",
    "neutral": "#E9A23B",
    "bad": "#C8553D",
    "maximum": "#1F4E79",
    "center": "#DCE6F0",
    "minimum": "#FFFFFF",
    "textClasses": {
        "title": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": "#1B2A3A"},
        "header": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": "#1B2A3A"},
        "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": "#3D4F63"},
        "callout": {"fontFace": "Segoe UI Light", "fontSize": 26, "color": "#1F4E79"},
    },
    "visualStyles": {
        "*": {"*": {
            "border": [{"show": False}],
            "background": [{"show": True, "transparency": 0}],
            "visualHeader": [{"show": True}],
        }},
        "page": {"*": {"background": [{"color": {"solid": {"color": "#F4F6F9"}}, "transparency": 0}]}},
    },
}


def vid(*parts: str) -> str:
    return uuid.uuid5(NS, "/".join(parts)).hex[:20]


def lit(value) -> dict:
    if isinstance(value, bool):
        v = "true" if value else "false"
    elif isinstance(value, int):
        v = f"{value}L"
    elif isinstance(value, float):
        v = f"{value}D"
    else:
        v = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": v}}}


def col(entity: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def meas(prop: str, entity: str = M) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def proj(field: dict, display: str | None = None) -> dict:
    kind = "Measure" if "Measure" in field else "Column"
    entity = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    p = {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}
    if display:
        p["displayName"] = display
    return p


def title_objects(title: str | None, subtitle: str | None = None) -> dict:
    if not title:
        return {"title": [{"properties": {"show": lit(False)}}]}
    props = {"show": lit(True), "text": lit(title)}
    out = {"title": [{"properties": props}]}
    if subtitle:
        out["subTitle"] = [{"properties": {"show": lit(True), "text": lit(subtitle)}}]
    return out


class Page:
    def __init__(self, name: str, display: str, what: str, how: str, notice: str, *, page_type=None,
                 width=W, height=H, hidden=False):
        self.name, self.display = name, display
        self.what, self.how, self.notice = what, how, notice
        self.visuals: list[dict] = []
        self.page_type, self.width, self.height, self.hidden = page_type, width, height, hidden
        self.filters: list[dict] = []
        self.binding = None
        self.z = 0
        if page_type is None:
            self._header()

    def add(self, name: str, vtype: str, x, y, w, h, roles: dict | None = None, *, title=None, subtitle=None,
            objects=None, sort=None, vco_extra=None, drill=True) -> dict:
        self.z += 1000
        visual = {"visualType": vtype}
        if roles:
            state = {}
            for r, projections in roles.items():
                state[r] = {"projections": projections}
                # A field parameter in a role must be declared as such, or the visual treats it as a plain column.
                params = [{"parameterExpr": pr["field"], "index": i, "length": 1} for i, pr in enumerate(projections)
                          if pr["field"].get("Column", {}).get("Expression", {}).get("SourceRef", {}).get("Entity") == "Metric Selector"]
                if params and vtype != "slicer":
                    state[r]["fieldParameters"] = params
            visual["query"] = {"queryState": state}
            if sort:
                visual["query"]["sortDefinition"] = {
                    "sort": [{"field": f, "direction": d} for f, d in sort], "isDefaultSort": True}
        if objects:
            visual["objects"] = objects
        vco = title_objects(title, subtitle)
        if vco_extra:
            vco.update(vco_extra)
        visual["visualContainerObjects"] = vco
        if roles and vtype not in ("slicer", "textbox", "actionButton"):
            visual["drillFilterOtherVisuals"] = drill
        container = {
            "$schema": V_CONTAINER,
            "name": vid(self.name, name),
            "position": {"x": x, "y": y, "z": self.z, "width": w, "height": h, "tabOrder": self.z},
            "visual": visual,
        }
        self.visuals.append(container)
        return container

    def text(self, name: str, x, y, w, h, runs: list[list[tuple[str, dict]]]):
        paragraphs = [{"textRuns": [{"value": v, **({"textStyle": s} if s else {})} for v, s in para]} for para in runs]
        return self.add(name, "textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": paragraphs}}]},
                        vco_extra={"background": [{"properties": {"show": lit(False)}}]})

    def _header(self):
        bold = {"fontWeight": "bold", "color": "#1F4E79", "fontSize": "11pt"}
        body = {"fontSize": "11pt", "color": "#1B2A3A"}
        self.text("header_title", 16, 8, 1248, 40, [[(self.display, {"fontSize": "20pt", "fontWeight": "bold", "color": "#1B2A3A"})]])
        self.text("header_guide", 16, 52, 1248, 74, [
            [("What this is: ", bold), (self.what, body)],
            [("How to use it: ", bold), (self.how, body)],
            [("What to notice: ", bold), (self.notice, body)],
        ])
        self.text("footer", 16, H - 28, 1248, 24, [[(
            "Developed by Reza Azad Gholami  |  " + REPO + "  |  Data: EU MRV (EMSA), Kystverket AIS (NLOD), "
            "Open-Meteo (CC BY 4.0), Ember (CC-BY-4.0)", {"fontSize": "8pt", "color": "#5B6B7F"})]])

    def json(self) -> dict:
        page = {"$schema": V_PAGE, "name": self.name, "displayName": self.display, "displayOption": "FitToPage",
                "height": self.height, "width": self.width}
        if self.filters:
            page["filterConfig"] = {"filters": self.filters}
        if self.binding:
            page["pageBinding"] = self.binding
        if self.page_type:
            page["type"] = self.page_type
        if self.hidden:
            page["visibility"] = "HiddenInViewMode"
        return page


def card(page: Page, name: str, measure: str, x, y, w=232, h=96, label: str | None = None):
    return page.add(name, "card", x, y, w, h, {"Values": [proj(meas(measure), label)]}, title=label or measure,
                    objects={"labels": [{"properties": {"fontSize": lit(24.0)}}],
                             "categoryLabels": [{"properties": {"show": lit(False)}}]})


def slicer(page: Page, name: str, field: dict, x, y, w=232, h=96, title=None, mode="Dropdown", default=None,
           start: float | None = None):
    # The container title names the slicer, so the slicer's own header is hidden.
    objects = {"data": [{"properties": {"mode": lit(mode)}}], "header": [{"properties": {"show": lit(False)}}]}
    if default is not None:
        entity = field["Column"]["Expression"]["SourceRef"]["Entity"]
        prop = field["Column"]["Property"]
        objects["general"] = [{"properties": {"filter": {"filter": {
            "Version": 2,
            "From": [{"Name": "t", "Entity": entity, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": prop}}],
                "Values": [[{"Literal": {"Value": default}}]]}}}],
        }}}}]
    if start is not None:
        # A single-value slider keeps its value as numericStart plus an equality filter (as Desktop saves it).
        entity = field["Column"]["Expression"]["SourceRef"]["Entity"]
        prop = field["Column"]["Property"]
        objects["data"][0]["properties"]["numericStart"] = lit(float(start))
        objects["general"] = [{"properties": {"filter": {"filter": {
            "Version": 2,
            "From": [{"Name": "s", "Entity": entity, "Type": 0}],
            "Where": [{"Condition": {"Comparison": {"ComparisonKind": 0,
                       "Left": {"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": prop}},
                       "Right": {"Literal": {"Value": f"{float(start)}D"}}}}}],
        }}}}]
    return page.add(name, "slicer", x, y, w, h, {"Values": [proj(field)]}, title=title, objects=objects)


def metric_default(page_slicer: dict, measure: str) -> None:
    """Preselect one measure in the field parameter slicer, in the form Power BI Desktop saves it."""
    value = "'" + f"'{M}'[{measure}]".replace("'", "''") + "'"
    fields_col = {"Column": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": "Metric Selector Fields"}}
    page_slicer["visual"]["objects"]["general"] = [{"properties": {"filter": {"filter": {
        "Version": 2,
        "From": [{"Name": "m", "Entity": "Metric Selector", "Type": 0}],
        "Where": [{
            "Condition": {"In": {"Expressions": [fields_col], "Values": [[{"Literal": {"Value": value}}]]}},
            "Annotations": {"filterExpressionMetadata": {
                "expressions": [col("Metric Selector", "Metric Selector")],
                "decomposedIdentities": {"values": [[{"0": [{"Literal": {"Value": value}}]}]],
                                         "columns": [{"value": col("Metric Selector", "Metric Selector Fields")}]},
                "valueMap": [{"0": measure}]}},
        }],
    }}}}]


RATING_COLORS = {"A": "#1c5cab", "B": "#86b6ef", "C": "#c9c8c3", "D": "#f0a09f", "E": "#d03b3b"}


def rating_colors(field: dict) -> list[dict]:
    """Fixed fill per CII rating letter (blue for good, gray in the middle, red for poor)."""
    out = []
    for letter, color in RATING_COLORS.items():
        out.append({"properties": {"fill": {"solid": {"color": lit(color)}}},
                    "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": field,
                                                                      "Right": {"Literal": {"Value": f"'{letter}'"}}}}}]}})
    return out


def not_blank_filter(name: str, entity: str, prop: str) -> dict:
    """Visual-level filter that leaves out blank values of one column."""
    return {"name": name, "field": col(entity, prop), "type": "Advanced", "filter": {
        "Version": 2, "From": [{"Name": "x", "Entity": entity, "Type": 0}],
        "Where": [{"Condition": {"Not": {"Expression": {"Comparison": {"ComparisonKind": 0,
                  "Left": {"Column": {"Expression": {"SourceRef": {"Source": "x"}}, "Property": prop}},
                  "Right": {"Literal": {"Value": "null"}}}}}}}]}}


def segment_filter_def(segment: str) -> dict:
    return {
        "Version": 2,
        "From": [{"Name": "s", "Entity": "Segment", "Type": 0}],
        "Where": [{"Condition": {"In": {
            "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}}, "Property": "Segment"}}],
            "Values": [[{"Literal": {"Value": f"'{segment}'"}}]]}}}],
    }


def build_pages() -> list[Page]:
    seg = col("Segment", "Segment")
    year = col("Ship Year Emissions", "Reporting Year")
    ship = col("Ship", "Ship")
    rating = col("Ship Year Emissions", "CII Rating")
    top = 132
    SH = 66  # slicer height: title plus dropdown
    pages = []

    # 1. Overview
    p = Page("overview", "Fleet overview",
             "Fuel, CO2, EU ETS cost and carbon ratings of ro-ro ships and vehicle carriers that report to the EU MRV system, 2018 to 2025.",
             "Pick a segment or year below, or use the bookmarks (View > Bookmarks). Right-click a ship to open its profile.",
             "CO2 per nautical mile changes slowly, while EU ETS cost jumps in 2024 and 2025 as the scheme phases in.")
    p.filters.append({"name": "overviewSegment", "field": seg, "type": "Categorical"})
    slicer(p, "slicer_segment", seg, 16, top, 300, SH, "Segment")
    slicer(p, "slicer_year", year, 328, top, 300, SH, "Reporting year")
    kt = top + SH + 8
    for i, (m, label) in enumerate([("CO2 (t)", "CO2 emitted (t)"), ("EU ETS Cost (EUR)", "EU ETS cost (EUR)"),
                                    ("CO2 per nm (kg)", "CO2 per nautical mile (kg)"), ("Share Rated D or E", "Rated D or E")]):
        card(p, f"kpi_{i}", m, 16 + i * 314, kt, 302, 84, label)
    ct = kt + 92
    p.add("trend_efficiency", "lineChart", 16, ct, 620, 196,
          {"Category": [proj(year)], "Y": [proj(meas("CO2 per nm (kg)"))], "Series": [proj(seg)]},
          title="CO2 per nautical mile by year", subtitle="Quality-checked ship-years, kg CO2 per nm")
    p.add("trend_ets", "clusteredColumnChart", 648, ct, 616, 196,
          {"Category": [proj(year)], "Y": [proj(meas("EU ETS Cost (EUR)"))], "Series": [proj(seg)]},
          title="EU ETS cost by year", subtitle="Allowances due x average price of the year")
    bt = ct + 204
    v = p.add("ratings_mix", "hundredPercentStackedColumnChart", 16, bt, 620, 684 - bt,
              {"Category": [proj(seg)], "Y": [proj(meas("Rated Ship-Years"))], "Series": [proj(rating)]},
              title="Carbon rating mix", subtitle="Share of rated ship-years, A best to E worst",
              objects={"dataPoint": rating_colors(rating)})
    v["filterConfig"] = {"filters": [not_blank_filter("ratedOnlyOverview", "Ship Year Emissions", "CII Rating")]}
    p.add("top_emitters", "tableEx", 648, bt, 616, 684 - bt,
          {"Values": [proj(ship), proj(col("Ship", "Size Class")), proj(meas("CO2 (t)")), proj(meas("CO2 per nm (kg)")),
                      proj(meas("Variance vs Segment Peers"), "Vs segment")]},
          title="Largest emitters in the selection", sort=[(meas("CO2 (t)"), "Descending")])
    pages.append(p)

    # 2. Fleet efficiency
    p = Page("efficiency", "Fleet efficiency",
             "Each dot is one ship in the selected year: its average speed against its CO2 per nautical mile.",
             "Choose a year, segment and size class. Hover a dot for the ship's summary. Right-click a dot and choose Drill through > Ship profile.",
             "Faster ships burn more fuel per mile. Ships far above the cloud at their speed are the candidates for a closer look.")
    p.filters.append({"name": "efficiencyYear", "field": year, "type": "Categorical", "filter": {
        "Version": 2, "From": [{"Name": "y", "Entity": "Ship Year Emissions", "Type": 0}],
        "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "y"}}, "Property": "Reporting Year"}}],
                                        "Values": [[{"Literal": {"Value": "2025L"}}]]}}}]}})
    slicer(p, "slicer_segment", seg, 16, top, 260, SH, "Segment")
    slicer(p, "slicer_size", col("Ship", "Size Class"), 288, top, 300, SH, "Size class")
    card(p, "kpi_speed", "Average Speed (kn)", 600, top, 210, SH, "Average speed (kn)")
    card(p, "kpi_eff", "CO2 per nm (kg)", 822, top, 210, SH, "CO2 per nm (kg)")
    card(p, "kpi_ships", "Ships Reporting", 1044, top, 220, SH, "Ships")
    ct = top + SH + 8
    p.add("scatter_speed", "scatterChart", 16, ct, 760, 684 - ct,
          {"Category": [proj(ship)], "X": [proj(meas("Average Speed (kn)"))], "Y": [proj(meas("CO2 per nm (kg)"))],
           "Series": [proj(seg)]},
          title="Speed against CO2 per nautical mile", subtitle="One dot per ship; the year is set in the Filters pane (2025 to start)",
          vco_extra={"visualTooltip": [{"properties": {"type": lit("ReportPage"), "section": lit("shiptip")}}]})
    p.add("ranking", "tableEx", 788, ct, 476, 684 - ct,
          {"Values": [proj(ship), proj(meas("Efficiency Rank"), "Rank"), proj(meas("CO2 per nm (kg)")),
                      proj(meas("Variance vs Size-Class Peers"), "Vs size class"), proj(meas("Average Speed (kn)"), "Speed (kn)")]},
          title="Ranking within the selection", subtitle="1 = lowest CO2 per nautical mile",
          sort=[(meas("Efficiency Rank"), "Ascending")])
    pages.append(p)

    # 3. Slow steaming and carbon cost
    p = Page("scenarios", "Slow steaming and carbon cost",
             "A what-if calculator: what a lower speed would save in CO2, fuel cost and EU ETS cost, and what it costs in extra days at sea.",
             "Move the sliders for speed change, carbon price and fuel price, and pick a speed relation. The cards recalculate at once for the selected year and segment.",
             "Annual MRV data show only a weak speed effect (the conservative case). The engineering rule gives the upper reference. The price is time: more days at sea per ship.")
    p.filters.append({"name": "scenarioYear", "field": year, "type": "Categorical", "filter": {
        "Version": 2, "From": [{"Name": "y", "Entity": "Ship Year Emissions", "Type": 0}],
        "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "y"}}, "Property": "Reporting Year"}}],
                                        "Values": [[{"Literal": {"Value": "2025L"}}]]}}}]}})
    WH = 84
    slicer(p, "slicer_speed", col("Speed Change", "Speed Change"), 16, top, 240, WH, "Speed change", mode="Single", start=-0.1)
    slicer(p, "slicer_carbon", col("Carbon Price Scenario", "Carbon Price Scenario"), 266, top, 240, WH, "Carbon price (EUR/t)", mode="Single", start=75)
    slicer(p, "slicer_fuel", col("Fuel Price", "Fuel Price"), 516, top, 240, WH, "Fuel price (EUR/t)", mode="Single", start=550)
    slicer(p, "slicer_relation", col("Speed Relation", "Speed Relation"), 766, top, 300, WH, "Speed relation")
    slicer(p, "slicer_segment", seg, 1076, top, 188, WH, "Segment")
    kt = top + WH + 8
    for i, (m, label) in enumerate([("CO2 Saved (t)", "CO2 saved (t)"), ("Fuel Cost Saved (EUR)", "Fuel cost saved (EUR)"),
                                    ("EU ETS Cost Saved (EUR)", "EU ETS cost saved (EUR)"), ("Extra Days per Ship", "Extra days at sea per ship")]):
        card(p, f"kpi_{i}", m, 16 + i * 314, kt, 302, 84, label)
    ct = kt + 92
    p.add("carbon_price", "lineChart", 16, ct, 620, 684 - ct,
          {"Category": [proj(col("Date", "Month Start"), "Month")], "Y": [proj(meas("Average EUA Price (EUR/t)"))]},
          title="EU ETS allowance price", subtitle="Monthly average, EUR per tonne CO2, 2018 to September 2026")
    p.add("scope", "clusteredBarChart", 648, ct, 616, 684 - ct,
          {"Category": [proj(seg)], "Y": [proj(meas("CO2 (t)"), "CO2 now (t)"), proj(meas("Scenario CO2 (t)"), "CO2 in the scenario (t)")]},
          title="CO2 now and in the scenario", subtitle="Selected year (2025 to start, see the Filters pane)")
    pages.append(p)

    # 4. Carbon ratings
    p = Page("ratings", "Carbon ratings",
             "IMO carbon intensity ratings (CII, A best to E worst) per ship and year, computed from MRV data as an approximation.",
             "Pick a segment. The list on the right shows ships whose rating got worse than the year before.",
             "Required intensity tightens every year, so a ship that does not improve drifts toward D and E.")
    slicer(p, "slicer_segment", seg, 16, top, 232, SH, "Segment")
    card(p, "kpi_de", "Share Rated D or E", 260, top, 232, SH, "Rated D or E")
    card(p, "kpi_ab", "Share Rated A or B", 504, top, 232, SH, "Rated A or B")
    card(p, "kpi_worse", "Ships with Worsening Rating", 748, top, 260, SH, "Ships rated worse")
    card(p, "kpi_ratio", "Average CII Ratio", 1020, top, 244, SH, "Attained / required")
    ct = top + SH + 8
    v = p.add("rating_by_year", "hundredPercentStackedColumnChart", 16, ct, 760, 684 - ct,
              {"Category": [proj(year)], "Y": [proj(meas("Rated Ship-Years"))], "Series": [proj(rating)]},
              title="Rating mix by year", subtitle="Share of rated ship-years",
              objects={"dataPoint": rating_colors(rating)})
    v["filterConfig"] = {"filters": [not_blank_filter("ratedOnly", "Ship Year Emissions", "CII Rating")]}
    p.add("drifting", "tableEx", 788, ct, 476, 684 - ct,
          {"Values": [proj(ship), proj(year), proj(col("Ship Year Emissions", "CII Rating Previous Year"), "Previous"),
                      proj(rating, "Rating")]},
          title="Ships whose rating worsened", sort=[(year, "Descending")])
    p.visuals[-1]["filterConfig"] = {"filters": [{
        "name": "onlyWorse", "field": col("Ship Year Emissions", "Rating Worsened"), "type": "Categorical",
        "filter": {"Version": 2, "From": [{"Name": "f", "Entity": "Ship Year Emissions", "Type": 0}],
                   "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": "Rating Worsened"}}],
                                                    "Values": [[{"Literal": {"Value": "true"}}]]}}}]}}]}
    pages.append(p)

    # 5. Ports and weather
    p = Page("ports", "Ports and weather",
             "Port calls of fleet ships on the Norwegian coast, August and September 2026, found from AIS positions, with wind and waves along each voyage leg.",
             "Click a port in the chart to filter the table and the legs. The scatter shows each voyage leg's speed against the average wind.",
             "Most calls go straight to the quay: anchorage waiting is rare in this liner-style trade. Wind changes leg speed by only a few percent.")
    card(p, "kpi_calls", "Port Calls", 16, top, 232, SH, "Port calls")
    card(p, "kpi_wait", "Share of Calls with Waiting", 260, top, 232, SH, "Calls with waiting")
    card(p, "kpi_berth", "Median Berth Time (h)", 504, top, 232, SH, "Median hours at berth")
    card(p, "kpi_conf", "Calls Confirmed by Kystverket", 748, top, 260, SH, "Confirmed by Kystverket")
    card(p, "kpi_rough", "Rough Weather Share", 1020, top, 244, SH, "Time in rough weather")
    ct = top + SH + 8
    p.add("calls_by_port", "clusteredBarChart", 16, ct, 380, 684 - ct,
          {"Category": [proj(col("Port", "Port"))], "Y": [proj(meas("Port Calls"))]},
          title="Port calls by port", sort=[(meas("Port Calls"), "Descending")])
    p.add("port_table", "tableEx", 408, ct, 440, 684 - ct,
          {"Values": [proj(col("Port", "Port")), proj(meas("Port Calls"), "Calls"), proj(meas("Median Berth Time (h)"), "Median h at berth"),
                      proj(meas("Share of Calls with Waiting"), "Waited")]},
          title="Time in port", sort=[(meas("Port Calls"), "Descending")])
    p.add("legs_weather", "scatterChart", 860, ct, 404, 684 - ct,
          {"Category": [proj(col("Voyage Legs", "voyage_leg_key"))], "X": [proj(meas("Average Wind (m/s)"))], "Y": [proj(meas("Leg Speed (kn)"))]},
          title="Leg speed against wind", subtitle="One dot per voyage leg")
    pages.append(p)

    # 6. Explore (self-service)
    p = Page("explore", "Explore",
             "A self-service page: choose any metric and any time calculation and slice it by segment, size, flag region or design generation.",
             "Pick one metric in the first box and one time calculation (for example Year over Year %) in the second. Edit the report to drag other fields onto the matrix.",
             "The same measures and definitions are used on every page, so numbers here match the other pages.")
    metric_default(slicer(p, "slicer_metric", col("Metric Selector", "Metric Selector"), 16, top, 300, SH, "Metric"), "CO2 per nm (kg)")
    slicer(p, "slicer_time", col("Time Intelligence", "Time Calculation"), 328, top, 300, SH, "Time calculation")
    slicer(p, "slicer_segment", seg, 640, top, 300, SH, "Segment")
    slicer(p, "slicer_region", col("Ship", "Flag Region"), 952, top, 312, SH, "Flag region")
    ct = top + SH + 8
    dyear = col("Date", "Year")
    p.add("matrix", "pivotTable", 16, ct, 760, 684 - ct,
          {"Rows": [proj(col("Ship", "Size Class")), proj(col("Ship", "Design Generation"))], "Columns": [proj(dyear)],
           "Values": [proj(col("Metric Selector", "Metric Selector"))]},
          title="Selected metric by size class, design generation and year")
    p.add("metric_trend", "clusteredColumnChart", 788, ct, 476, 684 - ct,
          {"Category": [proj(dyear)], "Y": [proj(col("Metric Selector", "Metric Selector"))], "Series": [proj(seg)]},
          title="Selected metric by year")
    pages.append(p)

    # 7. Ship profile (drill-through target)
    p = Page("shipprofile", "Ship profile",
             "One pseudonymous ship over time: efficiency, carbon rating and how it compares with ships of the same segment and size.",
             "Reach this page by right-clicking a ship on another page and choosing Drill through > Ship profile. Use the back arrow to return.",
             "A ship with a large positive variance against its size class burns more per mile than its peers at similar size.",
             page_type="Drillthrough")
    p._header()
    p.filters.append({"name": "drillShip", "field": ship, "type": "Categorical", "howCreated": "Drillthrough"})
    # Only the ship flows through, so the profile shows every year of that ship.
    p.binding = {"name": "shipDrill", "type": "Drillthrough", "acceptsFilterContext": "None",
                 "parameters": [{"name": "shipParam", "boundFilter": "drillShip", "fieldExpr": ship}]}
    card(p, "kpi_eff", "CO2 per nm (kg)", 16, top, 300, 80, "CO2 per nm (kg)")
    card(p, "kpi_peer", "Size-Class Peer CO2 per nm (kg)", 328, top, 300, 80, "Size-class peers (kg per nm)")
    card(p, "kpi_var", "Variance vs Size-Class Peers", 640, top, 300, 80, "Variance against peers")
    card(p, "kpi_ets", "EU ETS Cost (EUR)", 952, top, 312, 80, "EU ETS cost (EUR)")
    ct = top + 88
    p.add("ship_trend", "lineChart", 16, ct, 620, 684 - ct,
          {"Category": [proj(year)], "Y": [proj(meas("CO2 per nm (kg)")), proj(meas("Size-Class Peer CO2 per nm (kg)"), "Size-class peers")]},
          title="CO2 per nautical mile against size-class peers")
    p.add("ship_years", "tableEx", 648, ct, 616, 684 - ct,
          {"Values": [proj(year), proj(meas("Average Speed (kn)"), "Speed (kn)"), proj(meas("CO2 (t)")), proj(rating, "Rating"),
                      proj(meas("Average CII Ratio"), "Attained / required")]},
          title="Year by year", sort=[(year, "Ascending")])
    pages.append(p)

    # 8. Ship tooltip (report page tooltip)
    p = Page("shiptip", "Ship tooltip", "", "", "", page_type="Tooltip", width=320, height=240, hidden=True)
    p.binding = {"name": "shipTooltip", "type": "Tooltip", "parameters": []}
    p.add("tip_title", "card", 8, 4, 304, 56, {"Values": [proj(meas("Ship Label"))]}, title=None,
          objects={"labels": [{"properties": {"fontSize": lit(14.0)}}], "categoryLabels": [{"properties": {"show": lit(False)}}]})
    p.add("tip_table", "multiRowCard", 8, 64, 304, 170,
          {"Values": [proj(meas("CO2 per nm (kg)")), proj(meas("Average Speed (kn)")), proj(meas("Variance vs Size-Class Peers")),
                      proj(meas("CO2 (t)"))]}, title=None)
    pages.append(p)
    return pages


def bookmarks(pages: list[Page]) -> list[dict]:
    """Segment views of the overview page, written as Power BI Desktop saves bookmarks (filters by expression)."""
    overview = next(p for p in pages if p.name == "overview")
    table = vid(overview.name, "top_emitters")
    out = []
    for name, display, segment in (("bmAll", "All ships", None), ("bmVehicle", "Vehicle carriers", "Vehicle carrier"),
                                   ("bmRoro", "Ro-ro ships", "Ro-ro ship")):
        state = {"name": "overviewSegment", "type": "Categorical", "expression": col("Segment", "Segment"), "howCreated": 0}
        if segment:
            state["filter"] = segment_filter_def(segment)
        out.append({
            "$schema": SCHEMA + "definition/bookmark/2.0.0/schema.json",
            "displayName": display,
            "name": name,
            "options": {"targetVisualNames": [], "suppressDisplay": True},
            "explorationState": {
                "version": "1.0",
                "activeSection": "overview",
                # The table's sort order is part of the state, so applying a bookmark keeps it.
                "sections": {"overview": {"filters": {"byExpr": [state]}, "visualContainers": {
                    table: {"singleVisual": {"visualType": "tableEx", "objects": {},
                                             "orderBy": [{"Direction": 2, "Expression": meas("CO2 (t)")}]}}}}},
            },
        })
    return out


def write(dest: Path, model_folder: str) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    d = dest / "definition"
    (d / "pages").mkdir(parents=True)
    (dest / "definition.pbir").write_text(json.dumps({
        "$schema": SCHEMA + "definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{model_folder}"}},
    }, indent=2), encoding="utf-8")
    (d / "version.json").write_text(json.dumps({
        "$schema": SCHEMA + "definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2), encoding="utf-8")
    theme_dir = dest / "StaticResources" / "RegisteredResources"
    theme_dir.mkdir(parents=True)
    (theme_dir / "ShippingPerformanceTheme.json").write_text(json.dumps(THEME, indent=2), encoding="utf-8")
    (d / "report.json").write_text(json.dumps({
        "$schema": SCHEMA + "definition/report/3.0.0/schema.json",
        "themeCollection": {"customTheme": {"name": "ShippingPerformanceTheme.json", "reportVersionAtImport": {"visual": "2.4.0", "report": "3.0.0", "page": "2.0.0"}, "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources", "items": [
            {"name": "ShippingPerformanceTheme.json", "path": "ShippingPerformanceTheme.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True},
    }, indent=2), encoding="utf-8")
    pages = build_pages()
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": SCHEMA + "definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name}, indent=2), encoding="utf-8")
    for p in pages:
        pdir = d / "pages" / p.name
        (pdir / "visuals").mkdir(parents=True)
        (pdir / "page.json").write_text(json.dumps(p.json(), indent=2), encoding="utf-8")
        for v in p.visuals:
            vdir = pdir / "visuals" / v["name"]
            vdir.mkdir()
            (vdir / "visual.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
    bms = bookmarks(pages)
    (d / "bookmarks").mkdir()
    for b in bms:
        (d / "bookmarks" / f"{b['name']}.bookmark.json").write_text(json.dumps(b, indent=2), encoding="utf-8")
    (d / "bookmarks" / "bookmarks.json").write_text(json.dumps({
        "$schema": SCHEMA + "definition/bookmarksMetadata/1.0.0/schema.json",
        "items": [{"name": b["name"]} for b in bms]}, indent=2), encoding="utf-8")
    return dest
