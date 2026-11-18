# Operations: refresh, monitoring and deployment

## One command

`spa refresh` runs every step in order:

1. `spa ingest`: download and parse every source into `data/raw` (each request is checkpointed, so a rerun resumes; free API limits are respected and a step that hits a limit stops and records its coverage instead of waiting).
2. `spa build`: dbt seed, run and test, then `dbt docs generate`. A failing test stops the refresh.
3. `spa export`: gold Parquet for Power BI and the demo, and the bronze, silver and gold Delta tables.
4. `spa analyze`: the five analysis questions with intervals, the main figure and the model parameters for Power BI.
5. `spa powerbi`: regenerate the TMDL model, the PBIR report and the paginated RDL.
6. `spa ai eval`: the AI evaluation, replayed from the call cache.
7. `spa status`: the freshness and quality table.
8. `spa demo-export` and `spa docs`: the demo data, the measure catalogue and the README tables.

## Monitoring

`spa status` writes `results/status.json` and prints a table of checks with ok, warn or fail:

- **Freshness** of AIS positions, port calls, carbon prices and weather against the data end date, and the latest MRV reporting year.
- **Quality**: the share of ship-years that pass the plausibility checks, the share of AIS-derived port calls that Kystverket's own records confirm, and the share of ships with a gross tonnage.
- **dbt tests**: passed out of run.

The same table is shown on the demo's "How it is built" page.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request, without secrets and without data downloads:

- lint (ruff), the Python tests, and a dbt build and test on the synthetic fixtures in `tests/fixtures/raw`;
- a check that the README tables and the measure catalogue match the result files and the TMDL;
- the Best Practice Analyzer on the TMDL model (Windows runner, Tabular Editor 2 portable);
- a build of the demo and a smoke test of every data file and the home page.

## Deployment

The demo is a FastAPI app serving the built React app and its precomputed data, so it needs no database and no keys. `python deploy/package.py` assembles the zip; `deploy/main.bicep` describes the Azure App Service Free (F1) Linux plan and web app. Deployment is a zip deploy of that package.

## Rebuilding the Power BI checks

On Windows with Power BI Desktop and Tabular Editor 2:

1. `spa powerbi`, then open `powerbi/ShippingPerformance.pbip` in Desktop and refresh.
2. `spa powerbi-check` evaluates every measure, reconciles key measures with SQL and tests the roles against the running model.
3. `tools/powerbi/run_bpa.ps1 -TabularEditor <path to TabularEditor.exe>` runs the Best Practice Analyzer.
