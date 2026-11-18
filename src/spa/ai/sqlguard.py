"""Read-only SQL access for the AI analyst.

A query is accepted only when it parses as one SELECT statement (WITH and set
operations allowed), reads only the public star schema (marts and reference)
and calls no file, network or system function. Accepted queries run on a
read-only DuckDB connection with a row limit and a time limit.
"""

from __future__ import annotations

import threading

import duckdb
import sqlglot
from sqlglot import exp

ALLOWED_SCHEMAS = {"marts", "reference"}
BLOCKED_FUNCTIONS = {
    "read_csv", "read_csv_auto", "read_parquet", "parquet_scan", "read_json", "read_json_auto", "read_text", "read_blob",
    "glob", "sniff_csv", "query", "query_table", "sqlite_scan", "postgres_scan", "mysql_scan", "delta_scan", "iceberg_scan",
    "getenv", "current_setting", "duckdb_settings", "duckdb_secrets", "duckdb_extensions", "pragma", "system",
}
MAX_ROWS = 200
TIMEOUT_S = 5.0


class UnsafeQuery(ValueError):
    pass


def check(sql: str) -> str:
    """Return the normalised SQL if it is a safe SELECT, else raise UnsafeQuery."""
    try:
        statements = sqlglot.parse(sql, read="duckdb")
    except sqlglot.errors.ParseError as e:
        raise UnsafeQuery(f"could not parse the query: {str(e)[:200]}") from e
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise UnsafeQuery("send exactly one statement")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise UnsafeQuery("only SELECT statements are allowed")
    for node in tree.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command,
                             exp.Copy, exp.Set, exp.Pragma, exp.Attach, exp.Detach, exp.Use, exp.Merge)):
            raise UnsafeQuery(f"statement type {type(node).__name__} is not allowed")
        if isinstance(node, exp.Func):
            name = (node.sql_name() if not isinstance(node, exp.Anonymous) else node.name).lower()
            if name in BLOCKED_FUNCTIONS:
                raise UnsafeQuery(f"function {name} is not allowed")
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if isinstance(table.this, exp.Func) or table.args.get("this") is None:
            raise UnsafeQuery("table functions are not allowed")
        name = table.name.lower()
        schema = (table.db or "").lower()
        if not schema and name in ctes:
            continue
        if schema not in ALLOWED_SCHEMAS:
            raise UnsafeQuery(f"table {table.sql()} is outside the allowed schemas; use marts.<table> or reference.<table>")
        if table.catalog:
            raise UnsafeQuery("database-qualified names are not allowed")
    return tree.sql(dialect="duckdb")


def run(con: duckdb.DuckDBPyConnection, sql: str, max_rows: int = MAX_ROWS, timeout_s: float = TIMEOUT_S) -> dict:
    """Run a checked query with row and time limits; returns columns, rows and the SQL that ran."""
    safe = check(sql)
    limited = f"select * from ({safe}) as q limit {max_rows + 1}"
    timer = threading.Timer(timeout_s, con.interrupt)
    timer.start()
    try:
        cur = con.execute(limited)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    except duckdb.InterruptException as e:
        raise UnsafeQuery(f"query stopped after {timeout_s:.0f} seconds") from e
    finally:
        timer.cancel()
    truncated = len(rows) > max_rows
    return {"sql": safe, "columns": cols, "rows": [list(r) for r in rows[:max_rows]], "truncated": truncated}
