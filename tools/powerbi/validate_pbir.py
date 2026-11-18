"""Validate every PBIR JSON file against Microsoft's published JSON schemas.

Schemas are read from a local mirror (default data/cache/schemas, filled by
tools/fetch_pbir_schemas.py) so validation works offline.

Usage: python tools/powerbi/validate_pbir.py [report folder] [schema mirror]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource

PREFIX = "https://developer.microsoft.com/json-schemas/"


def registry(mirror: Path) -> Registry:
    resources = []
    for f in mirror.rglob("*.json"):
        uri = PREFIX + f.relative_to(mirror).as_posix()
        resources.append((uri, Resource.from_contents(json.loads(f.read_text(encoding="utf-8")))))
    return Registry().with_resources(resources)


def validate(report: Path, mirror: Path) -> list[str]:
    reg = registry(mirror)
    errors = []
    files = [p for p in report.rglob("*.json") if "StaticResources" not in p.parts]
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        uri = doc.get("$schema")
        if not uri:
            continue
        schema = reg.get_or_retrieve(uri).value.contents
        v = Draft7Validator(schema, registry=reg)
        for e in v.iter_errors(doc):
            errors.append(f"{f.relative_to(report)}: {'/'.join(map(str, e.absolute_path))}: {e.message[:300]}")
    return errors


if __name__ == "__main__":
    rep = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("powerbi/ShippingPerformance.Report")
    mirror = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/cache/schemas")
    errs = validate(rep, mirror)
    for e in errs[:60]:
        print(e)
    print(f"{len(errs)} schema errors")
    sys.exit(1 if errs else 0)
