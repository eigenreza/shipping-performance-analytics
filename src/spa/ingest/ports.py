"""Port areas, anchorages and coastline from open sources.

* Port area polygons and anchorage areas from OpenStreetMap (Overpass API),
  limited to Norway (ODbL).
* Coastline and land polygons for the demo map from Natural Earth (public
  domain), 1:10m scale, clipped to the Norwegian coast.
"""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import requests
from shapely.geometry import MultiPolygon, Polygon, box, mapping, shape

from spa.http import USER_AGENT
from spa.paths import RAW

OVERPASS = "https://overpass-api.de/api/interpreter"
NE_LAND = "https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip"
OUT = RAW / "ports"
NORWAY_BBOX = (4.0, 57.8, 31.5, 71.5)  # lon_min, lat_min, lon_max, lat_max

QUERY = """
[out:json][timeout:300];
area["ISO3166-1"="NO"][admin_level=2]->.no;
(
  way["landuse"="port"](area.no);
  relation["landuse"="port"](area.no);
  way["industrial"="port"](area.no);
  relation["industrial"="port"](area.no);
  way["seamark:type"="anchorage"](area.no);
  relation["seamark:type"="anchorage"](area.no);
  way["seamark:type"="anchor_berth"](area.no);
);
out tags geom;
"""


def _geom(el: dict):
    if el["type"] == "way":
        pts = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        return Polygon(pts) if len(pts) >= 4 else None
    rings = []
    for m in el.get("members", []):
        if m.get("role") == "outer" and m.get("geometry"):
            pts = [(p["lon"], p["lat"]) for p in m["geometry"]]
            if len(pts) >= 4 and pts[0] == pts[-1]:
                rings.append(Polygon(pts))
    return MultiPolygon(rings) if rings else None


def osm_areas(force: bool = False) -> int:
    dest = OUT / "osm_port_areas.parquet"
    if dest.exists() and not force:
        return len(pd.read_parquet(dest))
    r = requests.post(OVERPASS, data={"data": QUERY}, headers={"User-Agent": USER_AGENT}, timeout=400)
    r.raise_for_status()
    rows = []
    for el in r.json()["elements"]:
        g = _geom(el)
        if g is None or not g.is_valid:
            g = g.buffer(0) if g is not None else None
        if g is None or g.is_empty:
            continue
        tags = el.get("tags", {})
        kind = "anchorage" if tags.get("seamark:type", "").startswith("anchor") else "port_area"
        c = g.centroid
        rows.append({
            "osm_id": f"{el['type']}/{el['id']}",
            "kind": kind,
            "osm_name": tags.get("name"),
            "centroid_lon": c.x,
            "centroid_lat": c.y,
            "area_km2": g.area * 111.32**2 * abs(__import__("math").cos(__import__("math").radians(c.y))),
            "geojson": json.dumps(mapping(g)),
        })
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest, index=False)
    print(f"OSM areas: {df.kind.value_counts().to_dict()}")
    return len(df)


def coastline(force: bool = False) -> int:
    dest = OUT / "ne_land_norway.geojson"
    if dest.exists() and not force:
        return 1
    r = requests.get(NE_LAND, headers={"User-Agent": USER_AGENT}, timeout=300)
    r.raise_for_status()
    (OUT / "ne_10m_land.zip").write_bytes(r.content)
    import shapefile  # pyshp

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        shp = io.BytesIO(z.read("ne_10m_land.shp"))
        dbf = io.BytesIO(z.read("ne_10m_land.dbf"))
        reader = shapefile.Reader(shp=shp, dbf=dbf)
        clip = box(NORWAY_BBOX[0] - 2, NORWAY_BBOX[1] - 1.5, NORWAY_BBOX[2], NORWAY_BBOX[3])
        feats = []
        for s in reader.shapes():
            g = shape(s.__geo_interface__)
            if not g.intersects(clip):
                continue
            g = g.intersection(clip).simplify(0.005, preserve_topology=True)
            if not g.is_empty:
                feats.append({"type": "Feature", "properties": {}, "geometry": mapping(g)})
    dest.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    print(f"Natural Earth land features: {len(feats)}")
    return len(feats)


def run() -> None:
    osm_areas()
    coastline()


if __name__ == "__main__":
    run()
