"""Demo server: serves the built React app and its precomputed data.

The site needs no keys and no database: everything it shows was computed by
`spa demo-export` and is served as static files, compressed on the fly.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

app = FastAPI(title="Shipping performance analytics", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "built": (DIST / "index.html").exists()})


@app.middleware("http")
async def cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.startswith("/data/") or path.startswith("/powerbi/"):
        # Revalidate every time (ETag), so a new data snapshot shows at once.
        response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")
    app.mount("/data", StaticFiles(directory=DIST / "data"), name="data")
    if (DIST / "powerbi").exists():
        app.mount("/powerbi", StaticFiles(directory=DIST / "powerbi"), name="powerbi")


@app.get("/{path:path}")
def spa(path: str) -> FileResponse:
    candidate = (DIST / path).resolve()
    if path and candidate.is_file() and DIST in candidate.parents:
        return FileResponse(candidate)
    return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})
