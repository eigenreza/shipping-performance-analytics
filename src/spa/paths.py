"""Project paths, resolved relative to the repository root."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
WORK = DATA / "work"
CACHE = DATA / "cache"
FIXTURES = ROOT / "tests" / "fixtures"
RESULTS = ROOT / "results"
DBT_DIR = ROOT / "dbt"
WAREHOUSE = WORK / "warehouse.duckdb"
EXPORTS = DATA / "exports"

# Hard upper bound for every AIS, port and weather record in the project.
DATA_END = "2026-09-30"
