"""Assemble the zip that is deployed to Azure App Service (zip deploy).

The package holds the FastAPI server, its requirements and the built front
end (with the precomputed data). Build the front end first:
    cd demo/frontend && npm ci && npm run build
Usage: python deploy/package.py  ->  deploy/build/demo.zip
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deploy" / "build"


def main() -> Path:
    dist = ROOT / "demo" / "frontend" / "dist"
    if not (dist / "index.html").exists():
        raise SystemExit("build the front end first (demo/frontend: npm run build)")
    stage = OUT / "stage"
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "frontend").mkdir(parents=True)
    app = (ROOT / "demo" / "backend" / "app.py").read_text(encoding="utf-8")
    # In the package, app.py sits at the root next to frontend/dist.
    app = app.replace('Path(__file__).resolve().parents[1] / "frontend" / "dist"', 'Path(__file__).resolve().parent / "frontend" / "dist"')
    (stage / "app.py").write_text(app, encoding="utf-8")
    shutil.copy(ROOT / "demo" / "requirements.txt", stage / "requirements.txt")
    shutil.copytree(dist, stage / "frontend" / "dist")
    zpath = OUT / "demo.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(stage.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(stage))
    size = sum(f.stat().st_size for f in stage.rglob("*") if f.is_file())
    print(f"{zpath.relative_to(ROOT)}: {zpath.stat().st_size / 1e6:.1f} MB zipped, {size / 1e6:.1f} MB unpacked")
    return zpath


if __name__ == "__main__":
    main()
