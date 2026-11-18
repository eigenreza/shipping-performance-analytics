"""Command line interface: ``spa <command>``.

    spa ingest        download and parse every source into data/raw
    spa build         dbt seed, run and test (the warehouse)
    spa export        gold Parquet for Power BI, Delta medallion layers
    spa analyze       analysis questions 1 to 5 into results/
    spa ai eval       AI analyst and insight checker evaluation (cached calls)
    spa powerbi       Power BI project (TMDL, PBIR) and paginated report (RDL)
    spa powerbi-check measures, reconciliation and RLS in a running Power BI Desktop
    spa demo-export   precomputed JSON for the demo app
    spa docs          measure catalogue from TMDL and README tables from results
    spa status        data freshness and quality table
    spa refresh       all of the above in order
"""

from __future__ import annotations

import os
import subprocess
import sys

import typer
from rich.console import Console
from rich.table import Table

from spa.paths import DBT_DIR, ROOT
from spa.settings import ensure_salt

app = typer.Typer(add_completion=False, help="Shipping performance analytics pipeline.")
ai_app = typer.Typer(add_completion=False, help="AI analyst and insight writer.")
app.add_typer(ai_app, name="ai")
console = Console()


@app.command()
def ingest(
    skip_ais: bool = typer.Option(False, help="Skip AIS and port call downloads."),
    skip_weather: bool = typer.Option(False, help="Skip weather downloads."),
) -> None:
    """Download and parse every source into data/raw (resumes where it stopped)."""
    from spa.ingest import ais, carbon, mrv, ports, weather

    mrv.run()
    carbon.run()
    ports.run()
    if not skip_ais:
        ais.locations()
        ais.static()
        ais.port_calls()
        ais.positions()
        ais.tonnage_calibration()
    if not skip_weather:
        weather.run()


@app.command()
def build(target: str = typer.Option("local", help="dbt target (local or ci)."),
          raw_path: str = typer.Option(None, help="Override the raw data folder.")) -> None:
    """Build and test the dbt warehouse (seed, run, test)."""
    ensure_salt()
    dbt = os.path.join(os.path.dirname(sys.executable), "dbt")
    args = [dbt, "build", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR), "--target", target]
    if raw_path:
        args += ["--vars", f"{{raw_path: '{raw_path}'}}"]
    code = subprocess.call(args, cwd=ROOT)
    if code:
        raise typer.Exit(code)
    subprocess.call([dbt, "docs", "generate", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR),
                     "--target", target] + (["--vars", f"{{raw_path: '{raw_path}'}}"] if raw_path else []), cwd=ROOT)


@app.command()
def export(delta: bool = typer.Option(True, help="Also write Delta tables.")) -> None:
    """Write gold Parquet for Power BI and the Delta medallion layers."""
    from spa.export import delta as d

    info = d.run(delta=delta)
    console.print(info["gold_parquet"])


@app.command()
def analyze() -> None:
    """Run the analysis questions and write results/."""
    from spa.analysis import run_all

    run_all.run()


@ai_app.command("eval")
def ai_eval(live: bool = typer.Option(False, help="Allow model calls that are not cached yet.")) -> None:
    """Evaluate the AI analyst and the insight checker."""
    from spa.ai import evaluate

    evaluate.run(live=live)


@app.command("demo-export")
def demo_export() -> None:
    """Write the demo's precomputed data."""
    from spa.export import demo

    demo.run()


@app.command()
def powerbi() -> None:
    """Write the Power BI project (TMDL model, PBIR report) and the paginated RDL report."""
    from spa.powerbi import build as b
    from spa.powerbi import paginated

    b.run()
    path = paginated.build()
    errors = paginated.validate(path)
    console.print(f"Paginated report: {path.name}, {len(errors)} schema errors")
    if errors:
        raise typer.Exit(1)


@app.command("powerbi-check")
def powerbi_check(port: int = typer.Option(0, help="Port of the running Power BI Desktop model (0 = find it).")) -> None:
    """Evaluate every measure, reconcile key measures with SQL and test RLS roles in a running Power BI Desktop."""
    from spa.powerbi import reconcile

    console.print(reconcile.run(port or reconcile.desktop_port()))


@app.command()
def docs(check: bool = typer.Option(False, help="Only check that generated docs and README tables are current.")) -> None:
    """Generate docs/measures.md from TMDL and the README tables from result files."""
    from spa import docs as d

    if check:
        problems = d.check()
        for p in problems:
            console.print(f"[red]{p}[/]")
        raise typer.Exit(1 if problems else 0)
    d.write()
    console.print("docs/measures.md and README tables written")


@app.command()
def status() -> None:
    """Show the data freshness and data quality table."""
    from spa import status as s

    rows = s.run()
    table = Table(title="Data status")
    for col in ("check", "detail", "status"):
        table.add_column(col)
    colors = {"ok": "green", "warn": "yellow", "fail": "red"}
    for r in rows:
        table.add_row(r["check"], r["detail"], f"[{colors[r['status']]}]{r['status']}[/]")
    console.print(table)


@app.command()
def refresh(skip_download: bool = typer.Option(False, help="Reuse data/raw instead of downloading.")) -> None:
    """Run every step: ingest, build, export, analyze, AI evaluation, demo export, status."""
    if not skip_download:
        ingest()
    build()
    export()
    analyze()
    export(delta=True)
    powerbi()
    ai_eval(live=False)
    status()
    demo_export()
    docs()


if __name__ == "__main__":
    app()
