"""Shared fixtures: a dbt build of the synthetic raw data in tests/fixtures/raw."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DB = ROOT / "data" / "work" / "test_fixture_warehouse.duckdb"


@pytest.fixture(scope="session")
def fixture_warehouse() -> duckdb.DuckDBPyConnection:
    """Build the warehouse from the fixtures once per test session."""
    FIXTURE_DB.parent.mkdir(parents=True, exist_ok=True)
    if FIXTURE_DB.exists():
        FIXTURE_DB.unlink()
    env = {**os.environ, "SPA_WAREHOUSE": str(FIXTURE_DB), "SPA_PSEUDONYM_SALT": "fixture-salt"}
    dbt = str(Path(sys.executable).parent / "dbt")
    res = subprocess.run(
        [dbt, "build", "--project-dir", "dbt", "--profiles-dir", "dbt", "--target", "ci", "--vars", "{raw_path: 'tests/fixtures/raw'}"],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stdout[-3000:]
    con = duckdb.connect(str(FIXTURE_DB), read_only=True)
    yield con
    con.close()
