"""Assemble the Power BI project (PBIP) in powerbi/.

    powerbi/ShippingPerformance.pbip
    powerbi/ShippingPerformance.SemanticModel/   semantic model in TMDL
    powerbi/ShippingPerformance.Report/          report in the enhanced format (PBIR)
    powerbi/paginated/                           paginated report (RDL)

On Windows, when Tabular Editor 2's TOM library is available, the generated
TMDL is round-tripped through Microsoft's serializer for validation and the
canonical layout. Elsewhere the generated TMDL is used as is.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from spa.paths import CACHE, ROOT, WORK
from spa.powerbi import report, tmdl

PBI = ROOT / "powerbi"
NAME = "ShippingPerformance"
TOM = CACHE / "tools" / "te2"
NS = uuid.UUID("a6c1f0d2-55b4-4c5e-9d0a-2f1b7e0c4d31")


def platform(kind: str) -> str:
    return json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": kind, "displayName": NAME},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid5(NS, kind))},
    }, indent=2)


def build_model() -> Path:
    model_dir = PBI / f"{NAME}.SemanticModel"
    # Files Power BI Desktop writes when the project is saved (cache, local settings, diagram layout) are not part of the source.
    for leftover in (model_dir / ".pbi", model_dir / "diagramLayout.json", PBI / f"{NAME}.Report" / ".pbi"):
        if leftover.is_dir():
            shutil.rmtree(leftover, ignore_errors=True)
        elif leftover.exists():
            leftover.unlink()
    staging = tmdl.write(WORK / "tmdl_staging")
    target = model_dir / "definition"
    ps = ROOT / "tools" / "powerbi" / "normalize_tmdl.ps1"
    if sys.platform == "win32" and (TOM / "Microsoft.AnalysisServices.Tabular.dll").exists():
        res = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps),
                              "-Source", str(staging), "-Target", str(target), "-TomPath", str(TOM)],
                             capture_output=True, text=True)
        print(res.stdout.strip())
        if res.returncode:
            raise SystemExit(f"TMDL validation failed: {res.stdout} {res.stderr}")
    else:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(staging, target)
    (model_dir / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {},
    }, indent=2), encoding="utf-8")
    (model_dir / ".platform").write_text(platform("SemanticModel"), encoding="utf-8")
    return model_dir


def build_report() -> Path:
    rep = report.write(PBI / f"{NAME}.Report", f"{NAME}.SemanticModel")
    (rep / ".platform").write_text(platform("Report"), encoding="utf-8")
    return rep


def run() -> None:
    PBI.mkdir(exist_ok=True)
    build_model()
    build_report()
    (PBI / f"{NAME}.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }, indent=2), encoding="utf-8")
    print(f"Power BI project written to {PBI.relative_to(ROOT)}")


if __name__ == "__main__":
    run()
