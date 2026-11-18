"""The Power BI project: model spec, generated TMDL, report schemas, paginated report."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from spa import docs
from spa.powerbi import paginated, spec

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "powerbi" / "ShippingPerformance.SemanticModel" / "definition"
REPORT = ROOT / "powerbi" / "ShippingPerformance.Report"


def test_at_least_30_documented_measures():
    ms = docs.parse_measures()
    assert len(ms) >= 30
    for m in ms:
        assert m["description"], f"{m['name']} has no description"
        assert m["folder"], f"{m['name']} has no display folder"
        assert m["dax"], f"{m['name']} has no expression"


def test_measures_use_safe_division():
    for m in spec.MEASURES:
        assert not re.search(r"(?<![A-Z])/(?!/)", m.expr.replace("1000000", "").replace("* 1000", "")) or "DIVIDE" in m.expr, m.name


def test_field_parameter_and_relationships_reference_real_objects():
    names = {m.name for m in spec.MEASURES}
    assert set(spec.FIELD_PARAMETER) <= names
    tables = {t.name for t in spec.TABLES}
    for ft, _fc, tt, _tc, _active in spec.RELATIONSHIPS:
        assert ft in tables and tt in tables
    assert any(not r[4] for r in spec.RELATIONSHIPS)  # one inactive relationship, used by USERELATIONSHIP
    assert any("USERELATIONSHIP" in m.expr for m in spec.MEASURES)


def test_tmdl_has_model_features():
    text = "\n".join(p.read_text(encoding="utf-8") for p in MODEL.rglob("*.tmdl"))
    assert "calculationGroup" in text
    assert '"kind": 2' in text  # field parameter metadata
    assert "GENERATESERIES" in text  # what-if parameters
    assert "tablePermission" in text  # row-level security
    assert "dataCategory: Time" in text  # date table
    assert "discourageImplicitMeasures" in text


def test_report_matches_microsoft_schemas():
    sys.path.insert(0, str(ROOT / "tools" / "powerbi"))
    from validate_pbir import validate

    mirror = ROOT / "data" / "cache" / "schemas"
    if not (mirror / "fabric").exists():
        pytest.skip("schemas not fetched: run python tools/fetch_pbir_schemas.py")
    assert validate(REPORT, mirror) == []


def test_every_report_page_has_guide_and_footer():
    for page in (REPORT / "definition" / "pages").iterdir():
        if not page.is_dir():
            continue
        meta = json.loads((page / "page.json").read_text(encoding="utf-8"))
        if meta.get("type") == "Tooltip":
            continue
        texts = " ".join((v / "visual.json").read_text(encoding="utf-8") for v in (page / "visuals").iterdir())
        assert "What this is: " in texts and "How to use it: " in texts and "What to notice: " in texts, page.name
        assert "Developed by Reza Azad Gholami" in texts, page.name


def test_paginated_report_matches_rdl_schema():
    assert paginated.validate() == []


def test_reconciliation_results_all_match():
    rec = ROOT / "results" / "powerbi" / "reconciliation.json"
    if not rec.exists():
        pytest.skip("reconciliation has not been run against Power BI Desktop")
    s = json.loads(rec.read_text(encoding="utf-8"))["summary"]
    assert s["reconciliation_matches"] == s["reconciliation_checks"]
    assert s["measures_without_error"] == s["measures_evaluated"]
    assert s["rls_roles_passed"] == s["rls_roles"]
