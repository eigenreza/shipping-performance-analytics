"""Download the Microsoft PBIR JSON schemas used by the report, with everything
they reference, into data/cache/schemas (for offline validation in tests)."""

import re
import sys
from pathlib import Path

import requests

BASE = "https://developer.microsoft.com/json-schemas/"
RAW = "https://raw.githubusercontent.com/microsoft/json-schemas/main/"
ROOTS = [
    "fabric/item/report/definitionProperties/2.0.0/schema.json",
    "fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
    "fabric/item/report/definition/report/3.0.0/schema.json",
    "fabric/item/report/definition/page/2.0.0/schema.json",
    "fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
    "fabric/item/report/definition/visualContainer/2.4.0/schema.json",
    "fabric/item/report/definition/bookmark/2.0.0/schema.json",
    "fabric/item/report/definition/bookmarksMetadata/1.0.0/schema.json",
]


def main(out: Path) -> None:
    todo, seen = list(ROOTS), set()
    while todo:
        rel = todo.pop()
        if rel in seen:
            continue
        seen.add(rel)
        r = requests.get(RAW + rel, timeout=60)
        r.raise_for_status()
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        for ref in re.findall(r'"\$ref"\s*:\s*"([^"#]+)', r.text):
            if ref.startswith(BASE):
                todo.append(ref[len(BASE):])
            elif not ref.startswith("http"):
                todo.append(str((Path(rel).parent / ref).as_posix()).replace("/./", "/"))
    print(f"{len(seen)} schema files")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/cache/schemas"))
