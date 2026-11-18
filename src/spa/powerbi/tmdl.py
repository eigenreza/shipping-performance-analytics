"""Write the semantic model as TMDL (Tabular Model Definition Language).

The output goes to a staging folder. ``tools/powerbi/normalize_tmdl.ps1``
then loads it with Microsoft's TOM library (strict validation) and writes it
back in the canonical layout that Power BI Desktop produces.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from pathlib import Path

import pyarrow.parquet as pq

from spa.paths import EXPORTS
from spa.powerbi import spec

NS = uuid.UUID("6f1c2a52-3b0e-4f43-9a51-5e1c9e3a0b11")
MEASURE_TABLE = "Metrics"
GITHUB_DATA = "https://raw.githubusercontent.com/eigenreza/shipping-performance-analytics/main/data/exports/gold"


def tag(*parts: str) -> str:
    """Deterministic lineage tag so regenerated files do not churn."""
    return str(uuid.uuid5(NS, "/".join(parts)))


def q(name: str) -> str:
    """Quote a TMDL object name when needed."""
    if name.replace("_", "").isalnum() and not name[0].isdigit():
        return name
    return "'" + name.replace("'", "''") + "'"


def desc(text: str | None, indent: str) -> list[str]:
    return [f"{indent}/// {line}" for line in (text or "").splitlines() if line.strip()]


def expr_block(expr: str, indent: str) -> list[str]:
    return [f"{indent}{line}" for line in expr.strip().splitlines()]


def ignore(*rule_ids: str, indent: str = "\t") -> list[str]:
    """Annotation that tells the Best Practice Analyzer a rule is a documented exception here."""
    return [f'{indent}annotation BestPracticeAnalyzer_IgnoreRules = {json.dumps({"RuleIDs": list(rule_ids)})}', ""]


def report_columns() -> set[tuple[str, str]]:
    """(table, column) pairs that report visuals use, read from the report generator."""
    src = (Path(__file__).parent / "report.py").read_text(encoding="utf-8")
    return set(re.findall(r'col\("([^"]+)", "([^"]+)"\)', src))


def measure_refs() -> set[tuple[str, str]]:
    refs = set()
    exprs = [m.expr for m in spec.MEASURES] + [e for _, e, _ in spec.TIME_INTELLIGENCE]
    for e in exprs:
        for t1, t2, c in re.findall(r"(?:'([^']+)'|([A-Za-z_][A-Za-z0-9_ ]*?))\[([^\]]+)\]", e):
            refs.add(((t1 or t2).strip(), c))
    return refs


def needed_columns(t: spec.Table) -> set[str]:
    """Source columns the model needs: listed, related, referenced by measures or visuals."""
    need = {c.source for c in t.columns}
    for ft, fc, tt, tc, _ in spec.RELATIONSHIPS:
        if ft == t.name:
            need.add(fc)
        if tt == t.name:
            need.add(tc)
    names = {(c.name or c.source): c.source for c in t.columns}
    for table, col in measure_refs() | report_columns():
        if table == t.name:
            need.add(names.get(col, col))
    return need


def arrow_type(t) -> tuple[str, str | None]:
    s = str(t)
    if s.startswith("int") or s.startswith("uint"):
        return "int64", "0"
    if s in ("double", "float") or s.startswith("decimal"):
        return "decimal", None
    if s == "bool":
        return "boolean", None
    if s.startswith("date32"):
        return "dateTime", "Long Date"
    if s.startswith("timestamp"):
        return "dateTime", "General Date"
    return "string", None


def translate(expr: str) -> str:
    """Rewrite Table[source_column] references to the column's friendly name."""
    for t in spec.TABLES:
        for c in t.columns:
            if c.name and c.name != c.source:
                for tq in {q(t.name), f"'{t.name}'"}:
                    expr = expr.replace(f"{tq}[{c.source}]", f"{tq}[{c.name}]")
    return expr


def measure_lines(m: spec.Measure, table: str) -> list[str]:
    m = spec.Measure(m.name, translate(m.expr), m.fmt, m.folder, m.desc)
    out = desc(m.desc, "\t")
    lines = m.expr.strip().splitlines()
    if len(lines) == 1:
        out.append(f"\tmeasure {q(m.name)} = {lines[0]}")
    else:
        out.append(f"\tmeasure {q(m.name)} =")
        out += expr_block(m.expr, "\t\t\t")
    if m.fmt:
        out.append(f"\t\tformatString: {m.fmt}")
    out.append(f"\t\tdisplayFolder: {m.folder}")
    out.append(f"\t\tlineageTag: {tag('measure', m.name)}")
    out.append("")
    if m.name in spec.RATIO_MEASURES:
        out += ignore("INTEGER_FORMATTING", "PROVIDE_FORMAT_STRING_FOR_MEASURES", indent="\t\t")
    return out


def column_lines(name: str, source: str, dtype: str, *, hidden=False, fmt=None, description=None,
                 sort_by=None, summarize="none", category=None, is_key=False, table="", sort_targets=(),
                 ignore_rules=()) -> list[str]:
    out = desc(description, "\t")
    out.append(f"\tcolumn {q(name)}")
    out.append(f"\t\tdataType: {dtype}")
    if is_key:
        out.append("\t\tisKey")
    if hidden:
        out.append("\t\tisHidden")
        if name not in sort_targets and not sort_by:
            out.append("\t\tisAvailableInMdx: false")
    if fmt:
        out.append(f"\t\tformatString: {fmt}")
    if category:
        out.append(f"\t\tdataCategory: {category}")
    out.append(f"\t\tlineageTag: {tag('column', table, name)}")
    out.append(f"\t\tsummarizeBy: {summarize}")
    out.append(f"\t\tsourceColumn: {source}")
    if sort_by:
        out.append(f"\t\tsortByColumn: {q(sort_by)}")
    out.append("")
    out.append("\t\tannotation SummarizationSetBy = Automatic")
    out.append("")
    if ignore_rules:
        out += ignore(*ignore_rules, indent="\t\t")
    return out


PRIMARY_KEYS = {"Ship": "ship_version_key", "Segment": "segment_id", "Port": "port_id", "Date": "date_key"}
DISCONNECTED = {"Model Parameters"}


def import_table(t: spec.Table) -> str:
    schema = pq.read_schema(EXPORTS / "gold" / t.file)
    listed = {c.source: c for c in t.columns}
    taken = {(c.name or c.source).lower() for c in t.columns}
    need = needed_columns(t)
    sort_targets = {c.sort_by for c in t.columns if c.sort_by}
    out = desc(t.desc, "")
    out.append(f"table {q(t.name)}")
    if t.name == "Date":
        out.append("\tdataCategory: Time")
    out.append(f"\tlineageTag: {tag('table', t.name)}")
    out.append("")
    kept, decimals, ints = [], [], []
    for name, typ in zip(schema.names, schema.types, strict=True):
        if name not in need:
            continue
        kept.append(name)
        dtype, default_fmt = arrow_type(typ)
        if dtype == "decimal":
            decimals.append(name)
        elif dtype == "int64":
            ints.append(name)
        c = listed.get(name)
        if c is None:
            col_name = name if name.lower() not in taken else f"{name}_raw"
            report_only = (t.name, name) in report_columns() and (t.name, name) not in measure_refs()
            out += column_lines(col_name, name, dtype, hidden=t.hide_unlisted,
                                fmt=default_fmt if dtype == "dateTime" else ("#,0" if dtype == "int64" else None),
                                summarize="none", table=t.name, sort_targets=sort_targets,
                                ignore_rules=("UNNECESSARY_COLUMNS",) if report_only else ())
            continue
        out += column_lines(
            c.name or c.source, c.source, dtype, hidden=c.hidden, fmt=c.fmt or default_fmt,
            description=c.desc, sort_by=c.sort_by, summarize=c.summarize, category=c.category,
            is_key=PRIMARY_KEYS.get(t.name) == c.source, table=t.name, sort_targets=sort_targets,
        )
    types = ", ".join([f'{{"{n}", Currency.Type}}' for n in decimals] + [f'{{"{n}", Int64.Type}}' for n in ints])
    select = ", ".join(f'"{n}"' for n in kept)
    out.append(f"\tpartition {q(t.name)} = m")
    out.append("\t\tmode: import")
    out.append("\t\tsource =")
    steps = [f'    Source = Parquet.Document(GoldFile("{t.file}")),',
             f"    Selected = Table.SelectColumns(Source, {{{select}}})"]
    last = "Selected"
    if types:
        steps[-1] += ","
        steps.append(f"    Typed = Table.TransformColumnTypes(Selected, {{{types}}})")
        last = "Typed"
    out += expr_block("\n".join(["let"] + steps + ["in", f"    {last}"]), "\t\t\t\t")
    out.append("")
    out.append("\tannotation PBI_ResultType = Table")
    out.append("")
    if t.name in DISCONNECTED:
        out += ignore("ENSURE_TABLES_HAVE_RELATIONSHIPS")
    return "\n".join(out)


def measures_table() -> str:
    out = ["/// Home table for the report's measures, grouped in display folders."]
    out.append(f"table {MEASURE_TABLE}")
    out.append(f"\tlineageTag: {tag('table', MEASURE_TABLE)}")
    out.append("")
    for m in spec.MEASURES:
        out += measure_lines(m, MEASURE_TABLE)
    out += column_lines("Placeholder", "Placeholder", "string", hidden=True, table=MEASURE_TABLE,
                        ignore_rules=("UNNECESSARY_COLUMNS",))
    out.append(f"\tpartition {MEASURE_TABLE} = m")
    out.append("\t\tmode: import")
    out.append("\t\tsource = #table(type table [Placeholder = text], {})")
    out.append("")
    out.append("\tannotation PBI_ResultType = Table")
    out.append("")
    out += ignore("ENSURE_TABLES_HAVE_RELATIONSHIPS")
    return "\n".join(out)


def what_if_table(name, lo, hi, step, default, fmt, description) -> str:
    out = desc(description, "")
    out.append(f"table {q(name)}")
    out.append(f"\tlineageTag: {tag('table', name)}")
    out.append("")
    out += measure_lines(spec.Measure(f"{name} Value", f"SELECTEDVALUE({q(name)}[{name}], {default})", fmt, "Scenarios",
                                      f"Value chosen with the {name} parameter (default {default})."), name)
    out.append(f"\tcolumn {q(name)}")
    out.append("\t\tdataType: decimal")
    out.append(f"\t\tformatString: {fmt}")
    out.append(f"\t\tlineageTag: {tag('column', name, name)}")
    out.append("\t\tsummarizeBy: none")
    out.append("\t\tsourceColumn: [Value]")
    out.append("")
    out.append("\t\textendedProperty ParameterMetadata =")
    out.append("\t\t\t\t{")
    out.append('\t\t\t\t  "version": 0')
    out.append("\t\t\t\t}")
    out.append("")
    out.append("\t\tannotation SummarizationSetBy = User")
    out.append("")
    out.append(f"\tpartition {q(name)} = calculated")
    out.append("\t\tmode: import")
    out.append(f"\t\tsource = GENERATESERIES(CURRENCY({lo}), CURRENCY({hi}), CURRENCY({step}))")
    out.append("")
    out += ignore("ENSURE_TABLES_HAVE_RELATIONSHIPS", "REDUCE_USAGE_OF_CALCULATED_TABLES")
    return "\n".join(out)


def speed_relation_table() -> str:
    name = "Speed Relation"
    out = ["/// Choice of speed relation for the slow steaming scenarios: estimated from MRV data, or the engineering rule."]
    out.append(f"table {q(name)}")
    out.append(f"\tlineageTag: {tag('table', name)}")
    out.append("")
    for col_name, src, dtype, hidden in (("Speed Relation", "[Value1]", "string", False), ("Parameter Key", "[Value2]", "string", True),
                                         ("Speed Relation Order", "[Value3]", "int64", True)):
        out += column_lines(col_name, src, dtype, hidden=hidden, table=name,
                            sort_by="Speed Relation Order" if col_name == "Speed Relation" else None,
                            fmt="0" if dtype == "int64" else None, sort_targets=("Speed Relation Order",))
    out.append(f"\tpartition {q(name)} = calculated")
    out.append("\t\tmode: import")
    out.append("\t\tsource =")
    rows = '{\n    ("Estimated from MRV data", "speed_elasticity_mrv", 1),\n    ("Engineering rule (fuel per mile ~ speed squared)", "speed_elasticity_engineering", 2)\n}'
    out += expr_block(rows, "\t\t\t\t")
    out.append("")
    out += ignore("ENSURE_TABLES_HAVE_RELATIONSHIPS", "REDUCE_USAGE_OF_CALCULATED_TABLES")
    return "\n".join(out)


def field_parameter() -> str:
    name = "Metric Selector"
    out = ["/// Field parameter: lets the reader pick which metric a visual shows."]
    out.append(f"table {q(name)}")
    out.append(f"\tlineageTag: {tag('table', name)}")
    out.append("")
    out.append(f"\tcolumn {q(name)}")
    out.append("\t\tdataType: string")
    out.append(f"\t\tlineageTag: {tag('column', name, name)}")
    out.append("\t\tsummarizeBy: none")
    out.append("\t\tsourceColumn: [Value1]")
    out.append(f"\t\tsortByColumn: {q(name + ' Order')}")
    out.append("")
    out.append("\t\trelatedColumnDetails")
    out.append(f"\t\t\tgroupByColumn: {q(name + ' Fields')}")
    out.append("")
    out.append("\t\tannotation SummarizationSetBy = Automatic")
    out.append("")
    out.append(f"\tcolumn {q(name + ' Fields')}")
    out.append("\t\tdataType: string")
    out.append("\t\tisHidden")
    out.append(f"\t\tlineageTag: {tag('column', name, 'fields')}")
    out.append("\t\tsummarizeBy: none")
    out.append("\t\tsourceColumn: [Value2]")
    out.append(f"\t\tsortByColumn: {q(name + ' Order')}")
    out.append("")
    out.append("\t\textendedProperty ParameterMetadata =")
    out.append("\t\t\t\t{")
    out.append('\t\t\t\t  "version": 3,')
    out.append('\t\t\t\t  "kind": 2')
    out.append("\t\t\t\t}")
    out.append("")
    out.append("\t\tannotation SummarizationSetBy = Automatic")
    out.append("")
    out += ignore("UNNECESSARY_COLUMNS", indent="\t\t")
    out.append(f"\tcolumn {q(name + ' Order')}")
    out.append("\t\tdataType: int64")
    out.append("\t\tisHidden")
    out.append("\t\tformatString: 0")
    out.append(f"\t\tlineageTag: {tag('column', name, 'order')}")
    out.append("\t\tsummarizeBy: sum")
    out.append("\t\tsourceColumn: [Value3]")
    out.append("")
    out.append("\t\tannotation SummarizationSetBy = Automatic")
    out.append("")
    rows = ",\n".join(
        f'    ("{m}", NAMEOF({MEASURE_TABLE}[{m}]), {i})' for i, m in enumerate(spec.FIELD_PARAMETER)
    )
    out.append(f"\tpartition {q(name)} = calculated")
    out.append("\t\tmode: import")
    out.append("\t\tsource =")
    out += expr_block("{\n" + rows + "\n}", "\t\t\t\t")
    out.append("")
    out += ignore("ENSURE_TABLES_HAVE_RELATIONSHIPS", "REDUCE_USAGE_OF_CALCULATED_TABLES", "DAX_MEASURES_UNQUALIFIED")
    return "\n".join(out)


def calculation_group() -> str:
    name = "Time Intelligence"
    out = ["/// Calculation group: applies year to date, prior year, year over year and rolling 12 months to any measure."]
    out.append(f"table {q(name)}")
    out.append(f"\tlineageTag: {tag('table', name)}")
    out.append("")
    out.append("\tcalculationGroup")
    out.append("\t\tprecedence: 10")
    out.append("")
    for i, (item, expr, fmt) in enumerate(spec.TIME_INTELLIGENCE):
        out.append(f"\t\tcalculationItem {q(item)} = {expr}")
        out.append(f"\t\t\tordinal: {i}")
        if fmt:
            out.append(f"\t\t\tformatStringDefinition = {fmt}")
        out.append("")
    out.append("\tcolumn 'Time Calculation'")
    out.append("\t\tdataType: string")
    out.append(f"\t\tlineageTag: {tag('column', name, 'name')}")
    out.append("\t\tsummarizeBy: none")
    out.append("\t\tsourceColumn: Name")
    out.append("\t\tsortByColumn: Ordinal")
    out.append("")
    out.append("\t\tannotation SummarizationSetBy = Automatic")
    out.append("")
    out.append("\tcolumn Ordinal")
    out.append("\t\tdataType: int64")
    out.append("\t\tisHidden")
    out.append("\t\tformatString: 0")
    out.append(f"\t\tlineageTag: {tag('column', name, 'ordinal')}")
    out.append("\t\tsummarizeBy: sum")
    out.append("\t\tsourceColumn: Ordinal")
    out.append("")
    out.append("\t\tannotation SummarizationSetBy = Automatic")
    out.append("")
    out += ignore("ENSURE_TABLES_HAVE_RELATIONSHIPS")
    return "\n".join(out)


def friendly(table: str, source: str) -> str:
    for t in spec.TABLES:
        if t.name == table:
            for c in t.columns:
                if c.source == source:
                    return c.name or c.source
    return source


def relationships() -> str:
    out = []
    for ft, fc, tt, tc, active in spec.RELATIONSHIPS:
        out.append(f"relationship {tag('rel', ft, fc, tt, tc)}")
        if not active:
            out.append("\tisActive: false")
        out.append(f"\tfromColumn: {q(ft)}.{q(friendly(ft, fc))}")
        out.append(f"\ttoColumn: {q(tt)}.{q(friendly(tt, tc))}")
        out.append("")
    return "\n".join(out)


def roles() -> list[tuple[str, str]]:
    files = []
    for name, segment, description in spec.ROLES:
        out = desc(description, "")
        out.append(f"role {q(name)}")
        out.append("\tmodelPermission: read")
        out.append("")
        out.append(f'\ttablePermission Segment = Segment[Segment] = "{segment}"')
        out.append("")
        out.append(f'\ttablePermission Ship = Ship[Ship Segment] = "{segment}"')
        out.append("")
        out.append(f"\tannotation PBI_Id = {tag('role', name).replace('-', '')}")
        out.append("")
        out += ignore("REMOVE_ROLES_WITH_NO_MEMBERS")
        files.append((name, "\n".join(out)))
    return files


def expressions() -> str:
    return "\n".join([
        "/// Where the gold Parquet files are read from: the repository's raw GitHub URL, or a local folder such as",
        "/// C:\\code\\shipping-performance-analytics\\data\\exports\\gold after cloning.",
        f'expression DataFolder = "{os.environ.get("SPA_PBI_DATA_FOLDER", GITHUB_DATA)}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
        f"\tlineageTag: {tag('expr', 'DataFolder')}",
        "",
        "\tannotation PBI_ResultType = Text",
        "",
        "/// Returns the bytes of one gold Parquet file from DataFolder (web or local).",
        "expression GoldFile =",
        "\t\t(name as text) as binary =>",
        '\t\t    if Text.StartsWith(DataFolder, "http") then Web.Contents(DataFolder & "/" & name) else File.Contents(DataFolder & "\\" & name)',
        f"\tlineageTag: {tag('expr', 'GoldFile')}",
        "",
        "\tannotation PBI_ResultType = Function",
        "",
    ])


def model_file(table_names: list[str], role_names: list[str]) -> str:
    out = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tdiscourageImplicitMeasures",
        "\tsourceQueryCulture: en-US",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        f"annotation PBI_QueryOrder = {json.dumps(['DataFolder', 'GoldFile'] + [t.name for t in spec.TABLES])}",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
    ]
    out += [f"ref table {q(t)}" for t in table_names]
    out.append("")
    out += [f"ref role {q(r)}" for r in role_names]
    out.append("")
    return "\n".join(out)


def write(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "tables").mkdir(parents=True)
    (dest / "roles").mkdir()
    (dest / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1600\n\n", encoding="utf-8")
    tables = {}
    for t in spec.TABLES:
        tables[t.name] = import_table(t)
    tables[MEASURE_TABLE] = measures_table()
    for args in spec.WHAT_IF:
        tables[args[0]] = what_if_table(*args)
    tables["Speed Relation"] = speed_relation_table()
    tables["Metric Selector"] = field_parameter()
    tables["Time Intelligence"] = calculation_group()
    for name, text in tables.items():
        (dest / "tables" / f"{name}.tmdl").write_text(text, encoding="utf-8")
    role_files = roles()
    for name, text in role_files:
        (dest / "roles" / f"{name}.tmdl").write_text(text, encoding="utf-8")
    (dest / "relationships.tmdl").write_text(relationships(), encoding="utf-8")
    (dest / "expressions.tmdl").write_text(expressions(), encoding="utf-8")
    (dest / "model.tmdl").write_text(model_file(list(tables), [r for r, _ in role_files]), encoding="utf-8")
    return dest
