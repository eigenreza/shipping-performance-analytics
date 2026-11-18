"""Paginated report (RDL, Power BI Report Builder): printable segment performance.

Parameters: segment and reporting year. Sections: KPI summary against the
previous year, carbon rating mix, the fifteen ships with the highest CO2 per
nautical mile (pseudonymous), and the EU ETS allowance price by month with
the segment's allocated allowance cost.

The data is embedded in the RDL as inline XML (one dataset per section), so
the report runs in Report Builder without any connection. It is regenerated
from the warehouse by ``spa powerbi``.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import duckdb

from spa.paths import ROOT, WAREHOUSE

NS = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
RD = "http://schemas.microsoft.com/SQLServer/reporting/reportdesigner"
OUT = ROOT / "powerbi" / "paginated" / "SegmentPerformance.rdl"
REPO = "github.com/eigenreza/shipping-performance-analytics"
NAVY = "#1F4E79"
YEARS = list(range(2019, 2026))

# Dataset name -> (SQL, [(field, type)])
DATASETS = {
    "Kpi": ("""
        with y as (
            select segment_key as segment, reporting_year as year, sum(co2_t) co2_t, sum(fuel_t) fuel_t,
                   count(distinct ship_key) ships,
                   sum(case when is_quality_ok then co2_t end) * 1000 / sum(case when is_quality_ok then distance_nm end) co2_per_nm,
                   sum(case when is_quality_ok then distance_nm end) / sum(case when is_quality_ok then hours_at_sea end) speed_kn,
                   sum(co2_ets_scope_t) ets_scope_t, sum(ets_cost_eur) ets_cost_eur,
                   avg(case when cii_rating in ('D','E') then 1.0 when cii_rating is not null then 0.0 end) share_de
            from marts.fct_ship_year_emissions group by 1, 2)
        select c.*, p.co2_t prev_co2_t, p.co2_per_nm prev_co2_per_nm, p.speed_kn prev_speed_kn, p.share_de prev_share_de,
               p.ets_cost_eur prev_ets_cost_eur
        from y c left join y p on p.segment = c.segment and p.year = c.year - 1
        where c.year between 2019 and 2025""", None),
    "Ratings": ("""
        select segment_key as segment, reporting_year as year, cii_rating as rating, count(*) as ship_years
        from marts.fct_ship_year_emissions where cii_rating is not null and reporting_year between 2019 and 2025
        group by all""", None),
    "TopShips": ("""
        select * from (
            select f.segment_key as segment, f.reporting_year as year, s.ship_pseudonym as ship, s.size_class,
                   f.co2_kg_per_nm, f.avg_speed_kn as speed_kn, f.co2_t, f.cii_rating as rating,
                   row_number() over (partition by f.segment_key, f.reporting_year order by f.co2_kg_per_nm desc) as rank
            from marts.fct_ship_year_emissions f join marts.dim_ship s using (ship_version_key)
            where f.is_quality_ok and f.reporting_year between 2019 and 2025)
        where rank <= 15""", None),
    "Monthly": ("""
        with m as (
            select year(date_key) as year, month(date_key) as month, strftime(min(date_key), '%b') as month_name,
                   avg(eua_price_eur_per_t) as eua_eur
            from marts.fct_daily_carbon_price where year(date_key) between 2019 and 2025 group by 1, 2),
        s as (
            select segment_key as segment, reporting_year as year, sum(eua_due_t) as eua_due_t
            from marts.fct_ship_year_emissions group by 1, 2)
        select s.segment, m.year, m.month, m.month_name, m.eua_eur, s.eua_due_t / 12 as eua_due_month_t,
               s.eua_due_t / 12 * m.eua_eur as allocated_cost_eur
        from m join s on s.year = m.year""", None),
}


def fetch() -> dict[str, list[dict]]:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        return {name: con.sql(sql).df().to_dict("records") for name, (sql, _) in DATASETS.items()}
    finally:
        con.close()


def xml_data(rows: list[dict]) -> str:
    out = ["<Root>"]
    for r in rows:
        cells = []
        for k, v in r.items():
            if v is None or (isinstance(v, float) and v != v):
                continue
            cells.append(f"<{k}>{escape(str(v))}</{k}>")
        out.append("<Row>" + "".join(cells) + "</Row>")
    out.append("</Root>")
    return "".join(out)


def dataset(name: str, rows: list[dict], filters: list[str]) -> str:
    fields = "".join(f'<Field Name="{k}"><DataField>{k}</DataField></Field>' for k in rows[0].keys())
    query = escape(f"<Query><ElementPath IgnoreNamespaces=\"true\">Root{{}}/Row</ElementPath><XmlData>{xml_data(rows)}</XmlData></Query>")
    flt = "".join(
        f"<Filter><FilterExpression>=Fields!{f}.Value</FilterExpression><Operator>Equal</Operator>"
        f"<FilterValues><FilterValue>=CStr(Parameters!{'Segment' if f == 'segment' else 'Year'}.Value)</FilterValue></FilterValues></Filter>"
        for f in filters)
    return (f'<DataSet Name="{name}"><Query><DataSourceName>EmbeddedData</DataSourceName><CommandText>{query}</CommandText></Query>'
            f"<Fields>{fields}</Fields>" + (f"<Filters>{flt}</Filters>" if flt else "") + "</DataSet>")


def textbox(name: str, value: str, top: float, left: float, width: float, height: float, *, size="10pt", bold=False,
            color="#1B2A3A", align="Left", fmt: str | None = None, bg: str | None = None) -> str:
    style = f"<FontFamily>Segoe UI</FontFamily><FontSize>{size}</FontSize><Color>{color}</Color>"
    if bold:
        style += "<FontWeight>Bold</FontWeight>"
    if fmt:
        style += f"<Format>{escape(fmt)}</Format>"
    box = f"<Style><PaddingLeft>2pt</PaddingLeft><PaddingRight>2pt</PaddingRight><PaddingTop>1pt</PaddingTop><PaddingBottom>1pt</PaddingBottom>{f'<BackgroundColor>{bg}</BackgroundColor>' if bg else ''}</Style>"
    return (f'<Textbox Name="{name}"><CanGrow>true</CanGrow><KeepTogether>true</KeepTogether><Paragraphs><Paragraph>'
            f"<TextRuns><TextRun><Value>{escape(value)}</Value><Style>{style}</Style></TextRun></TextRuns>"
            f"<Style><TextAlign>{align}</TextAlign></Style></Paragraph></Paragraphs>"
            f"<Top>{top}cm</Top><Left>{left}cm</Left><Height>{height}cm</Height><Width>{width}cm</Width>{box}</Textbox>")


def cell(name: str, value: str, *, header=False, fmt=None, align="Left") -> str:
    color = "#FFFFFF" if header else "#1B2A3A"
    bg = NAVY if header else None
    style = f"<FontFamily>Segoe UI</FontFamily><FontSize>{'9pt' if header else '9pt'}</FontSize><Color>{color}</Color>"
    if header:
        style += "<FontWeight>Bold</FontWeight>"
    if fmt:
        style += f"<Format>{escape(fmt)}</Format>"
    border = "<Border><Color>#D5DCE4</Color><Style>Solid</Style></Border>"
    return (f'<TablixCell><CellContents><Textbox Name="{name}"><CanGrow>true</CanGrow>'
            f"<Paragraphs><Paragraph><TextRuns><TextRun><Value>{escape(value)}</Value><Style>{style}</Style></TextRun></TextRuns>"
            f"<Style><TextAlign>{align}</TextAlign></Style></Paragraph></Paragraphs>"
            f"<Style>{border}{f'<BackgroundColor>{bg}</BackgroundColor>' if bg else ''}<PaddingLeft>3pt</PaddingLeft><PaddingRight>3pt</PaddingRight>"
            f"<PaddingTop>2pt</PaddingTop><PaddingBottom>2pt</PaddingBottom></Style></Textbox></CellContents></TablixCell>")


def tablix(name: str, ds: str, cols: list[tuple[str, str, float, str | None, str]], top: float, left: float,
           sort: str | None = None) -> str:
    """cols: (header, value expression, width cm, format, align)."""
    columns = "".join(f"<TablixColumn><Width>{w}cm</Width></TablixColumn>" for _, _, w, _, _ in cols)
    header = "".join(cell(f"{name}_h{i}", h, header=True, align=a) for i, (h, _, _, _, a) in enumerate(cols))
    detail = "".join(cell(f"{name}_d{i}", v, fmt=f, align=a) for i, (_, v, _, f, a) in enumerate(cols))
    width = sum(c[2] for c in cols)
    sort_xml = f"<SortExpressions><SortExpression><Value>{escape(sort)}</Value></SortExpression></SortExpressions>" if sort else ""
    return (f'<Tablix Name="{name}"><TablixBody><TablixColumns>{columns}</TablixColumns><TablixRows>'
            f"<TablixRow><Height>0.6cm</Height><TablixCells>{header}</TablixCells></TablixRow>"
            f"<TablixRow><Height>0.5cm</Height><TablixCells>{detail}</TablixCells></TablixRow></TablixRows></TablixBody>"
            f"<TablixColumnHierarchy><TablixMembers>{'<TablixMember />' * len(cols)}</TablixMembers></TablixColumnHierarchy>"
            f"<TablixRowHierarchy><TablixMembers><TablixMember><KeepWithGroup>After</KeepWithGroup><RepeatOnNewPage>true</RepeatOnNewPage></TablixMember>"
            f'<TablixMember><Group Name="{name}_Details" />{sort_xml}</TablixMember></TablixMembers></TablixRowHierarchy>'
            f"<DataSetName>{ds}</DataSetName><Top>{top}cm</Top><Left>{left}cm</Left><Height>1.15cm</Height><Width>{width}cm</Width>"
            "<Style><Border><Style>None</Style></Border></Style></Tablix>")


def rectangle(name: str, items: list[str], top: float, left: float, width: float, height: float) -> str:
    """Container: items inside grow without pushing items in other containers."""
    return (f'<Rectangle Name="{name}"><ReportItems>{"".join(items)}</ReportItems>'
            f"<Top>{top}cm</Top><Left>{left}cm</Left><Height>{height}cm</Height><Width>{width}cm</Width><Style /></Rectangle>")


def kpi_block(top: float) -> str:
    items = [
        ("CO2 emitted (t)", "=Sum(CDbl(Fields!co2_t.Value), \"Kpi\")", "#,0", "prev_co2_t", "co2_t"),
        ("CO2 per nautical mile (kg)", "=Sum(CDbl(Fields!co2_per_nm.Value), \"Kpi\")", "#,0.0", "prev_co2_per_nm", "co2_per_nm"),
        ("Average speed (kn)", "=Sum(CDbl(Fields!speed_kn.Value), \"Kpi\")", "#,0.0", "prev_speed_kn", "speed_kn"),
        ("Rated D or E", "=Sum(CDbl(Fields!share_de.Value), \"Kpi\")", "0.0%", "prev_share_de", "share_de"),
        ("EU ETS cost (EUR)", "=Sum(CDbl(Fields!ets_cost_eur.Value), \"Kpi\")", "#,0", "prev_ets_cost_eur", "ets_cost_eur"),
    ]
    out, w = [], 5.3
    for i, (label, expr, fmt, prev, cur) in enumerate(items):
        left = 0.5 + i * (w + 0.25)
        out.append(textbox(f"kpiLabel{i}", label, top, left, w, 0.55, size="8.5pt", color="#5B6B7F", bg="#EEF2F7"))
        out.append(textbox(f"kpiValue{i}", expr, top + 0.55, left, w, 0.9, size="17pt", bold=True, color=NAVY, fmt=fmt, bg="#EEF2F7"))
        if fmt.endswith("%"):
            change = (f'Format((Sum(CDbl(Fields!{cur}.Value), "Kpi") - CDbl(First(Fields!{prev}.Value, "Kpi"))) * 100, "+0.0;-0.0;0.0")'
                      ' & " percentage points"')
        else:
            change = (f'Format(Sum(CDbl(Fields!{cur}.Value), "Kpi") / CDbl(First(Fields!{prev}.Value, "Kpi")) - 1, "+0.0%;-0.0%;0.0%")')
        delta = (f'=IIF(IsNothing(First(Fields!{prev}.Value, "Kpi")), "No previous year", IIF(CDbl(First(Fields!{prev}.Value, "Kpi")) = 0, '
                 f'"None in the previous year", "vs previous year: " & {change}))')
        out.append(textbox(f"kpiDelta{i}", delta, top + 1.45, left, w, 0.5, size="8pt", color="#5B6B7F", bg="#EEF2F7"))
    return "".join(out)


def build() -> Path:
    data = fetch()
    segments = sorted({r["segment"] for r in data["Kpi"]})
    params = (
        '<ReportParameters><ReportParameter Name="Segment"><DataType>String</DataType>'
        '<DefaultValue><Values><Value>Vehicle carrier</Value></Values></DefaultValue><Prompt>Segment</Prompt>'
        "<ValidValues><ParameterValues>"
        + "".join(f"<ParameterValue><Value>{s}</Value><Label>{s}</Label></ParameterValue>" for s in segments)
        + "</ParameterValues></ValidValues></ReportParameter>"
        '<ReportParameter Name="Year"><DataType>Integer</DataType><DefaultValue><Values><Value>2025</Value></Values></DefaultValue>'
        "<Prompt>Reporting year</Prompt><ValidValues><ParameterValues>"
        + "".join(f"<ParameterValue><Value>{y}</Value><Label>{y}</Label></ParameterValue>" for y in YEARS)
        + "</ParameterValues></ValidValues></ReportParameter></ReportParameters>"
        "<ReportParametersLayout><GridLayoutDefinition><NumberOfColumns>2</NumberOfColumns><NumberOfRows>1</NumberOfRows>"
        "<CellDefinitions><CellDefinition><ColumnIndex>0</ColumnIndex><RowIndex>0</RowIndex><ParameterName>Segment</ParameterName></CellDefinition>"
        "<CellDefinition><ColumnIndex>1</ColumnIndex><RowIndex>0</RowIndex><ParameterName>Year</ParameterName></CellDefinition>"
        "</CellDefinitions></GridLayoutDefinition></ReportParametersLayout>"
    )
    datasets = (dataset("Kpi", data["Kpi"], ["segment", "year"]) + dataset("Ratings", data["Ratings"], ["segment", "year"])
                + dataset("TopShips", data["TopShips"], ["segment", "year"]) + dataset("Monthly", data["Monthly"], ["segment", "year"]))
    body = []
    body.append(textbox("intro", "What this is: a printable summary of one fleet segment for one EU MRV reporting year. "
                        "How to use it: pick the segment and the year at the top and press View Report. "
                        "What to notice: the change against the previous year, the rating mix, and which ships burn the most per mile.",
                        0.2, 0.5, 27.4, 1.0, size="9pt", color="#3D4F63"))
    body.append(kpi_block(1.4))
    left_items, right_items = [], []
    left_items.append(textbox("ratingsTitle", "Carbon rating mix (CII, A best to E worst)", 0, 0, 9.3, 0.6, size="11pt", bold=True))
    left_items.append(tablix("tblRatings", "Ratings", [
        ("Rating", "=Fields!rating.Value", 3.0, None, "Center"),
        ("Ship-years", "=CDbl(Fields!ship_years.Value)", 3.0, "#,0", "Right"),
        ("Share", "=CDbl(Fields!ship_years.Value) / Sum(CDbl(Fields!ship_years.Value), \"Ratings\")", 2.5, "0.0%", "Right")],
        0.7, 0, sort="=Fields!rating.Value"))
    left_items.append(textbox("monthlyTitle", "EU ETS price and allowance cost by month", 2.25, 0, 9.3, 0.6, size="11pt", bold=True))
    left_items.append(tablix("tblMonthly", "Monthly", [
        ("Month", "=Fields!month_name.Value", 1.4, None, "Left"),
        ("EUA EUR/t", "=CDbl(Fields!eua_eur.Value)", 2.2, "#,0.00", "Right"),
        ("Allowances (t)", "=CDbl(Fields!eua_due_month_t.Value)", 2.6, "#,0", "Right"),
        ("Cost (EUR)", "=CDbl(Fields!allocated_cost_eur.Value)", 3.0, "#,0", "Right")],
        2.95, 0, sort="=CInt(Fields!month.Value)"))
    right_items.append(textbox("shipsTitle", "Fifteen ships with the highest CO2 per nautical mile", 0, 0, 17.9, 0.6, size="11pt", bold=True))
    right_items.append(tablix("tblTopShips", "TopShips", [
        ("#", "=CInt(Fields!rank.Value)", 0.8, "0", "Right"),
        ("Ship", "=Fields!ship.Value", 2.6, None, "Left"),
        ("Size class", "=Fields!size_class.Value", 5.4, None, "Left"),
        ("CO2 per nm (kg)", "=CDbl(Fields!co2_kg_per_nm.Value)", 2.6, "#,0.0", "Right"),
        ("Speed (kn)", "=CDbl(Fields!speed_kn.Value)", 2.0, "#,0.0", "Right"),
        ("CO2 (t)", "=CDbl(Fields!co2_t.Value)", 2.4, "#,0", "Right"),
        ("CII", "=Fields!rating.Value", 1.2, None, "Center")],
        0.7, 0, sort="=CInt(Fields!rank.Value)"))
    right_items.append(textbox("notes", "Notes: CO2 per nautical mile and speed use ship-years that pass the plausibility checks. "
                        "CII ratings are an approximation computed from MRV data. Allowance cost is the year's allowances due, "
                        "spread evenly over the months, at each month's average EU ETS price. Shipping entered the EU ETS in 2024, so earlier years show no cost. "
                        "Ships are shown under pseudonyms.",
                        2.3, 0, 17.9, 1.4, size="8pt", color="#5B6B7F"))
    body.append(rectangle("leftColumn", left_items, 3.7, 0.5, 9.3, 4.1))
    body.append(rectangle("rightColumn", right_items, 3.7, 10.0, 17.9, 3.8))
    header = (
        "<PageHeader><Height>1.6cm</Height><PrintOnFirstPage>true</PrintOnFirstPage><PrintOnLastPage>true</PrintOnLastPage><ReportItems>"
        + textbox("title", "Segment performance report", 0.2, 0.5, 16.0, 0.8, size="16pt", bold=True)
        + textbox("subtitle", '=Parameters!Segment.Value & ", EU MRV reporting year " & CStr(Parameters!Year.Value)', 0.95, 0.5, 16.0, 0.6,
                  size="10pt", color="#5B6B7F")
        + textbox("source", "Shipping performance analytics: vehicle carriers and ro-ro ships", 0.35, 17.0, 10.9, 0.6, size="8pt",
                  color="#5B6B7F", align="Right")
        + "</ReportItems><Style><BottomBorder><Color>#1F4E79</Color><Style>Solid</Style><Width>1.5pt</Width></BottomBorder></Style></PageHeader>"
    )
    footer = (
        "<PageFooter><Height>0.8cm</Height><PrintOnFirstPage>true</PrintOnFirstPage><PrintOnLastPage>true</PrintOnLastPage><ReportItems>"
        + textbox("footer", f"Developed by Reza Azad Gholami  |  {REPO}  |  Data: EU MRV (EMSA), Ember (CC-BY-4.0)", 0.15, 0.5, 20.0, 0.5,
                  size="7.5pt", color="#5B6B7F")
        + textbox("page", '="Page " & Globals!PageNumber & " of " & Globals!TotalPages', 0.15, 21.0, 6.9, 0.5, size="7.5pt",
                  color="#5B6B7F", align="Right")
        + "</ReportItems><Style /></PageFooter>"
    )
    rdl = (
        f'<?xml version="1.0" encoding="utf-8"?>\n<Report xmlns="{NS}" xmlns:rd="{RD}">'
        "<AutoRefresh>0</AutoRefresh>"
        '<DataSources><DataSource Name="EmbeddedData"><ConnectionProperties><DataProvider>XML</DataProvider>'
        "<ConnectString /></ConnectionProperties></DataSource></DataSources>"
        f"<DataSets>{datasets}</DataSets>"
        "<ReportSections><ReportSection>"
        f"<Body><ReportItems>{''.join(body)}</ReportItems><Height>7.9cm</Height><Style /></Body>"
        "<Width>28.4cm</Width>"
        f"<Page>{header}{footer}<PageHeight>21cm</PageHeight><PageWidth>29.7cm</PageWidth><LeftMargin>0.6cm</LeftMargin>"
        "<RightMargin>0.6cm</RightMargin><TopMargin>0.6cm</TopMargin><BottomMargin>0.6cm</BottomMargin><Style /></Page>"
        "</ReportSection></ReportSections>"
        f"{params}"
        "<Language>en-US</Language><ConsumeContainerWhitespace>true</ConsumeContainerWhitespace>"
        "<rd:ReportUnitType>Cm</rd:ReportUnitType><rd:ReportID>5c3b1e8a-2f4d-4a7b-9c61-0d2e8f7a1b44</rd:ReportID>"
        "</Report>\n"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(rdl, encoding="utf-8")
    return OUT


def validate(path: Path = OUT, xsd: Path = ROOT / "tools" / "powerbi" / "schemas" / "rdl" / "reportdefinition.xsd") -> list[str]:
    from lxml import etree

    schema = etree.XMLSchema(etree.parse(str(xsd)))
    doc = etree.parse(str(path))
    if schema.validate(doc):
        return []
    return [f"line {e.line}: {e.message}" for e in schema.error_log]


if __name__ == "__main__":
    p = build()
    errs = validate(p)
    print(f"{p.relative_to(ROOT)}: {p.stat().st_size / 1024:.0f} KB, {len(errs)} schema errors")
    for e in errs[:30]:
        print(e)
