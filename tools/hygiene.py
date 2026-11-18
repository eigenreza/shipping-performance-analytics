"""Hygiene and privacy scan of every file that would be published.

Checks text files for dashes used as punctuation, banned words, tool names,
local paths, secrets, e-mail addresses, dates after the data end date and
operator names; data files for real ship identifiers (IMO numbers, MMSI
numbers and ship names, compared against the private raw data when it is
present); PDF and PNG files for metadata.

Usage: python tools/hygiene.py            exit code 1 when anything fails
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pathspec

ROOT = Path(__file__).resolve().parents[1]
ALWAYS_SKIP = {".git", ".venv", "node_modules", "_admin", ".claude", "bin", "obj", "__pycache__", ".pytest_cache", ".ruff_cache"}
TEXT_EXT = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".sql", ".csv", ".tmdl", ".pbism", ".pbir", ".pbip", ".rdl",
            ".ts", ".tsx", ".css", ".html", ".js", ".ps1", ".bicep", ".cs", ".csproj", ".platform", ".svg", ".gitignore", ".cfg", ".ini"}
DATA_END = "2026-09-30"

# Extra terms for a project can be kept in a local file that is never published (_admin is ignored).
_LOCAL_TERMS = ROOT / "_admin" / "hygiene-terms.json"
_local = json.loads(_LOCAL_TERMS.read_text(encoding="utf-8")) if _LOCAL_TERMS.exists() else {}
FORBIDDEN = _local.get("forbidden", [])
CASE_SENSITIVE = _local.get("case_sensitive", [])
# Operators of vehicle carriers and ro-ro ships; none may appear in public files.
OPERATORS = [
    r"h[oø]egh",
    r"\buecc\b",
    r"hyundai glovis",
    r"\bglovis\b",
    r"grimaldi",
    r"\bnyk\b",
    r"\bk[- ]line\b",
    r"mitsui o\.?s\.?k",
    r"sallaum",
    r"neptune lines",
    r"\beukor\b",
    r"toyofuji",
    r"\bdfds\b",
    r"stena line",
    r"finnlines",
    r"sea-cargo",
    r"\bsmyril\b",
    r"transfennica",
    r"\bcldn\b",
    r"\bnor lines\b",
    r"\bbore ltd\b",
    r"\bcobelfret\b",
    r"\bsiem car\b",
    r"wallenius",
    r"wilhelmsen",
]
TOOLS = _local.get("tools", [])
WARN = [r"\bapplication\b", r"\bjob\b"]
SECRETS = [r"AIza[0-9A-Za-z_\-]{30,}", r"gh[opsu]_[0-9A-Za-z]{30,}", r"\bsk-[0-9A-Za-z]{20,}", r"SPA_PSEUDONYM_SALT\s*=\s*[0-9a-f]{16,}"]
PATHS = [r"[A-Za-z]:\\Users\\", r"/Users/[a-z]", r"\brezaa\b", r"AppData", r"/home/[a-z]"]
EMAIL = r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
EMAIL_OK = {"noreply.github.com"}
DATE = r"\b(20\d\d)-(\d\d)(?:-(\d\d))?\b"


def public_files() -> list[Path]:
    spec = pathspec.PathSpec.from_lines("gitwildmatch", (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel_dir = Path(dirpath).relative_to(ROOT)
        # Prune skipped and ignored folders before descending into them.
        dirnames[:] = [d for d in dirnames if d not in ALWAYS_SKIP and not spec.match_file((rel_dir / d).as_posix() + "/")]
        for name in filenames:
            rel = rel_dir / name
            if not spec.match_file(rel.as_posix()):
                out.append(ROOT / rel)
    return sorted(out)


def private_identifiers() -> tuple[set[str], set[str], set[str]]:
    """Real IMO numbers, MMSI numbers and ship names from the private raw layer, if present."""
    imos, mmsis, names = set(), set(), set()
    raw = ROOT / "data" / "raw"
    try:
        import duckdb

        if (raw / "mrv").exists():
            for imo, name in duckdb.sql(f"""select distinct cast(imo_number as varchar), upper(trim(name))
                from read_parquet('{(raw / 'mrv').as_posix()}/mrv_*.parquet', union_by_name=true)
                where ship_type in ('Ro-ro ship', 'Vehicle carrier')""").fetchall():
                if imo and imo.isdigit():
                    imos.add(imo)
                if name and len(name) >= 6 and not name.isdigit():
                    names.add(name)
        if (raw / "ports" / "kystverket_locations.parquet").exists():
            # Ships are often named after places; a port name is not a ship identifier.
            places = {r[0] for r in duckdb.sql(f"""select distinct upper(trim(locationnamenor))
                from '{(raw / 'ports' / 'kystverket_locations.parquet').as_posix()}'""").fetchall() if r[0]}
            names -= places
        if (raw / "ais" / "static_fleet.parquet").exists():
            for (m,) in duckdb.sql(f"select distinct cast(mmsi as varchar) from '{(raw / 'ais' / 'static_fleet.parquet').as_posix()}'").fetchall():
                mmsis.add(m)
    except Exception:  # noqa: BLE001 - raw data is optional (CI has none)
        pass
    return imos, mmsis, names


def scan_text(path: Path, text: str, ids) -> tuple[list[str], list[str]]:
    fails, warns = [], []
    rel = path.relative_to(ROOT).as_posix()
    lines = text.splitlines()
    imos, mmsis, names = ids
    is_tool_list = rel.endswith("tools/hygiene.py") or rel.endswith("tests/test_hygiene.py")
    for i, line in enumerate(lines, 1):
        where = f"{rel}:{i}"
        if chr(0x2014) in line or chr(0x2013) in line:
            fails.append(f"{where}: em or en dash")
        if is_tool_list:
            continue
        low = line.lower()
        for pat in FORBIDDEN + OPERATORS:
            if re.search(pat, low):
                fails.append(f"{where}: banned word /{pat}/")
        for pat in CASE_SENSITIVE:
            if re.search(pat, line):
                fails.append(f"{where}: banned word /{pat}/")
        if path.suffix not in (".css", ".tsx", ".ts", ".js"):
            for pat in TOOLS:
                if re.search(pat, low):
                    fails.append(f"{where}: tool name")
        for pat in SECRETS + PATHS:
            if re.search(pat, line):
                fails.append(f"{where}: secret or local path /{pat}/")
        for m in re.finditer(EMAIL, line):
            if m.group(0).split("@")[1] not in EMAIL_OK and not m.group(0).endswith((".png", ".svg")):
                fails.append(f"{where}: e-mail address")
        for m in re.finditer(DATE, line):
            y, mo, d = m.group(1), m.group(2), m.group(3) or "01"
            if 1 <= int(mo) <= 12 and f"{y}-{mo}-{d}" > DATA_END and not (y == "2026" and mo == "09"):
                before = line[max(0, m.start() - 40):m.start()]
                # An exclusive upper bound in recorded SQL (date < '2026-10-01') is not data after the end.
                if not re.search(r"schema|version|\d\.\d", before) and not re.search(r"<\s*(?:DATE\s*)?'?$", before, re.I):
                    fails.append(f"{where}: date after the data end ({m.group(0)})")
        for pat in WARN:
            if re.search(pat, low):
                warns.append(f"{where}: check wording /{pat}/")
        if re.search(r"\bIMO\s*(?:no\.?|number)?\s*\d{7}\b", line, re.I):
            fails.append(f"{where}: IMO-like number")
    if path.suffix in (".json", ".csv", ".md", ".tsx", ".rdl", ".tmdl", ".html") and (imos or mmsis or names):
        tokens = set(re.findall(r"\b\d{7}\b|\b\d{9}\b", text))
        hit = (tokens & imos) | (tokens & mmsis)
        if hit:
            fails.append(f"{rel}: real IMO or MMSI numbers present ({len(hit)})")
        is_data = "/public/data/" in rel or rel.startswith("results/") or rel.startswith("data/exports/")
        words = re.findall(r"[A-Z0-9À-Þ]+", text.upper())
        grams = {" ".join(words[i:i + n]) for n in (1, 2, 3, 4) for i in range(len(words) - n + 1)}
        exact = set(re.findall(r"[A-Z0-9À-Þ]+", text))  # single-word names must match in upper case
        named = [n for n in names if (" " in n and n in grams) or (is_data and " " not in n and n in exact)]
        if named:
            fails.append(f"{rel}: real ship names present: {named[:5]}")
    return fails, warns


def scan_parquet(path: Path, ids) -> list[str]:
    """Public Parquet files must not hold real identifiers or names."""
    import pyarrow.parquet as pq

    rel = path.relative_to(ROOT).as_posix()
    imos, mmsis, names = ids
    t = pq.read_table(path)
    values = set()
    for col in t.columns:
        values.update(str(v) for v in col.to_pylist() if v is not None)
    out = []
    if values & (imos | mmsis):
        out.append(f"{rel}: real IMO or MMSI numbers present")
    if {v.upper() for v in values} & names:
        out.append(f"{rel}: real ship names present")
    return out


def scan_binary(path: Path) -> list[str]:
    rel = path.relative_to(ROOT).as_posix()
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        r = PdfReader(str(path))
        info = {k: str(v) for k, v in (r.metadata or {}).items() if str(v).strip()}
        if info or "/Metadata" in r.trailer["/Root"]:
            return [f"{rel}: PDF metadata present {list(info)}"]
    if path.suffix.lower() == ".png":
        from PIL import Image

        with Image.open(path) as im:
            meta = {k: v for k, v in im.info.items() if k not in ("dpi", "gamma", "transparency", "srgb", "icc_profile")}
        if meta:
            return [f"{rel}: PNG metadata present {list(meta)}"]
    return []


def run() -> dict:
    ids = private_identifiers()
    fails, warns, files, size = [], [], 0, 0
    for p in public_files():
        files += 1
        size += p.stat().st_size
        if p.suffix.lower() in (".pdf", ".png"):
            fails += scan_binary(p)
        elif p.suffix.lower() == ".parquet":
            fails += scan_parquet(p, ids)
        elif p.suffix.lower() in TEXT_EXT or p.name in (".gitignore", "LICENSE"):
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = p.read_text(encoding="utf-8-sig", errors="replace")
            f, w = scan_text(p, text, ids)
            fails += f
            warns += w
    return {"files": files, "bytes": size, "fails": fails, "warnings": warns,
            "checked_against_private_ids": bool(ids[0])}


if __name__ == "__main__":
    res = run()
    for f in res["fails"][:200]:
        print("FAIL", f)
    for w in res["warnings"][:80]:
        print("warn", w)
    print(json.dumps({k: v for k, v in res.items() if k not in ("fails", "warnings")}), f"{len(res['fails'])} fails, {len(res['warnings'])} warnings")
    sys.exit(1 if res["fails"] else 0)
